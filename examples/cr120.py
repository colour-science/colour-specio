# %%
from specio import colorimetry_research as cr

colorimeter = cr.CRColorimeter.discover()

colorimeter.average_samples = 2  # Average 3 samples

print(colorimeter.measure())

# %% with error handling

from colour import SpectralShape
from specio.common.colorimeters import ColorimeterMeasurement

try:
    measurement = colorimeter.measure()
except cr.CommandError as e:
    if (
        e.response.code is cr.ResponseCode.LIGHT_INTENSITY_UNMEASURABLE
        or e.response.code is cr.ResponseCode.LIGHT_INTENSITY_TOO_LOW
    ):
        # Make a fake measurement
        shape = SpectralShape(380, 780, 1)
        measurement = ColorimeterMeasurement(
            XYZ=(0, 0, 0),
            exposure=0,
            device_id="My Project Fake Measurement",
        )
    else:
        raise

print(measurement)
