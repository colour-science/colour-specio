from datetime import datetime

import numpy as np
from colour import sd_multi_leds

from specio.measurement import Measurement, RawMeasurement

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"


class SpecRadiometer:
    def __init__(
        self,
        model: str = "Virtual Spectrometer",
        manufacturer: str = "Specio",
        serial_num: str | None = None,
    ):
        self.manufacturer: str = manufacturer
        self._model: str = model
        self._serial_number: str | None = serial_num

    @property
    def model(self):
        return self._model

    @property
    def serial_number(self):
        return self._serial_number

    @property
    def readable_id(self) -> str:
        return f"{self.model} - {self.serial_number}"

    def measure(self) -> Measurement:
        _rm = self._raw_measure()
        _measurement = Measurement(_rm)
        return _measurement

    def _raw_measure(self) -> RawMeasurement:
        peaks = np.random.randint([460, 510, 600], [480, 570, 690], 3)
        widths = np.random.randint(40, 80, 3)
        powers = np.random.randint(10, 40, 3) / 1000
        spd = sd_multi_leds(
            peak_wavelengths=peaks, fwhm=widths, peak_power_ratios=powers
        )

        _measurement = RawMeasurement(
            spd=spd,
            exposure=1,
            spectrometer_id="Virtual Spectrometer",
        )
        return _measurement


if __name__ == "__main__":
    t = SpecRadiometer()
    m = t.measure()
    print(m)
