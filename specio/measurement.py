"""
Data classes for the creation and manipulation of `specio.Measurement` data.
"""

import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self, cast

import numpy as np
from colour import (
    SpectralDistribution,
    XYZ_to_xy,
    dominant_wavelength,
    sd_to_XYZ,
    uv_to_CCT,
    xy_to_UCS_uv,
)

from specio import protobuf
from specio.utility import buffer_to_sd, sd_to_buffer

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
    anc_data: None | Any = None


class Measurement:
    """
    The basic measurement structure for specio. It contains
    `colour.SpectralDistribution` and several convenience calculations. It an
    also be converted to a readable string for logging.
    """

    def _from_buffer(self, data: bytes | protobuf.Measurement):
        m: protobuf.Measurement
        if isinstance(data, bytes):
            m = protobuf.Measurement()
            m.ParseFromString(data)
        else:
            m = cast(protobuf.Measurement, data)

        self.spd = buffer_to_sd(m.spd)
        self.exposure = m.exposure
        self.spectrometer_id = m.spectrometer_id
        self.XYZ = np.array([m.XYZ.X, m.XYZ.Y, m.XYZ.Z])
        self.xy = np.array([m.xy.x, m.xy.y])
        self.cct = m.cct.cct
        self.duv = m.cct.duv
        self.dominant_wl = m.dominant_wl
        self.power = self.spd.values.sum()
        self.time = datetime.fromisoformat(m.time.timestr)

    def to_bytes(self) -> bytes:
        """Return a serialized bytes array

        Returns
        -------
        bytes
            The object data serialized to binary by `protobuf.Measurement`
        """
        return self.to_buffer().SerializeToString()

    def to_buffer(self) -> protobuf.Measurement:
        """Convert this measurement to a protobuf buffer object.

        See Also
        --------
        `Measurement.to_bytes`

        Returns
        -------
        protobuf.Measurement
            The protobuf object. This can be added to other protobuf structures
            or serialized
        """
        m = protobuf.Measurement()
        m.exposure = self.exposure
        m.dominant_wl = self.dominant_wl
        m.power = self.power
        m.spectrometer_id = self.spectrometer_id

        m.time.timestr = self.time.isoformat()

        m.spd.CopyFrom(
            cast(
                protobuf.SpectralDistribution,
                sd_to_buffer(self.spd, return_pb=True),
            )
        )

        m.XYZ.X = self.XYZ[0]
        m.XYZ.Y = self.XYZ[1]
        m.XYZ.Z = self.XYZ[2]

        m.xy.x = self.xy[0]
        m.xy.y = self.xy[1]

        m.cct.cct = self.cct
        m.cct.duv = self.duv

        return m

    def __init__(
        self, raw_meas: RawMeasurement | bytes | protobuf.Measurement
    ):
        if isinstance(raw_meas, (bytes, protobuf.Measurement)):
            self._from_buffer(raw_meas)
            return

        raw_meas = cast(RawMeasurement, raw_meas)
        self.spd = raw_meas.spd
        self.exposure = raw_meas.exposure
        self.spectrometer_id = raw_meas.spectrometer_id
        self.anc_data = raw_meas.anc_data

        method = "ASTM E308"
        if self.spd.shape.interval not in [1, 5, 10, 20]:
            method = "Integration"

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
