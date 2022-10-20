import textwrap
from dataclasses import dataclass
from datetime import datetime

from typing import Any, Tuple
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
from specio.protoio._generated_ import measurements_pb2

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


@dataclass
class Measurement:
    def _from_protobuf(self, data: bytes | measurements_pb2.Measurement):
        m: measurements_pb2.Measurement
        if type(data) == bytes:
            m = measurements_pb2.Measurement()
            m.ParseFromString(data)
        else:
            m = data

        self.spd = SpectralDistribution(
            data=m.spd.values,
            shape=SpectralShape(
                start=m.spd.shape.start, end=m.spd.shape.end, interval=m.spd.shape.step
            ),
            name=m.spd.name,
        )
        self.exposure = m.exposure
        self.spectrometer_id = m.spectrometer_id
        self.XYZ = np.array([m.XYZ.X, m.XYZ.Y, m.XYZ.Z])
        self.xy = np.array([m.xy.x, m.xy.y])
        self.cct = m.cct.cct
        self.duv = m.cct.duv
        self.dominant_wl = m.dominant_wl
        self.power = m.power
        self.time = datetime.fromisoformat(m.time.timestr)
        self.anc_data = None

    def to_protobuf(self) -> Tuple[bytes, measurements_pb2.Measurement]:
        m = measurements_pb2.Measurement()
        m.exposure = self.exposure
        m.dominant_wl = self.dominant_wl
        m.power = self.power
        m.spectrometer_id = self.spectrometer_id

        m.time.timestr = self.time.isoformat()

        m.spd.values[:] = self.spd.values.tolist()
        m.spd.shape.start = self.spd.shape.start
        m.spd.shape.end = self.spd.shape.end
        m.spd.shape.step = self.spd.shape.interval
        m.spd.name = self.spd.name

        m.XYZ.X = self.XYZ[0]
        m.XYZ.Y = self.XYZ[1]
        m.XYZ.Z = self.XYZ[2]

        m.xy.x = self.xy[0]
        m.xy.y = self.xy[1]

        m.cct.cct = self.cct
        m.cct.duv = self.duv

        if self.anc_data is not None:
            pass

        return (m.SerializeToString(), m)

    def __init__(
        self,
        raw_meas: (None | RawMeasurement | bytes | measurements_pb2.Measurement) = None,
    ):
        if type(raw_meas) is bytes or type(raw_meas) == measurements_pb2.Measurement:
            self._from_protobuf(raw_meas)
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
            self.spd = raw_meas.spd
            self.exposure = raw_meas.exposure
            self.spectrometer_id = raw_meas.spectrometer_id
            self.anc_data = raw_meas.anc_data

        self.XYZ = sd_to_XYZ(self.spd, k=6.83)  # TODO colour-science > 0.4.2 k=683
        self.xy = XYZ_to_xy(self.XYZ)
        _cct = uv_to_CCT(xy_to_UCS_uv(self.xy))
        self.cct = _cct[0]
        self.duv = _cct[1]
        self.dominant_wl = dominant_wavelength(self.xy, [1 / 3, 1 / 3])[0]
        self.power = self.spd.values.sum() * 1000

    spd: SpectralDistribution
    exposure: float
    spectrometer_id: str
    XYZ: ndarray
    xy: ndarray
    cct: ndarray
    duv: ndarray
    dominant_wl: float
    power: float
    anc_data: None | Any
    time: datetime = datetime.now()

    def __str__(self) -> str:
        return textwrap.dedent(
            f"""
            Spectral Measurement - {self.spectrometer_id}:
                time: {self.time}
                XYZ: {np.array2string(self.XYZ, formatter={'float_kind':lambda x: "%.2f" % x})}
                CCT: {self.cct:.0f} ± {self.duv:.5f}
                Dominant WL: {self.dominant_wl:.1f}
            """
        )


if __name__ == "__main__":
    m = Measurement()
    str = m.to_protobuf()[0]
    print(str)
    m2 = Measurement(str)
    pass
