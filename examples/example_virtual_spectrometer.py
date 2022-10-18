## Example 1, connect to a virtual spectrometer

from colour import MultiSpectralDistributions
from matplotlib import pyplot as plt

from specio import SpecRadiometer

from colour.plotting import plot_multi_sds

meter = SpecRadiometer()
m = meter.measure()

measurements = [meter.measure().spd for idx in range(0, 100)]

measurements = MultiSpectralDistributions(measurements)
settings = dict(standalone=False, legend=False)
(fig, ax) = plot_multi_sds(measurements, **settings)

plt.show()
pass
