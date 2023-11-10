## Example 1, connect to a virtual spectrometer

from collections.abc import Mapping

from colour import MultiSpectralDistributions
from colour.plotting import plot_multi_sds
from matplotlib import pyplot as plt
from specio.spectrometers.common import VirtualSpectrometer

meter = VirtualSpectrometer()
m = meter.measure()

measurements = [meter.measure().spd for idx in range(100)]

measurements = MultiSpectralDistributions(measurements)
settings: Mapping = {"standalone": False, "legend": False}
(fig, ax) = plot_multi_sds(measurements, **settings)

plt.show()
