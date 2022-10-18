## Example 2, connect to CR300
from matplotlib import pyplot as plt

from specio.ColorimetryResearch import CR300, MeasurementSpeed
from colour.plotting import plot_single_sd
from specio.common import Measurement

# Auto Discovery supported on MacOS
meter = CR300(speed=MeasurementSpeed.FAST_2X)
# meter = CR300(device="COM4", speed=MeasurementSpeed.FAST_2X)

# Initiate Measurement
m: Measurement = meter.measure()

print(m)
# Spectral Measurement - Model.CR300 - A00237:
#     time: 2022-10-18 11:17:38.803674
#     XYZ: [21.29 22.72 14.37]
#     CCT: 4520 ± 0.01073
#     Dominant WL: 571.0

settings = dict(legend=False)
(fig, ax) = plot_single_sd(m.spd, **settings)
