from typing import Union
import warnings
import numpy as np
from copy import copy
from scipy import ndimage as ndi
from xml.etree.ElementTree import Element
from base64 import b64encode
from imageio import imwrite

from ..base import Layer
from ...util.colormaps import colormaps
from ...util.event import Event
from ...util.misc import interpolate_coordinates
from ._constants import Mode


class Labels(Layer):
    """Labels (or segmentation) layer.

    An image-like layer where every pixel contains an integer ID
    corresponding to the region it belongs to.

    Parameters
    ----------
    data : array
        Labels data.
    num_colors : int
        Number of unique colors to use in colormap.
    seed : float
        Seed for colormap random generator.
    n_dimensional : bool
        If `True`, paint and fill edit labels across all dimensions.
    name : str
        Name of the layer.
    metadata : dict
        Layer metadata.
    scale : tuple of float
        Scale factors for the layer.
    translate : tuple of float
        Translation values for the layer.
    opacity : float
        Opacity of the layer visual, between 0.0 and 1.0.
    blending : str
        One of a list of preset blending modes that determines how RGB and
        alpha values of the layer visual get mixed. Allowed values are
        {'opaque', 'translucent', and 'additive'}.
    visible : bool
        Whether the layer visual is currently being displayed.

    Attributes
    ----------
    data : array
        Integer valued label data. Can be N dimensional. Every pixel contains
        an integer ID corresponding to the region it belongs to. The label 0 is
        rendered as transparent.
    metadata : dict
        Labels metadata.
    num_colors : int
        Number of unique colors to use in colormap.
    seed : float
        Seed for colormap random generator.
    opacity : float
        Opacity of the labels, must be between 0 and 1.
    contiguous : bool
        If `True`, the fill bucket changes only connected pixels of same label.
    n_dimensional : bool
        If `True`, paint and fill edit labels across all dimensions.
    brush_size : float
        Size of the paint brush.
    selected_label : int
        Index of selected label. Can be greater than the current maximum label.
    mode : str
        Interactive mode. The normal, default mode is PAN_ZOOM, which
        allows for normal interactivity with the canvas.

        In PICKER mode the cursor functions like a color picker, setting the
        clicked on label to be the curent label. If the background is picked it
        will select the background label `0`.

        In PAINT mode the cursor functions like a paint brush changing any
        pixels it brushes over to the current label. If the background label
        `0` is selected than any pixels will be changed to background and this
        tool functions like an eraser. The size and shape of the cursor can be
        adjusted in the properties widget.

        In FILL mode the cursor functions like a fill bucket replacing pixels
        of the label clicked on with the current label. It can either replace
        all pixels of that label or just those that are contiguous with the
        clicked on pixel. If the background label `0` is selected than any
        pixels will be changed to background and this tool functions like an
        eraser.

    Extended Summary
    ----------
    _data_labels : array (N, M)
        2D labels data for the currently viewed slice.
    _selected_color : 4-tuple or None
        RGBA tuple of the color of the selected label, or None if the
        background label `0` is selected.
    _last_cursor_coord : list or None
        Coordinates of last cursor click before painting, gets reset to None
        after painting is done. Used for interpolating brush strokes.
    """

    def __init__(
        self,
        data,
        *,
        num_colors=50,
        seed=0.5,
        n_dimensional=False,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=0.7,
        blending='translucent',
        visible=True,
    ):

        super().__init__(
            data.ndim,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )

        self.events.add(
            contrast_limits=Event,
            colormap=Event,
            interpolation=Event,
            rendering=Event,
            mode=Event,
            n_dimensional=Event,
            contiguous=Event,
            brush_size=Event,
            selected_label=Event,
        )

        self._data = data
        self._data_labels = np.zeros((1,) * self.dims.ndisplay)
        self._data_view = np.zeros((1,) * self.dims.ndisplay)
        self.contrast_limits = [0.0, 1.0]
        self.interpolation = 'nearest'
        self.rendering = 'mip'
        self._seed = seed

        self._colormap_name = 'random'
        self._num_colors = num_colors
        self.colormap = (
            self._colormap_name,
            colormaps.label_colormap(self.num_colors),
        )

        self._n_dimensional = n_dimensional
        self._contiguous = True
        self._brush_size = 10
        self._last_cursor_coord = None

        self._selected_label = 0
        self._selected_color = None

        self._mode = Mode.PAN_ZOOM
        self._mode_history = self._mode
        self._status = self.mode
        self._help = 'enter paint or fill mode to edit labels'

        # Trigger generation of view slice and thumbnail
        self._update_dims()

    @property
    def data(self):
        """array: Labels data."""
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        self._update_dims()
        self.events.data()

    def _get_ndim(self):
        """Determine number of dimensions of the layer."""
        return self.data.ndim

    def _get_extent(self):
        return tuple((0, m) for m in self.data.shape)

    @property
    def contiguous(self):
        """bool: fill bucket changes only connected pixels of same label."""
        return self._contiguous

    @contiguous.setter
    def contiguous(self, contiguous):
        self._contiguous = contiguous
        self.events.contiguous()

    @property
    def n_dimensional(self):
        """bool: paint and fill edits labels across all dimensions."""
        return self._n_dimensional

    @n_dimensional.setter
    def n_dimensional(self, n_dimensional):
        self._n_dimensional = n_dimensional
        self.events.n_dimensional()

    @property
    def brush_size(self):
        """float: Size of the paint brush."""
        return self._brush_size

    @brush_size.setter
    def brush_size(self, brush_size):
        self._brush_size = int(brush_size)
        self.cursor_size = self._brush_size / self.scale_factor
        self.events.brush_size()

    @property
    def seed(self):
        """float: Seed for colormap random generator."""
        return self._seed

    @seed.setter
    def seed(self, seed):
        self._seed = seed
        self._set_view_slice()

    @property
    def num_colors(self):
        """int: Number of unique colors to use in colormap."""
        return self._num_colors

    @num_colors.setter
    def num_colors(self, num_colors):
        self._num_colors = num_colors
        self.colormap = (
            self._colormap_name,
            colormaps.label_colormap(num_colors),
        )
        self._set_view_slice()

    @property
    def selected_label(self):
        """int: Index of selected label."""
        return self._selected_label

    @selected_label.setter
    def selected_label(self, selected_label):
        if selected_label < 0:
            raise ValueError('cannot reduce selected label below 0')
        if selected_label == self.selected_label:
            return

        self._selected_label = selected_label
        self._selected_color = self.get_color(selected_label)
        self.events.selected_label()

    @property
    def mode(self):
        """MODE: Interactive mode. The normal, default mode is PAN_ZOOM, which
        allows for normal interactivity with the canvas.

        In PICKER mode the cursor functions like a color picker, setting the
        clicked on label to be the curent label. If the background is picked it
        will select the background label `0`.

        In PAINT mode the cursor functions like a paint brush changing any
        pixels it brushes over to the current label. If the background label
        `0` is selected than any pixels will be changed to background and this
        tool functions like an eraser. The size and shape of the cursor can be
        adjusted in the properties widget.

        In FILL mode the cursor functions like a fill bucket replacing pixels
        of the label clicked on with the current label. It can either replace
        all pixels of that label or just those that are contiguous with the
        clicked on pixel. If the background label `0` is selected than any
        pixels will be changed to background and this tool functions like an
        eraser.
        """
        return str(self._mode)

    @mode.setter
    def mode(self, mode: Union[str, Mode]):

        if isinstance(mode, str):
            mode = Mode(mode)

        if mode == self._mode:
            return

        if mode == Mode.PAN_ZOOM:
            self.cursor = 'standard'
            self.interactive = True
            self.help = 'enter paint or fill mode to edit labels'
        elif mode == Mode.PICKER:
            self.cursor = 'cross'
            self.interactive = False
            self.help = 'hold <space> to pan/zoom, ' 'click to pick a label'
        elif mode == Mode.PAINT:
            self.cursor_size = self.brush_size / self.scale_factor
            self.cursor = 'square'
            self.interactive = False
            self.help = 'hold <space> to pan/zoom, ' 'drag to paint a label'
        elif mode == Mode.FILL:
            self.cursor = 'cross'
            self.interactive = False
            self.help = 'hold <space> to pan/zoom, ' 'click to fill a label'
        else:
            raise ValueError("Mode not recongnized")

        self.status = str(mode)
        self._mode = mode

        self.events.mode(mode=mode)
        self._set_view_slice()

    def _raw_to_displayed(self, raw):
        """Determine displayed image from a saved raw image and a saved seed.

        This function ensures that the 0 label gets mapped to the 0 displayed
        pixel.

        Parameters
        -------
        raw : array or int
            Raw integer input image.

        Returns
        -------
        image : array
            Image mapped between 0 and 1 to be displayed.
        """
        image = np.where(
            raw > 0, colormaps._low_discrepancy_image(raw, self._seed), 0
        )
        return image

    def new_colormap(self):
        self._seed = np.random.rand()
        self._selected_color = self.get_color(self.selected_label)
        self._set_view_slice()

    def get_color(self, label):
        """Return the color corresponding to a specific label."""
        if label == 0:
            col = None
        else:
            val = self._raw_to_displayed(np.array([label]))
            col = self.colormap[1].map(val)[0]
        return col

    def _set_view_slice(self):
        """Sets the view given the indices to slice with."""
        self._data_labels = np.asarray(self.data[self.dims.indices]).transpose(
            self.dims.displayed_order
        )
        self._data_view = self._raw_to_displayed(self._data_labels)

        self._update_thumbnail()
        self._update_coordinates()
        self.events.set_data()

    def fill(self, coord, old_label, new_label):
        """Replace an existing label with a new label, either just at the
        connected component if the `contiguous` flag is `True` or everywhere
        if it is `False`, working either just in the current slice if
        the `n_dimensional` flag is `False` or on the entire data if it is
        `True`.

        Parameters
        ----------
        coord : sequence of float
            Position of mouse cursor in image coordinates.
        old_label : int
            Value of the label image at the coord to be replaced.
        new_label : int
            Value of the new label to be filled in.
        """
        int_coord = np.round(coord).astype(int)

        if self.n_dimensional or self.ndim == 2:
            # work with entire image
            labels = self.data
            slice_coord = tuple(int_coord)
        else:
            # work with just the sliced image
            labels = self._data_labels
            slice_coord = tuple(int_coord[d] for d in self.dims.displayed)

        matches = labels == old_label
        if self.contiguous:
            # if not contiguous replace only selected connected component
            labeled_matches, num_features = ndi.label(matches)
            if num_features != 1:
                match_label = labeled_matches[slice_coord]
                matches = np.logical_and(
                    matches, labeled_matches == match_label
                )

        # Replace target pixels with new_label
        labels[matches] = new_label

        if not (self.n_dimensional or self.ndim == 2):
            # if working with just the slice, update the rest of the raw data
            self.data[tuple(self.indices)] = labels

        self._set_view_slice()

    def paint(self, coord, new_label):
        """Paint over existing labels with a new label, using the selected
        brush shape and size, either only on the visible slice or in all
        n dimensions.

        Parameters
        ----------
        coord : sequence of int
            Position of mouse cursor in image coordinates.
        new_label : int
            Value of the new label to be filled in.
        """
        if self.n_dimensional or self.ndim == 2:
            slice_coord = tuple(
                [
                    slice(
                        np.round(
                            np.clip(c - self.brush_size / 2 + 0.5, 0, s)
                        ).astype(int),
                        np.round(
                            np.clip(c + self.brush_size / 2 + 0.5, 0, s)
                        ).astype(int),
                        1,
                    )
                    for c, s in zip(coord, self.shape)
                ]
            )
        else:
            slice_coord = [0] * self.ndim
            for i in self.dims.displayed:
                slice_coord[i] = slice(
                    np.round(
                        np.clip(
                            coord[i] - self.brush_size / 2 + 0.5,
                            0,
                            self.shape[i],
                        )
                    ).astype(int),
                    np.round(
                        np.clip(
                            coord[i] + self.brush_size / 2 + 0.5,
                            0,
                            self.shape[i],
                        )
                    ).astype(int),
                    1,
                )
            for i in self.dims.not_displayed:
                slice_coord[i] = np.round(coord[i]).astype(int)
            slice_coord = tuple(slice_coord)

        # update the labels image
        self.data[slice_coord] = new_label

        self._set_view_slice()

    def get_value(self):
        """Returns coordinates, values, and a string for a given mouse position
        and set of indices.

        Returns
        ----------
        coord : tuple of int
            Position of mouse cursor in data.
        value : int or float or sequence of int or float or None
            Value of the data at the coord, or none if coord is outside range.
        """
        coord = np.round(self.coordinates).astype(int)
        shape = self._data_labels.shape
        if all(0 <= c < s for c, s in zip(coord[self.dims.displayed], shape)):
            value = self._data_labels[tuple(coord[self.dims.displayed])]
        else:
            value = None

        return value

    def _update_thumbnail(self):
        """Update thumbnail with current image data and colors.
        """
        if self.dims.ndisplay == 3:
            image = np.max(self._data_labels, axis=0)
        else:
            image = self._data_labels

        zoom_factor = np.divide(
            self._thumbnail_shape[:2], image.shape[:2]
        ).min()
        # warning filter can be removed with scipy 1.4
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            downsampled = np.round(
                ndi.zoom(image, zoom_factor, prefilter=False, order=0)
            )
        downsampled = self._raw_to_displayed(downsampled)
        colormapped = self.colormap[1].map(downsampled)
        colormapped = colormapped.reshape(downsampled.shape + (4,))
        # render background as black instead of transparent
        colormapped[..., 3] = 1
        colormapped[..., 3] *= self.opacity
        self.thumbnail = colormapped

    def to_xml_list(self):
        """Generates a list with a single xml element that defines the
        currently viewed image as a png according to the svg specification.

        Returns
        ----------
        xml : list of xml.etree.ElementTree.Element
            List of a single xml element specifying the currently viewed image
            as a png according to the svg specification.
        """
        mapped_image = (self.colormap[1].map(self._data_view) * 255).astype(
            np.uint8
        )
        mapped_image = mapped_image.reshape(list(self._data_view.shape) + [4])
        image_str = imwrite('<bytes>', mapped_image, format='png')
        image_str = "data:image/png;base64," + str(b64encode(image_str))[2:-1]
        props = {'xlink:href': image_str}
        width = str(self.shape[self.dims.displayed[1]])
        height = str(self.shape[self.dims.displayed[0]])
        opacity = str(self.opacity)
        xml = Element(
            'image', width=width, height=height, opacity=opacity, **props
        )
        return [xml]

    def on_mouse_press(self, event):
        """Called whenever mouse pressed in canvas.

        Parameters
        ----------
        event : Event
            Vispy event
        """
        if self._mode == Mode.PAN_ZOOM:
            # If in pan/zoom mode do nothing
            pass
        elif self._mode == Mode.PICKER:
            self.selected_label = self._value
        elif self._mode == Mode.PAINT:
            # Start painting with new label
            self.paint(self.coordinates, self.selected_label)
            self._last_cursor_coord = copy(self.coordinates)
        elif self._mode == Mode.FILL:
            # Fill clicked on region with new label
            self.fill(self.coordinates, self._value, self.selected_label)
        else:
            raise ValueError("Mode not recongnized")

    def on_mouse_move(self, event):
        """Called whenever mouse moves over canvas.

        Parameters
        ----------
        event : Event
            Vispy event
        """
        if self._mode == Mode.PAINT and event.is_dragging:
            new_label = self.selected_label
            if self._last_cursor_coord is None:
                interp_coord = [self.coordinates]
            else:
                interp_coord = interpolate_coordinates(
                    self._last_cursor_coord, self.coordinates, self.brush_size
                )
            with self.events.set_data.blocker():
                for c in interp_coord:
                    self.paint(c, new_label)
            self._set_view_slice()
            self._last_cursor_coord = copy(self.coordinates)

    def on_mouse_release(self, event):
        """Called whenever mouse released in canvas.

        Parameters
        ----------
        event : Event
            Vispy event
        """
        self._last_cursor_coord = None
