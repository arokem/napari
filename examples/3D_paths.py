"""
Display two vectors layers ontop of a 4-D image layer. One of the vectors
layers is 3D and "sliced" with a different set of vectors appearing on
different 3D slices. Another is 2D and "broadcast" with the same vectors
apprearing on each slice.
"""

import numpy as np
from skimage import data
import napari
import dipy.data as dpd

bundles = dpd.read_bundles_2_subjects()
cst = bundles['cst.right']

with napari.gui_qt():
    blobs = data.binary_blobs(
                length=128, blob_size_fraction=0.05, n_dim=3, volume_fraction=0.05
            )

    viewer = napari.view(blobs.astype(float))

    # sample vector coord-like data
    # path = np.array([np.array([[0, 0, 0], [0, 10, 10], [0, 5, 15], [20, 5, 15],
    #     [56, 70, 21], [127, 127, 127]]),
    #     np.array([[0, 0, 0], [0, 10, 10], [0, 5, 15], [0, 5, 15],
    #         [0, 70, 21], [0, 127, 127]])])

    print('Path', len(cst))
    layer = viewer.add_shapes(
        cst, shape_type='path', edge_width=4, edge_color=['red', 'blue']
    )

    #viewer.dims.ndisplay = 3
