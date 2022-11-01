from specio.ColorimetryResearch import CRSpectrometer
from specio.ColorimetryResearch.CR_Definitions import MeasurementSpeed
from datetime import datetime, timedelta
from specio.fileio import save_measurements

cr = CR300(speed=MeasurementSpeed.SLOW)

measurements = []

last_save = datetime.now()
while True:
    try:
        measurements.append(cr.measure())
        print(measurements[-1])
    except Exception as e:
        print(e)

    if datetime.now() - last_save > timedelta(minutes=20):
        save_measurements(
            "data/443_north_window" + datetime.now().strftime("%Y_%m_%d"), measurements
        )
