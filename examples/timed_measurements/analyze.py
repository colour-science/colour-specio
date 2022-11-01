from matplotlib import pyplot as plt
import numpy as np

from colour import (
    UCS_to_uv,
    XYZ_to_UCS,
)

from colour.plotting import (
    plot_planckian_locus_in_chromaticity_diagram_CIE1960UCS,
)

from specio.fileio import load_measurements

measurements = load_measurements("data\\example_data_file")
measurements = measurements.measurements


XYZ = np.array([m.XYZ for m in measurements])
xy = UCS_to_uv(XYZ_to_UCS(XYZ))

# Plotting
fig, ax = plot_planckian_locus_in_chromaticity_diagram_CIE1960UCS("", standalone=False)
ax.plot(xy[:, 0], xy[:, 1], markersize=4, color=[0, 0, 0], marker=".", linestyle="")

plt.show()
