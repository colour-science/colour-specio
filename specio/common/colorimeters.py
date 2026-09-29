"""
Define basic colorimeter interfaces
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Self

import numpy as np
from colour.hints import ArrayLike
from colour.temperature.ohno2013 import XYZ_to_CCT_Ohno2013

from ._measurements_shared import (
    BaseMeasurement,
    compute_color_properties,
    validate_repetitions,
)

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
    """
    Raw colorimeter measurement data from hardware before color calculations.

    Contains the fundamental measurement data captured directly from colorimeter
    hardware, including XYZ tristimulus values, exposure settings, and device
    identification.

    Parameters
    ----------
    XYZ : np.ndarray
        CIE 1931 XYZ tristimulus values from the measurement.
    exposure : float
        Exposure time or integration time used for the measurement.
    device_id : str
        Unique identifier for the measuring device.
    """

    XYZ: np.ndarray
    exposure: float
    device_id: str


class ColorimeterMeasurement(BaseMeasurement):
    @classmethod
    def FromRaw(cls, raw: RawColorimeterMeasurement) -> Self:
        """
        Create a ColorimeterMeasurement from raw measurement data.

        Parameters
        ----------
        raw : RawColorimeterMeasurement
            Raw measurement data from the colorimeter hardware.

        Returns
        -------
        ColorimeterMeasurement
            Processed measurement with calculated color properties.
        """
        return cls(raw.XYZ, raw.exposure, raw.device_id)

    def __init__(
        self,
        XYZ: ArrayLike,
        exposure: float,
        device_id: str,
        no_compute: bool = False,
    ):
        """
        Initialize colorimeter measurement with computed color properties.

        Parameters
        ----------
        XYZ : ArrayLike
            CIE 1931 XYZ tristimulus values as a 3-element array.
        exposure : float
            Exposure time or integration time used for the measurement.
        device_id : str
            Unique identifier for the measuring device.
        no_compute : bool, optional
            If True, skip calculation of derived color properties (CCT, xy, etc.).
            Default is False.

        Raises
        ------
        RuntimeError
            If XYZ array is not size 3.
        """
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

            # Use shared color property computation
            color_props = compute_color_properties(self.XYZ)
            self.xy = color_props["xy"]
            self.dominant_wl: float = color_props["dominant_wl"]
            self.purity: float = color_props["purity"]
            self.time = color_props["time"]

    def _get_comparison_keys(self) -> list[str]:
        """
        Get list of attribute names to use for equality comparison.

        Returns
        -------
        list[str]
            List of attribute names for comparison.
        """
        return [
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

    def __str__(self) -> str:
        """
        Return printable string with interesting data for an observant reader.

        Returns
        -------
        str
        """
        return self._format_measurement_string("Colorimeter", self.device_id)


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

        validate_repetitions(repetitions)

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
