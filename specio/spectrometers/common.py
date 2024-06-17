"""
Define basic spectrometer interfaces
"""

import datetime
import textwrap
from abc import ABC, abstractmethod
from ctypes import ArgumentError
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Self, final

import numpy as np
from colour import SpectralDistribution, SpragueInterpolator, sd_multi_leds
from colour.colorimetry.dominant import (
    colorimetric_purity,
    dominant_wavelength,
)
from colour.colorimetry.tristimulus_values import sd_to_XYZ
from colour.models.cie_ucs import xy_to_UCS_uv
from colour.models.cie_xyy import XYZ_to_xy
from colour.temperature import uv_to_CCT

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = (
    "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
)
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = []


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
            self.dominant_wl = float(
                dominant_wavelength(self.xy, [1 / 3, 1 / 3])[0]
            )
            self.purity: float = colorimetric_purity(self.xy, (1 / 3, 1 / 3))  # type: ignore
            self.power: float = np.asarray(self.spd.values).sum()
            self.time = datetime.datetime.now(tz=datetime.UTC)

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
                XYZ: {np.array2string(self.XYZ, formatter={'float_kind':lambda x: "%.2f" % x})}
                xy: {np.array2string(self.xy, formatter={'float_kind':lambda x: "%.4f" % x})}
                CCT: {self.cct:.0f} ± {self.duv:.5f}
                Dominant WL: {self.dominant_wl:.1f} @ {self.purity * 100:.1f}%
                Exposure: {self.exposure:.3f}
            """  # noqa: E501
        )

    def __repr__(self) -> str:
        """Return a loggable 1-line string for some basic details for this
        measurement.

        Returns
        -------
        str
        """

        return f"Spectral Measurement - {self.spectrometer_id}, Time: {self.time}, XYZ = {self.XYZ}"  # noqa: E501

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
        for i in range(repetitions):
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


@final
class VirtualSpectrometer(SpecRadiometer):
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

    @cached_property
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

    def _raw_measure(self) -> RawSPDMeasurement:
        """Return a random SPD generated by combining three gaussian spectra

        Returns
        -------
        RawMeasurement
            A simple dataclass with the required parameters to produce fully
            defined :class:`specio.spectrometers.common.Measurement`
        """
        peaks = np.random.randint([460, 510, 600], [480, 570, 690], 3)
        widths = np.random.randint(40, 80, 3)
        powers = np.random.randint(10, 40, 3) / 1000
        spd = sd_multi_leds(
            peak_wavelengths=peaks,
            half_spectral_widths=widths / 2,
            peak_power_ratios=powers,
        )
        spd.interpolator = SpragueInterpolator

        _measurement = RawSPDMeasurement(
            spd=spd,
            exposure=1,
            spectrometer_id="Virtual Spectrometer",
        )
        return _measurement
