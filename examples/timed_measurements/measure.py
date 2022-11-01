import time
from specio.ColorimetryResearch import CRSpectrometer
from specio.ColorimetryResearch.CR_Definitions import MeasurementSpeed
from datetime import datetime, timedelta
from specio.fileio import save_measurements

cr = CRSpectrometer(speed=MeasurementSpeed.SLOW)

measurements = []

last_save = datetime.now()
last_measurement = datetime.min

measure_interval = timedelta(minutes=1)  # Measures at most once per interval

while True:
    try:
        if (due := last_measurement + measure_interval) > (now := datetime.now()):
            time.sleep((due - now).total_seconds())

        last_measurement = datetime.now()
        measurements.append(cr.measure())

        print(measurements[-1])
    except Exception as e:
        last_measurement = datetime.min
        print(e)

    if datetime.now() - last_save > timedelta(minutes=20):
        last_save = datetime.now()
        save_measurements(
            "data/example_data_file",
            measurements,
        )
