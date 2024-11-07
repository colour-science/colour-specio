# %%
from colour import SpectralShape, sd_zeros
from specio import colorimetry_research as cr
from specio.common.spectrometers import SPDMeasurement

spectrometer = cr.CRSpectrometer.discover()

spectrometer.average_samples = 2  # Average 3 samples
spectrometer.measurement_speed = spectrometer.MeasurementSpeed.FAST_2X

print(spectrometer.measure())

# %% with error handling
try:
    measurement = spectrometer.measure()
except cr.CommandError as e:
    if (
        e.response.code is cr.ResponseCode.LIGHT_INTENSITY_UNMEASURABLE
        or e.response.code is cr.ResponseCode.LIGHT_INTENSITY_TOO_LOW
    ):
        # Make a fake measurement
        shape = SpectralShape(380, 780, 1)
        measurement = SPDMeasurement(
            sd_zeros(shape=shape),
            exposure=0,
            spectrometer_id="My Project Fake Measurement",
        )
    else:
        raise

print(measurement)
