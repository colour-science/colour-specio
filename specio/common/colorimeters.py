"""
Define basic spectrometer interfaces
"""

import textwrap
from abc import ABC, abstractmethod
from ctypes import ArgumentError
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Self

import numpy as np
from colour.colorimetry.dominant import (
    colorimetric_purity,
    dominant_wavelength,
)
from colour.hints import ArrayLike
from colour.models.cie_xyy import XYZ_to_xy
from colour.temperature.ohno2013 import XYZ_to_CCT_Ohno2013

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "Colorimeter",
    "ColorimeterMeasurement",
    "RawColorimeterMeasurement",
]


@dataclass
class RawColorimeterMeasurement:
    XYZ: np.ndarray
    exposure: float
    device_id: str


class ColorimeterMeasurement:
    @classmethod
    def FromRaw(cls, raw: RawColorimeterMeasurement) -> Self:
        return cls(raw.XYZ, raw.exposure, raw.device_id)

    def __init__(
        self,
        XYZ: ArrayLike,
        exposure: float,
        device_id: str,
        no_compute: bool = False,
    ):
        XYZ = np.asarray(XYZ)
        if XYZ.size != (3,):
            RuntimeError("XYZ must be size (3,)")

        self.XYZ = XYZ
        self.exposure = exposure
        self.device_id = device_id

        if not no_compute:
            cct = XYZ_to_CCT_Ohno2013(self.XYZ)
            self.cct: float = cct[0]
            self.duv: float = cct[1]

            self.xy = XYZ_to_xy(self.XYZ)
            self.dominant_wl: float = float(
                dominant_wavelength(self.xy, [1 / 3, 1 / 3])[0]
            )
            self.purity: float = colorimetric_purity(self.xy, (1 / 3, 1 / 3))  # type: ignore
            self.time = datetime.now().astimezone()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ColorimeterMeasurement):
            keys = [
                "XYZ",
                "exposure",
                "device_id",
                "cct",
                "duv",
                "xy",
                "dominant_wl",
                "purity",
                "time",
            ]
            bools = [np.all(getattr(self, k) == getattr(other, k)) for k in keys]
            return all(bools)
        return False

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
                Dominant WL: {self.dominant_wl:.1f} @ {self.purity * 100:.1f}%
                Exposure: {self.exposure:.3f}
            """
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

    @cached_property
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
            defined :class:`specio.spectrometers.common.Measurement`
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
            return ColorimeterMeasurement.FromRaw(_rm[0])

        XYZ = np.asarray([m.XYZ for m in _rm]).mean(axis=0)
        exposure = np.mean([m.exposure for m in _rm]).item()
        id = _rm[0].device_id

        return ColorimeterMeasurement.FromRaw(
            RawColorimeterMeasurement(XYZ=XYZ, exposure=exposure, device_id=id)
        )


