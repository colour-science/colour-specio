"""
Data classes for the creation and manipulation of `specio.Measurement` data.
"""

import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self

import numpy as np
from colour import (
    SpectralDistribution,
    XYZ_to_xy,
    dominant_wavelength,
    sd_to_XYZ,
    uv_to_CCT,
    xy_to_UCS_uv,
)

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = (
    "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
)
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"


@dataclass
class RawMeasurement:
    """
    A measurement only containing the bare minimum amount of collected data.
    Expected to be further transformed into `specio.Measurement`.
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
    def from_raw(cls, raw: RawMeasurement) -> "SPDMeasurement":
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
            self.power: float = np.asarray(self.spd.values).sum()
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
            Spectral Measurement - {self.spectrometer_id}:
                time: {self.time}
                XYZ: {np.array2string(self.XYZ, formatter={'float_kind':lambda x: "%.2f" % x})}
                xy: {np.array2string(self.xy, formatter={'float_kind':lambda x: "%.4f" % x})}
                CCT: {self.cct:.0f} ± {self.duv:.5f}
                Dominant WL: {self.dominant_wl:.1f}
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

    def __eq__(self, other: Self) -> bool:
        """Check equality to another `specio.measurement.Measurement.` Based on
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
            "power",
            "time",
            "cct",
            "duv",
        ]
        data = [getattr(self, k) == getattr(other, k) for k in keys]
        return all(np.all(d) for d in data)
