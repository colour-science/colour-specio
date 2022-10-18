import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
from colour import (
    SpectralDistribution,
    XYZ_to_xy,
    dominant_wavelength,
    sd_to_XYZ,
    uv_to_CCT,
    xy_to_UCS_uv,
)
from numpy import ndarray


@dataclass
class RawMeasurement:
    spd: SpectralDistribution
    exposure: float
    spectrometer_id: str
    anc_data: None | Any = None


@dataclass
class Measurement:
    def __init__(self, raw_meas: RawMeasurement):
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
