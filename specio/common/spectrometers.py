"""
Define basic spectrometer interfaces
"""

import textwrap
from abc import ABC, abstractmethod
from ctypes import ArgumentError
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any, Self

import numpy as np
from colour import SpectralDistribution
from colour.colorimetry.dominant import (
    colorimetric_purity,
    dominant_wavelength,
)
from colour.colorimetry.tristimulus_values import sd_to_XYZ
from colour.models.cie_ucs import xy_to_UCS_uv
from colour.models.cie_xyy import XYZ_to_xy
from colour.temperature import uv_to_CCT

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "RawSPDMeasurement",
    "SPDMeasurement",
    "SpecRadiometer",
]


@dataclass
class RawSPDMeasurement:
    """
    A measurement only containing the bare minimum amount of collected data.
    Expected to be further transformed into `specio.spectrometers.common.Measurement`.
    """

    spd: SpectralDistribution
    exposure: float
    spectrometer_id: str
    anc_data: Any = None


class SPDMeasurement:
    """
    The basic measurement structure for specio. It contains
    `colour.SpectralDistribution` and several convenience calculations. It an
    also be converted to a readable string for logging.
    """

    @classmethod
    def FromRaw(cls, raw: RawSPDMeasurement) -> Self:
        """
        Create an SPDMeasurement from raw spectrometer measurement data.

        Parameters
        ----------
        raw : RawSPDMeasurement
            Raw measurement data containing spectral power distribution and metadata.

        Returns
        -------
        SPDMeasurement
            Processed measurement with calculated color properties.
        """
        return cls(
            spd=raw.spd,
            exposure=raw.exposure,
            spectrometer_id=raw.spectrometer_id,
            ancillary=raw.anc_data,
        )

    def __init__(
        self,
        spd: SpectralDistribution,
        exposure: float,
        spectrometer_id: str,
        ancillary: Any = None,
        no_compute: bool = False,
    ):
        """
        Initialize spectral measurement with computed color properties.

        Parameters
        ----------
        spd : SpectralDistribution
            Spectral power distribution data from the measurement.
        exposure : float
            Exposure time or integration time used for the measurement.
        spectrometer_id : str
            Unique identifier for the measuring spectrometer.
        ancillary : Any, optional
            Additional metadata or ancillary data from the measurement.
        no_compute : bool, optional
            If True, skip calculation of derived color properties (XYZ, CCT, etc.).
            Default is False.
        """
        self.spd = spd
        self.exposure = exposure
        self.spectrometer_id = spectrometer_id
        self.anc_data = ancillary

        method = "ASTM E308"
        if self.spd.shape.interval not in [1, 5, 10, 20]:
            method = "Integration"

        if not no_compute:
            self.XYZ = sd_to_XYZ(self.spd, k=683, method=method)
            self.xy = XYZ_to_xy(self.XYZ)
            _cct = uv_to_CCT(xy_to_UCS_uv(self.xy))
            self.cct: float = _cct[0]
            self.duv: float = _cct[1]
            self.dominant_wl = float(dominant_wavelength(self.xy, [1 / 3, 1 / 3])[0])
            self.purity: float = colorimetric_purity(self.xy, (1 / 3, 1 / 3))  # type: ignore
            self.power: float = np.asarray(self.spd.values).sum()
            self.time = datetime.now().astimezone()

    def __str__(self) -> str:
        """
        Return printable string with interesting data for an observant reader.

        Returns
        -------
        str
        """
        return textwrap.dedent(
            f"""
            Spectral Measurement - {self.spectrometer_id}:
                time: {self.time}
                XYZ: {np.array2string(self.XYZ, formatter={"float_kind": lambda x: f"{x:.4f}"})}
                xy: {np.array2string(self.xy, formatter={"float_kind": lambda x: f"{x:.4f}"})}
                CCT: {self.cct:.0f} ± {self.duv:.5f}
                Dominant WL: {self.dominant_wl:.1f} @ {self.purity * 100:.1f}%
                Exposure: {self.exposure:.3f}
            """
        )

    def __repr__(self) -> str:
        """Return a loggable 1-line string for some basic details for this
        measurement.

        Returns
        -------
        str
        """

        return f"Spectral Measurement - {self.spectrometer_id}, Time: {self.time}, XYZ = {self.XYZ}"

    def __eq__(self, other: object) -> bool:
        """Check equality to another `specio.spectrometers.common.Measurement.` Based on
        multiple subfields.

        True if "exposure", "spectrometer_id", "XYZ", "xy", "dominant_wl",
        "power", "time", "cct", "duv" are all equal.

        Parameters
        ----------
        other : Measurement
            The object to compare to

        Returns
        -------
        bool
        """

        keys = [
            "spd",
            "exposure",
            "spectrometer_id",
            "XYZ",
            "xy",
            "dominant_wl",
            "purity",
            "power",
            "time",
            "cct",
            "duv",
        ]
        data = [getattr(self, k) == getattr(other, k) for k in keys]
        return all(np.all(d) for d in data)


class SpecRadiometer(ABC):
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
    def _raw_measure(self) -> RawSPDMeasurement:
        """Conduct remote triggering and RPC / serial interaction to collect
        the raw spectrometer data from the device.

        Returns
        -------
        RawMeasurement
            A simple dataclass with the required parameters to produce fully
            defined :class:`specio.spectrometers.common.Measurement`
        """

        ...

    @property
    def readable_id(self) -> str:
        """Human readable spectrometer id. Defaults to "<MODEL> - <SERIAL>" if
        not set by the implementing class.

        Returns
        -------
        str
        """
        return f"{self.model} - {self.serial_number}"

    def measure(self, repetitions: int = 1) -> SPDMeasurement:
        """Trigger and collect one measurement from the LED tile

        Returns
        -------
        Measurement
            A dataclass containing various convenience calculations from python
            colour-science and the raw SPD.
        """

        if repetitions < 1:
            ArgumentError("Repetitions must be greater than 1")

        _rm: list[RawSPDMeasurement] = []
        for _ in range(repetitions):
            _rm += [self._raw_measure()]

        if len(_rm) == 1:
            return SPDMeasurement.FromRaw(_rm[0])

        spd_values = np.asarray([m.spd.values for m in _rm]).mean(axis=0)
        spd = SpectralDistribution(data=spd_values, domain=_rm[0].spd.domain)
        exposure = np.mean([m.exposure for m in _rm]).item()
        id = _rm[0].spectrometer_id

        return SPDMeasurement.FromRaw(
            RawSPDMeasurement(spd=spd, exposure=exposure, spectrometer_id=id)
        )
