## Example 2, connect to CRSpectrometer
from collections.abc import Mapping

from colour.plotting import plot_single_sd

from specio.ColorimetryResearch import CRSpectrometer, MeasurementSpeed
from specio.measurement import SPDMeasurement

# Auto Discovery supported on MacOS
meter = CRSpectrometer.discover()
meter.speed = MeasurementSpeed.FAST_2X
# meter = CRSpectrometer(device="COM4", speed=MeasurementSpeed.FAST_2X)

# Initiate Measurement
m: SPDMeasurement = meter.measure()

print(m)
# Spectral Measurement - Model.CR300 - A00237:
#     time: 2022-10-18 11:17:38.803674
#     XYZ: [21.29 22.72 14.37]
#     CCT: 4520 ± 0.01073
#     Dominant WL: 571.0

settings: Mapping = {"legend": False}
(fig, ax) = plot_single_sd(m.spd, **settings)
