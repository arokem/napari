import numpy as np
from math import inf
from itertools import zip_longest
from xml.etree.ElementTree import Element, tostring
from .dims import Dims
from .layerlist import LayerList
from .. import layers
from ..util.event import EmitterGroup, Event
from ..util.keybindings import KeymapMixin
from ..util.theme import palettes


class ViewerModel(KeymapMixin):
    """Viewer containing the rendered scene, layers, and controlling elements
    including dimension sliders, and control bars for color limits.

    Parameters
    ----------
    title : string
        The title of the viewer window.
    ndisplay : int
        Number of displayed dimensions.
    tuple of int
        Order in which dimensions are displayed where the last two or last
        three dimensions correspond to row x column or plane x row x column if
        ndisplay is 2 or 3.

    Attributes
    ----------
    window : Window
        Parent window.
    layers : LayerList
        List of contained layers.
    dims : Dimensions
        Contains axes, indices, dimensions and sliders.
    themes : dict of str: dict of str: str
        Preset color palettes.
    """

    themes = palettes

    def __init__(self, title='napari', ndisplay=2, order=None):
        super().__init__()

        self.events = EmitterGroup(
            source=self,
            auto_connect=True,
            status=Event,
            help=Event,
            title=Event,
            interactive=Event,
            cursor=Event,
            reset_view=Event,
            active_layer=Event,
            palette=Event,
        )

        if order is None:
            ndim = ndisplay
            order = list(range(ndim))
        else:
            ndim = len(order)

        self.dims = Dims(ndim)
        self.dims.ndisplay = ndisplay
        self.dims.order = order

        self.layers = LayerList()

        self._status = 'Ready'
        self._help = ''
        self._title = title
        self._cursor = 'standard'
        self._cursor_size = None
        self._interactive = True
        self._active_layer = None

        self._palette = None
        self.theme = 'dark'

        self.dims.events.camera.connect(lambda e: self.reset_view())
        self.dims.events.ndisplay.connect(lambda e: self._update_layers())
        self.dims.events.order.connect(lambda e: self._update_layers())
        self.dims.events.axis.connect(lambda e: self._update_layers())
        self.layers.events.added.connect(self._on_layers_change)
        self.layers.events.removed.connect(self._on_layers_change)
        self.layers.events.added.connect(self._update_active_layer)
        self.layers.events.removed.connect(self._update_active_layer)
        self.layers.events.reordered.connect(self._update_active_layer)

    @property
    def palette(self):
        """dict of str: str : Color palette with which to style the viewer.
        """
        return self._palette

    @palette.setter
    def palette(self, palette):
        if palette == self.palette:
            return

        self._palette = palette
        self.events.palette(palette=palette)

    @property
    def theme(self):
        """string or None : Preset color palette.
        """
        for theme, palette in self.themes.items():
            if palette == self.palette:
                return theme

    @theme.setter
    def theme(self, theme):
        if theme == self.theme:
            return

        try:
            self.palette = self.themes[theme]
        except KeyError:
            raise ValueError(
                f"Theme '{theme}' not found; "
                f"options are {list(self.themes)}."
            )

    @property
    def status(self):
        """string: Status string
        """
        return self._status

    @status.setter
    def status(self, status):
        if status == self.status:
            return
        self._status = status
        self.events.status(text=self._status)

    @property
    def help(self):
        """string: String that can be displayed to the
        user in the status bar with helpful usage tips.
        """
        return self._help

    @help.setter
    def help(self, help):
        if help == self.help:
            return
        self._help = help
        self.events.help(text=self._help)

    @property
    def title(self):
        """string: String that is displayed in window title.
        """
        return self._title

    @title.setter
    def title(self, title):
        if title == self.title:
            return
        self._title = title
        self.events.title(text=self._title)

    @property
    def interactive(self):
        """bool: Determines if canvas pan/zoom interactivity is enabled or not.
        """
        return self._interactive

    @interactive.setter
    def interactive(self, interactive):
        if interactive == self.interactive:
            return
        self._interactive = interactive
        self.events.interactive()

    @property
    def cursor(self):
        """string: String identifying cursor displayed over canvas.
        """
        return self._cursor

    @cursor.setter
    def cursor(self, cursor):
        if cursor == self.cursor:
            return
        self._cursor = cursor
        self.events.cursor()

    @property
    def cursor_size(self):
        """int | None: Size of cursor if custom. None is yields default size
        """
        return self._cursor_size

    @cursor_size.setter
    def cursor_size(self, cursor_size):
        if cursor_size == self.cursor_size:
            return
        self._cursor_size = cursor_size
        self.events.cursor()

    @property
    def active_layer(self):
        """int: index of active_layer
        """
        return self._active_layer

    @active_layer.setter
    def active_layer(self, active_layer):
        if active_layer == self.active_layer:
            return
        self._active_layer = active_layer
        self.events.active_layer(item=self._active_layer)

    def reset_view(self):
        """Resets the camera's view using `event.viewbox` a 4-tuple of the x, y
        corner position followed by width and height of the camera
        """
        # Scale the camera to the contents in the scene
        min_shape, max_shape = self._calc_bbox()
        centroid = np.add(min_shape, max_shape) / 2
        centroid = [centroid[i] for i in self.dims.displayed]
        size = np.subtract(max_shape, min_shape)
        size = [size[i] for i in self.dims.displayed]
        corner = [min_shape[i] for i in self.dims.displayed]

        if self.dims.ndisplay == 2:
            # For a PanZoomCamera emit a 4-tuple of the viewbox
            corner = np.subtract(corner, np.multiply(0.05, size))[::-1]
            size = np.multiply(1.1, size)[::-1]
            rect = tuple(corner) + tuple(size)
            self.events.reset_view(viewbox=rect)
        else:
            # For an ArcballCamera emit the center and scale_factor
            center = centroid[::-1]
            scale_factor = 1.5 * np.mean(size)
            self.events.reset_view(center=center, scale_factor=scale_factor)

    def to_svg(self, file=None, view_box=None):
        """Convert the viewer state to an SVG. Non visible layers will be
        ignored.

        Parameters
        ----------
        file : path-like object, optional
            An object representing a file system path. A path-like object is
            either a str or bytes object representing a path, or an object
            implementing the `os.PathLike` protocol. If passed the svg will be
            written to this file
        view_box : 4-tuple, optional
            View box of SVG canvas to be generated specified as `min-x`,
            `min-y`, `width` and `height`. If not specified, calculated
            from the last two dimensions of the view.

        Returns
        ----------
        svg : string
            SVG representation of the currently viewed layers.
        """

        if view_box is None:
            min_shape, max_shape = self._calc_bbox()
            min_shape = min_shape[-2:]
            max_shape = max_shape[-2:]
            shape = np.subtract(max_shape, min_shape)
        else:
            shape = view_box[2:]
            min_shape = view_box[:2]

        props = {
            'xmlns': 'http://www.w3.org/2000/svg',
            'xmlns:xlink': 'http://www.w3.org/1999/xlink',
        }

        xml = Element(
            'svg',
            height=f'{shape[0]}',
            width=f'{shape[1]}',
            version='1.1',
            **props,
        )

        transform = f'translate({-min_shape[1]} {-min_shape[0]})'
        xml_transform = Element('g', transform=transform)

        for layer in self.layers:
            if layer.visible:
                xml_list = layer.to_xml_list()
                for x in xml_list:
                    xml_transform.append(x)
        xml.append(xml_transform)

        svg = (
            '<?xml version=\"1.0\" standalone=\"no\"?>\n'
            + '<!DOCTYPE svg PUBLIC \"-//W3C//DTD SVG 1.1//EN\"\n'
            + '\"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd\">\n'
            + tostring(xml, encoding='unicode', method='xml')
        )

        if file:
            # Save svg to file
            with open(file, 'w') as f:
                f.write(svg)

        return svg

    def add_layer(self, layer):
        """Add a layer to the viewer.

        Parameters
        ----------
        layer : Layer
            Layer to add.
        """
        layer.events.select.connect(self._update_active_layer)
        layer.events.deselect.connect(self._update_active_layer)
        layer.events.status.connect(self._update_status)
        layer.events.help.connect(self._update_help)
        layer.events.interactive.connect(self._update_interactive)
        layer.events.cursor.connect(self._update_cursor)
        layer.events.cursor_size.connect(self._update_cursor_size)
        layer.events.data.connect(self._on_layers_change)
        layer.dims.events.ndisplay.connect(self._on_layers_change)
        layer.dims.events.order.connect(self._on_layers_change)
        layer.dims.events.range.connect(self._on_layers_change)
        self.layers.append(layer)
        self._update_layers(layers=[layer])

        if len(self.layers) == 1:
            self.reset_view()

    def add_image(
        self,
        data,
        *,
        multichannel=None,
        colormap='gray',
        contrast_limits=None,
        interpolation='nearest',
        rendering='mip',
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=1,
        blending='translucent',
        visible=True,
    ):
        """Add an image layer to the layers list.

        Parameters
        ----------
        data : array
            Image data. Can be N dimensional. If the last dimension has length
            3 or 4 can be interpreted as RGB or RGBA if multichannel is `True`.
        multichannel : bool
            Whether the image is multichannel RGB or RGBA if multichannel. If
            not specified by user and the last dimension of the data has length
            3 or 4 it will be set as `True`. If `False` the image is
            interpreted as a luminance image.
        colormap : str, vispy.Color.Colormap, tuple, dict
            Colormap to use for luminance images. If a string must be the name
            of a supported colormap from vispy or matplotlib. If a tuple the
            first value must be a string to assign as a name to a colormap and
            the second item must be a Colormap. If a dict the key must be a
            string to assign as a name to a colormap and the value must be a
            Colormap.
        contrast_limits : list (2,)
            Color limits to be used for determining the colormap bounds for
            luminance images. If not passed is calculated as the min and max of
            the image.
        interpolation : str
            Interpolation mode used by vispy. Must be one of our supported
            modes.
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

        Returns
        -------
        layer : :class:`napari.layers.Image`
            The newly-created image layer.
        """
        layer = layers.Image(
            data,
            multichannel=multichannel,
            colormap=colormap,
            contrast_limits=contrast_limits,
            interpolation=interpolation,
            rendering=rendering,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_pyramid(self, data, *args, **kwargs):
        """Add an image pyramid layer to the layers list.

        Parameters
        ----------
        data : list
            Pyramid data. List of array like image date. Each image can be N
            dimensional. If the last dimensions of the images have length 3
            or 4 they can be interpreted as RGB or RGBA if multichannel is
            `True`.
        multichannel : bool
            Whether the image is multichannel RGB or RGBA if multichannel. If
            not specified by user and the last dimension of the data has length
            3 or 4 it will be set as `True`. If `False` the image is
            interpreted as a luminance image.
        colormap : str, vispy.Color.Colormap, tuple, dict
            Colormap to use for luminance images. If a string must be the name
            of a supported colormap from vispy or matplotlib. If a tuple the
            first value must be a string to assign as a name to a colormap and
            the second item must be a Colormap. If a dict the key must be a
            string to assign as a name to a colormap and the value must be a
            Colormap.
        contrast_limits : list (2,)
            Color limits to be used for determining the colormap bounds for
            luminance images. If not passed is calculated as the min and max of
            the image.
        interpolation : str
            Interpolation mode used by vispy. Must be one of our supported
            modes.
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

        Returns
        -------
        layer : :class:`napari.layers.Pyramid`
            The newly-created pyramid layer.
        """
        layer = layers.Pyramid(data, *args, **kwargs)
        self.add_layer(layer)
        return layer

    def add_points(
        self,
        data,
        *,
        symbol='o',
        size=10,
        edge_width=1,
        edge_color='black',
        face_color='white',
        n_dimensional=False,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=1,
        blending='translucent',
        visible=True,
    ):
        """Add a points layer to the layers list.

        Parameters
        ----------
        data : array (N, D)
            Coordinates for N points in D dimensions.
        symbol : str
            Symbol to be used for the point markers. Must be one of the
            following: arrow, clobber, cross, diamond, disc, hbar, ring,
            square, star, tailed_arrow, triangle_down, triangle_up, vbar, x.
        size : float, array
            Size of the point marker. If given as a scalar, all points are made
            the same size. If given as an array, size must be the same
            broadcastable to the same shape as the data.
        edge_width : float
            Width of the symbol edge in pixels.
        edge_color : str
            Color of the point marker border.
        face_color : str
            Color of the point marker body.
        n_dimensional : bool
            If True, renders points not just in central plane but also in all
            n-dimensions according to specified point marker size.
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

        Returns
        -------
        layer : :class:`napari.layers.Points`
            The newly-created points layer.

        Notes
        -----
        See vispy's marker visual docs for more details:
        http://api.vispy.org/en/latest/visuals.html#vispy.visuals.MarkersVisual
        """
        layer = layers.Points(
            data,
            symbol=symbol,
            size=size,
            edge_width=edge_width,
            edge_color=edge_color,
            face_color=face_color,
            n_dimensional=n_dimensional,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_labels(
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
        """Add a labels (or segmentation) layer to the layers list.

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

        Returns
        -------
        layer : :class:`napari.layers.Labels`
            The newly-created labels layer.
        """
        layer = layers.Labels(
            data,
            num_colors=num_colors,
            seed=seed,
            n_dimensional=n_dimensional,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_shapes(
        self,
        data,
        *,
        shape_type='rectangle',
        edge_width=1,
        edge_color='black',
        face_color='white',
        z_index=0,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=0.7,
        blending='translucent',
        visible=True,
    ):
        """Add a shapes layer to the layers list.

        Parameters
        ----------
        data : list or array
            List of shape data, where each element is an (N, D) array of the
            N vertices of a shape in D dimensions. Can be an 3-dimensional
            array if each shape has the same number of vertices.
        shape_type : string or list
            String of shape shape_type, must be one of "{'line', 'rectangle',
            'ellipse', 'path', 'polygon'}". If a list is supplied it must be
            the same length as the length of `data` and each element will be
            applied to each shape otherwise the same value will be used for all
            shapes.
        edge_width : float or list
            Thickness of lines and edges. If a list is supplied it must be the
            same length as the length of `data` and each element will be
            applied to each shape otherwise the same value will be used for all
            shapes.
        edge_color : str or list
            If string can be any color name recognized by vispy or hex value if
            starting with `#`. If array-like must be 1-dimensional array with 3
            or 4 elements. If a list is supplied it must be the same length as
            the length of `data` and each element will be applied to each shape
            otherwise the same value will be used for all shapes.
        face_color : str or list
            If string can be any color name recognized by vispy or hex value if
            starting with `#`. If array-like must be 1-dimensional array with 3
            or 4 elements. If a list is supplied it must be the same length as
            the length of `data` and each element will be applied to each shape
            otherwise the same value will be used for all shapes.
        z_index : int or list
            Specifier of z order priority. Shapes with higher z order are
            displayed ontop of others. If a list is supplied it must be the
            same length as the length of `data` and each element will be
            applied to each shape otherwise the same value will be used for all
            shapes.
        name : str
            Name of the layer.
        metadata : dict
            Layer metadata.
        scale : tuple of float
            Scale factors for the layer.
        translate : tuple of float
            Translation values for the layer.
        opacity : float or list
            Opacity of the layer visual, between 0.0 and 1.0.
        blending : str
            One of a list of preset blending modes that determines how RGB and
            alpha values of the layer visual get mixed. Allowed values are
            {'opaque', 'translucent', and 'additive'}.
        visible : bool
            Whether the layer visual is currently being displayed.

        Returns
        -------
        layer : :class:`napari.layers.Shapes`
            The newly-created shapes layer.
        """
        layer = layers.Shapes(
            data,
            shape_type=shape_type,
            edge_width=edge_width,
            edge_color=edge_color,
            face_color=face_color,
            z_index=z_index,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def add_vectors(
        self,
        data,
        *,
        edge_width=1,
        edge_color='red',
        length=1,
        name=None,
        metadata=None,
        scale=None,
        translate=None,
        opacity=0.7,
        blending='translucent',
        visible=True,
    ):
        """Add a vectors layer to the layers list.

        Parameters
        ----------
        data : (N, 2, D) or (N1, N2, ..., ND, D) array
            An (N, 2, D) array is interpreted as "coordinate-like" data and a
            list of N vectors with start point and projections of the vector in
            D dimensions. An (N1, N2, ..., ND, D) array is interpreted as
            "image-like" data where there is a length D vector of the
            projections at each pixel.
        edge_width : float
            Width for all vectors in pixels.
        length : float
             Multiplicative factor on projections for length of all vectors.
        edge_color : str
            Edge color of all the vectors.
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

        Returns
        -------
        layer : :class:`napari.layers.Vectors`
            The newly-created vectors layer.
        """
        layer = layers.Vectors(
            data,
            edge_width=edge_width,
            edge_color=edge_color,
            length=length,
            name=name,
            metadata=metadata,
            scale=scale,
            translate=translate,
            opacity=opacity,
            blending=blending,
            visible=visible,
        )
        self.add_layer(layer)
        return layer

    def _new_points(self):
        if self.dims.ndim == 0:
            ndim = 2
        else:
            ndim = self.dims.ndim
        self.add_points(np.empty((0, ndim)))

    def _new_shapes(self):
        if self.dims.ndim == 0:
            ndim = 2
        else:
            ndim = self.dims.ndim
        layer = self.add_shapes(np.empty((0, 0, ndim)))

    def _new_labels(self):
        if self.dims.ndim == 0:
            dims = (512, 512)
        else:
            dims = self._calc_bbox()[1]
            dims = [np.ceil(d).astype('int') if d > 0 else 1 for d in dims]
            if len(dims) < 1:
                dims = (512, 512)
        empty_labels = np.zeros(dims, dtype=int)
        self.add_labels(empty_labels)

    def _update_layers(self, layers=None):
        """Updates the contained layers.

        Parameters
        ----------
        layers : list of napari.layers.Layer, optional
            List of layers to update. If none provided updates all.
        """
        layers = layers or self.layers

        for layer in layers:
            # adjust the order of the global dims based on the number of
            # dimensions that a layer has - for example a global order of
            # [2, 1, 0, 3] -> [0, 1] for a layer that only has two dimesnions
            # or -> [1, 0, 2] for a layer with three as that corresponds to
            # the relative order of the last two and three dimensions
            # respectively
            offset = self.dims.ndim - layer.dims.ndim
            order = np.array(self.dims.order)
            if offset <= 0:
                order = list(range(-offset)) + list(order - offset)
            else:
                order = list(order[order >= offset] - offset)
            layer.dims.order = order
            layer.dims.ndisplay = self.dims.ndisplay

            # Update the point values of the layers for the dimensions that
            # the layer has
            for axis in range(layer.dims.ndim):
                point = self.dims.point[axis + offset]
                layer.dims.set_point(axis, point)

    def _update_active_layer(self, event):
        """Set the active layer by iterating over the layers list and
        finding the first selected layer. If multiple layers are selected the
        iteration stops and the active layer is set to be None

        Parameters
        ----------
        event : Event
            No Event parameters are used
        """
        # iteration goes backwards to find top most selected layer if any
        # if multiple layers are selected sets the active layer to None
        active_layer = None
        for layer in self.layers:
            if active_layer is None and layer.selected:
                active_layer = layer
            elif active_layer is not None and layer.selected:
                active_layer = None
                break

        if active_layer is None:
            self.status = 'Ready'
            self.help = ''
            self.cursor = 'standard'
            self.interactive = True
            self.active_layer = None
        else:
            self.status = active_layer.status
            self.help = active_layer.help
            self.cursor = active_layer.cursor
            self.interactive = active_layer.interactive
            self.active_layer = active_layer

    def _on_layers_change(self, event):
        layer_range = self._calc_layers_ranges()
        self.dims.ndim = len(layer_range)
        for i, r in enumerate(layer_range):
            self.dims.set_range(i, r)

    def _calc_layers_ranges(self):
        """Calculates the range along each axis from all present layers.
        """

        ndims = self._calc_layers_num_dims()
        ranges = [(inf, -inf, inf)] * ndims

        for layer in self.layers:
            layer_range = layer.dims.range[::-1]
            ranges = [
                (min(a, b), max(c, d), min(e, f))
                for (a, c, e), (b, d, f) in zip_longest(
                    ranges, layer_range, fillvalue=(inf, -inf, inf)
                )
            ]

        return ranges[::-1]

    def _calc_bbox(self):
        """Calculates the bounding box of all displayed layers.
        This assumes that all layers are stacked.
        """

        min_shape = []
        max_shape = []
        for min, max, step in self._calc_layers_ranges():
            min_shape.append(min)
            max_shape.append(max)
        if len(min_shape) == 0:
            min_shape = [0] * self.dims.ndim
            max_shape = [1] * self.dims.ndim

        return min_shape, max_shape

    def _calc_layers_num_dims(self):
        """Calculates the number of maximum dimensions in the contained images.
        """
        max_dims = 0
        for layer in self.layers:
            dims = layer.ndim
            if dims > max_dims:
                max_dims = dims

        return max_dims

    def _update_status(self, event):
        """Set the viewer status with the `event.status` string."""
        self.status = event.status

    def _update_help(self, event):
        """Set the viewer help with the `event.help` string."""
        self.help = event.help

    def _update_interactive(self, event):
        """Set the viewer interactivity with the `event.interactive` bool."""
        self.interactive = event.interactive

    def _update_cursor(self, event):
        """Set the viewer cursor with the `event.cursor` string."""
        self.cursor = event.cursor

    def _update_cursor_size(self, event):
        """Set the viewer cursor_size with the `event.cursor_size` int."""
        self.cursor_size = event.cursor_size
