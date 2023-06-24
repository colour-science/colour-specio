import textwrap
from dataclasses import dataclass
from datetime import datetime

from typing import Any, Self, Tuple, cast
import colour

import numpy as np
from colour import (
    SpectralDistribution,
    SpectralShape,
    XYZ_to_xy,
    dominant_wavelength,
    sd_to_XYZ,
    uv_to_CCT,
    xy_to_UCS_uv,
)
from numpy import byte, ndarray, power
from specio import protobuf
from specio.utility import buffer_to_sd, sd_to_buffer

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"


@dataclass
class RawMeasurement:
    spd: SpectralDistribution
    exposure: float
    spectrometer_id: str
    anc_data: None | Any = None


class Measurement:
    def _from_buffer(self, data: bytes | protobuf.Measurement):
        m: protobuf.Measurement
        if type(data) == bytes:
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
        self.power = m.power
        self.time = datetime.fromisoformat(m.time.timestr)

    def to_buffer(self, return_pb: bool = False) -> bytes | protobuf.Measurement:
        m = protobuf.Measurement()
        m.exposure = self.exposure
        m.dominant_wl = self.dominant_wl
        m.power = self.power
        m.spectrometer_id = self.spectrometer_id

        m.time.timestr = self.time.isoformat()

        m.spd.CopyFrom(
            cast(protobuf.SpectralDistribution, sd_to_buffer(self.spd, return_pb=True))  # type: ignore
        )

        m.XYZ.X = self.XYZ[0]
        m.XYZ.Y = self.XYZ[1]
        m.XYZ.Z = self.XYZ[2]

        m.xy.x = self.xy[0]
        m.xy.y = self.xy[1]

        m.cct.cct = self.cct
        m.cct.duv = self.duv

        return m if return_pb else m.SerializeToString()

    def __init__(
        self,
        raw_meas: (None | RawMeasurement | bytes | protobuf.Measurement) = None,
    ):
        if type(raw_meas) is bytes or type(raw_meas) == protobuf.Measurement:
            self._from_buffer(raw_meas)
            return

        if raw_meas is None:
            self.spd = colour.sd_multi_leds(
                np.random.randint(400, 700, size=3), np.random.randint(40, 150, size=3)
            )
            self.spd.values / 1000
            self.exposure = 1
            self.spectrometer_id = "Virtual Spectrometer"
            self.anc_data = None
        else:
            raw_meas = cast(RawMeasurement, raw_meas)
            self.spd = raw_meas.spd
            self.exposure = raw_meas.exposure
            self.spectrometer_id = raw_meas.spectrometer_id
            self.anc_data = raw_meas.anc_data

        self.XYZ = sd_to_XYZ(self.spd, k=683)
        self.xy = XYZ_to_xy(self.XYZ)
        _cct = uv_to_CCT(xy_to_UCS_uv(self.xy))
        self.cct: float = _cct[0]
        self.duv: float = _cct[1]
        self.dominant_wl = float(dominant_wavelength(self.xy, [1 / 3, 1 / 3])[0])
        self.power = self.spd.values.sum() * 1000
        self.time = datetime.now()

    def __str__(self) -> str:
        return textwrap.dedent(
            f"""
            Spectral Measurement - {self.spectrometer_id}:
                time: {self.time}
                XYZ: {np.array2string(self.XYZ, formatter={'float_kind':lambda x: "%.2f" % x})}
                xy: {np.array2string(self.xy, formatter={'float_kind':lambda x: "%.4f" % x})}
                CCT: {self.cct:.0f} ± {self.duv:.5f}
                Dominant WL: {self.dominant_wl:.1f}
                Exposure: {self.exposure:.3f}
            """
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: Self) -> bool:
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
        for d in data:
            if not np.all(d):
                return False
        return True


if __name__ == "__main__":
    m = Measurement()
    str = m.to_buffer()
    m2 = Measurement(str)
    print(m2 == m)
    pass
