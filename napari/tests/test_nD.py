import numpy as np

from napari import Viewer


def test_nD_image(qtbot):
    """Test adding nD image."""
    viewer = Viewer()
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    data = np.random.random((6, 10, 15))
    viewer.add_image(data)
    assert np.all(viewer.layers[0].data == data)

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2

    assert viewer.dims.ndim == 3
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Flip dims order displayed
    viewer.dims.order = [0, 2, 1]
    assert viewer.dims.order == [0, 2, 1]

    # Flip dims order including non-displayed
    viewer.dims.order = [1, 0, 2]
    assert viewer.dims.order == [1, 0, 2]

    # Close the viewer
    viewer.window.close()


def test_nD_volume(qtbot):
    """Test adding nD volume."""
    viewer = Viewer()
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    data = np.random.random((6, 10, 15, 20))
    viewer.add_image(data)
    viewer.dims.ndisplay = 3
    assert np.all(viewer.layers[0].data == data)

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2

    assert viewer.dims.ndim == 4
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Flip dims order displayed
    viewer.dims.order = [0, 2, 1, 3]
    assert viewer.dims.order == [0, 2, 1, 3]

    # Flip dims order including non-displayed
    viewer.dims.order = [1, 0, 2, 3]
    assert viewer.dims.order == [1, 0, 2, 3]

    # Close the viewer
    viewer.window.close()


def test_nD_volume_launch(qtbot):
    """Test adding nD volume when viewer launched with 3D."""
    viewer = Viewer(ndisplay=3)
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    shape = (6, 10, 15, 20)
    data = np.random.random(shape)
    viewer.add_image(data)
    assert np.all(viewer.layers[0].data == data)
    assert viewer.layers[0]._data_view.shape == shape[-3:]

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2
    assert viewer.dims.ndim == 4
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Close the viewer
    viewer.window.close()


def test_nD_volume_launch_order(qtbot):
    """Test adding nD volume when viewer launched with 3D."""
    order = [1, 0, 2, 3]
    viewer = Viewer(ndisplay=3, order=order)
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    shape = (6, 10, 15, 20)
    data = np.random.random(shape)
    viewer.add_image(data)
    assert np.all(viewer.layers[0].data == data)
    assert viewer.layers[0]._data_view.shape == tuple(
        shape[o] for o in order[-3:]
    )

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2
    assert viewer.dims.ndim == 4
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1
    assert viewer.dims.order == order

    # Close the viewer
    viewer.window.close()


def test_nD_pyramid(qtbot):
    """Test adding nD image pyramid."""
    viewer = Viewer()
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    shapes = [(8, 40, 20), (4, 20, 10), (4, 10, 5)]
    np.random.seed(0)
    data = [np.random.random(s) for s in shapes]
    viewer.add_pyramid(data)
    assert np.all(viewer.layers[0].data == data)

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2

    assert viewer.dims.ndim == 3
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Flip dims order displayed
    viewer.dims.order = [0, 2, 1]
    assert viewer.dims.order == [0, 2, 1]

    # Flip dims order including non-displayed
    viewer.dims.order = [1, 0, 2]
    assert viewer.dims.order == [1, 0, 2]

    # Close the viewer
    viewer.window.close()


def test_nD_labels(qtbot):
    """Test adding nD labels image."""
    viewer = Viewer()
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    data = np.random.randint(20, size=(6, 10, 15))
    viewer.add_labels(data)
    assert np.all(viewer.layers[0].data == data)

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2

    assert viewer.dims.ndim == 3
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Flip dims order displayed
    viewer.dims.order = [0, 2, 1]
    assert viewer.dims.order == [0, 2, 1]

    # Flip dims order including non-displayed
    viewer.dims.order = [1, 0, 2]
    assert viewer.dims.order == [1, 0, 2]

    # Close the viewer
    viewer.window.close()


def test_nD_points(qtbot):
    """Test adding nD points."""
    viewer = Viewer()
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    data = 20 * np.random.random((10, 3))
    viewer.add_points(data)
    assert np.all(viewer.layers[0].data == data)

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2

    assert viewer.dims.ndim == 3
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Flip dims order displayed
    viewer.dims.order = [0, 2, 1]
    assert viewer.dims.order == [0, 2, 1]

    # Flip dims order including non-displayed
    viewer.dims.order = [1, 0, 2]
    assert viewer.dims.order == [1, 0, 2]

    # Close the viewer
    viewer.window.close()


def test_nD_vectors(qtbot):
    """Test adding nD vectors."""
    viewer = Viewer()
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    data = 20 * np.random.random((10, 2, 3))
    viewer.add_vectors(data)
    assert np.all(viewer.layers[0].data == data)

    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2

    assert viewer.dims.ndim == 3
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Flip dims order displayed
    viewer.dims.order = [0, 2, 1]
    assert viewer.dims.order == [0, 2, 1]

    # Flip dims order including non-displayed
    viewer.dims.order = [1, 0, 2]
    assert viewer.dims.order == [1, 0, 2]

    # Close the viewer
    viewer.window.close()


def test_nD_shapes(qtbot):
    """Test adding vectors."""
    viewer = Viewer()
    view = viewer.window.qt_viewer
    qtbot.addWidget(view)

    np.random.seed(0)
    # create one random rectangle per "plane"
    planes = np.tile(np.arange(10).reshape((10, 1, 1)), (1, 4, 1))
    corners = np.random.uniform(0, 10, size=(10, 4, 2))
    data = np.concatenate((planes, corners), axis=2)
    viewer.add_shapes(data)
    assert np.all(
        [np.all(ld == d) for ld, d in zip(viewer.layers[0].data, data)]
    )
    assert len(viewer.layers) == 1
    assert view.layers.vbox_layout.count() == 2 * len(viewer.layers) + 2

    assert viewer.dims.ndim == 3
    assert view.dims.nsliders == viewer.dims.ndim
    assert np.sum(view.dims._displayed_sliders) == 1

    # Flip dims order displayed
    viewer.dims.order = [0, 2, 1]
    assert viewer.dims.order == [0, 2, 1]

    # Flip dims order including non-displayed
    viewer.dims.order = [1, 0, 2]
    assert viewer.dims.order == [1, 0, 2]

    # Close the viewer
    viewer.window.close()
