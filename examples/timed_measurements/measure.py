import time
from datetime import datetime, timedelta

import specio.spectrometers.colorimetry_research as cr

meter = cr.CRSpectrometer.discover()
meter.measurement_speed = cr.MeasurementSpeed.SLOW

measurements = []

last_save = datetime.min
last_measurement = datetime.min

measure_interval = timedelta(minutes=1)  # Measures at most once per interval

file_name = "data/443_north_window_" + datetime.now().strftime(
    "%Y_%m_%d_%H_%M"
)

while True:
    try:
        if (due := last_measurement + measure_interval) > (
            now := datetime.now()
        ):
            time.sleep((due - now).total_seconds())

        last_measurement = datetime.now()
        measurements.append(meter.measure())

        print(measurements[-1])
    except Exception as e:
        last_measurement = datetime.min
        print(e)

    if datetime.now() - timedelta(minutes=20) > last_save:
        last_save = datetime.now()
        save_measurements(
            file_name,
            measurements=measurements,
            notes=MeasurementList_Notes(
                author="Tucker Downs",
                location="443",
                notes="Direct Sky Measurement",
            ),
        )
