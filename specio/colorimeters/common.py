"""
Define basic spectrometer interfaces
"""

import textwrap
from abc import ABC, abstractmethod
from ctypes import ArgumentError
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cached_property
from typing import final

import numpy as np
from colour import sd_multi_leds
from colour.colorimetry.dominant import (
    colorimetric_purity,
    dominant_wavelength,
)
from colour.colorimetry.tristimulus_values import sd_to_XYZ
from colour.models.cie_xyy import XYZ_to_xy
from colour.temperature.ohno2013 import XYZ_to_CCT_Ohno2013

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = (
    "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
)
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"


@dataclass
class RawColorimeterMeasurement:
    XYZ: np.ndarray
    exposure: float
    device_id: str


class ColorimeterMeasurement:
    def __init__(self, raw: RawColorimeterMeasurement):
        self.XYZ = raw.XYZ
        self.exposure = raw.exposure
        self.device_id = raw.device_id

        cct = XYZ_to_CCT_Ohno2013(self.XYZ)
        self.cct = cct[0]
        self.duv = cct[1]

        self.xy = XYZ_to_xy(self.XYZ)
        self.dominant_wl = float(
            dominant_wavelength(self.xy, [1 / 3, 1 / 3])[0]
        )
        self.purity = colorimetric_purity(self.xy, (1 / 3, 1 / 3))
        self.time = datetime.now(tz=UTC)

    def __str__(self) -> str:
        """
        Return printable string with interesting data for an observant reader.

        Returns
        -------
        str
        """
        return textwrap.dedent(
            f"""
            Colorimeter Measurement - {self.device_id}:
                time: {self.time}
                XYZ: {np.array2string(self.XYZ, formatter={'float_kind':lambda x: "%.2f" % x})}
                xy: {np.array2string(self.xy, formatter={'float_kind':lambda x: "%.4f" % x})}
                CCT: {self.cct:.0f} ± {self.duv:.5f}
                Dominant WL: {self.dominant_wl:.1f}
                Exposure: {self.exposure:.3f}
            """  # noqa: E501
        )


class Colorimeter(ABC):
    """
    Base class for spectroradiometers. Defines the minimum interface needed
    by implementing classes to collect measurement values from a spectrometer.
    """

    @property
    @abstractmethod
    def serial_number(self) -> str:
        """The serial number or id for the specific connected spectrometer

        Returns
        -------
        str
        """

        ...

    @property
    @abstractmethod
    def manufacturer(self) -> str:
        """The device manufacturer name

        Returns
        -------
        str
        """

        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """The model name or identifier for the device

        Returns
        -------
        str
        """

        ...

    @abstractmethod
    def _raw_measure(self) -> RawColorimeterMeasurement:
        """Conduct remote triggering and RPC / serial interaction to collect
        the raw spectrometer data from the device.

        Returns
        -------
        RawMeasurement
            A simple dataclass with the required parameters to produce fully
            defined :class:`specio.measurement.Measurement`
        """

        ...

    @cached_property
    def readable_id(self) -> str:
        """Human readable spectrometer id. Defaults to "<MODEL> - <SERIAL>" if
        not set by the implementing class.

        Returns
        -------
        str
        """
        return f"{self.model} - {self.serial_number}"

    def measure(self, repetitions: int = 1) -> ColorimeterMeasurement:
        """Trigger and collect one measurement from the LED tile

        Returns
        -------
        Measurement
            A dataclass containing various convenience calculations from python
            colour-science and the raw SPD.
        """

        if repetitions < 1:
            ArgumentError("Repetitions must be greater than 1")

        _rm: list[RawColorimeterMeasurement] = []
        for _ in range(repetitions):
            _rm += [self._raw_measure()]

        if len(_rm) == 1:
            return ColorimeterMeasurement(_rm[0])

        XYZ = np.asarray([m.XYZ for m in _rm]).mean(axis=0)
        exposure = np.mean([m.exposure for m in _rm]).item()
        id = _rm[0].device_id

        return ColorimeterMeasurement(
            RawColorimeterMeasurement(XYZ=XYZ, exposure=exposure, device_id=id)
        )


@final
class VirtualColorimeter(Colorimeter):
    """
    Basic spectroradiometer interface. Implements a virtual spectrometer
    returning random colors for basic testing
    """

    def __init__(self):
        super().__init__()

    @property
    def manufacturer(self) -> str:
        """Return "specio" as the manufacturer of this virtual spectrometer

        Returns
        -------
        str
        """
        return "specio"

    @property
    def model(self):
        """The model name or model signature from the spectrometer.

        Returns
        -------
        str
        """
        return "Virtual Random Spectrometer"

    @property
    def serial_number(self):
        """The serial number of the spectrometer

        Returns
        -------
        str
        """
        return "0000-0000"

    def _raw_measure(self) -> RawColorimeterMeasurement:
        """Return a random SPD generated by combining three gaussian spectra

        Returns
        -------
        RawMeasurement
            A simple dataclass with the required parameters to produce fully
            defined :class:`specio.measurement.Measurement`
        """
        peaks = np.random.randint([460, 510, 600], [480, 570, 690], 3)
        widths = np.random.randint(40, 80, 3)
        powers = np.random.randint(10, 40, 3) / 1000
        spd = sd_multi_leds(
            peak_wavelengths=peaks,
            half_spectral_widths=widths / 2,
            peak_power_ratios=powers,
        )

        _measurement = RawColorimeterMeasurement(
            XYZ=sd_to_XYZ(spd, k=683),
            exposure=1,
            device_id="Virtual Spectrometer",
        )
        return _measurement


if __name__ == "__main__":
    c = VirtualColorimeter()
    print(c.measure())
    print()
