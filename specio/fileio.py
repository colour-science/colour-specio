from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import numpy as np
import numpy.typing as npt
import xxhash
from colour.colorimetry.spectrum import MultiSpectralDistributions
from numpy import ndarray
from specio.measurement import Measurement
from specio.protobuf import measurements_pb2

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = (
    "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
)
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"


@dataclass()
class MeasurementList_Notes:
    notes: None | str = None
    author: None | str = None
    location: None | str = None
    software: None | str = "colour-specio"


@dataclass(kw_only=True)
class MeasurementList:
    test_colors: ndarray
    order: list[int]
    measurements: npt.NDArray = field(
        default_factory=lambda: np.zeros(shape=(0, 0))
    )
    metadata: MeasurementList_Notes = field(
        default_factory=MeasurementList_Notes
    )

    @property
    def shortname(self) -> str:
        if self.metadata.notes is None or self.metadata.notes == "":
            spds = MultiSpectralDistributions(
                [m.spd for m in self.measurements]
            )
            return xxhash.xxh32_hexdigest(
                np.ascontiguousarray(spds.values).data
            )
        return self.metadata.notes

    def __repr__(self) -> str:
        return f"MeasurementList - {self.shortname}"


def save_measurements(
    file: str,
    measurements: Measurement | list[Measurement],
    notes: MeasurementList_Notes = MeasurementList_Notes(),
    order: None | list[int] = None,
    testColors: None | ndarray | list[list[float]] = None,
):
    if type(measurements) == Measurement:
        measurements = [measurements]
    measurements = cast(list, measurements)

    pbuf = measurements_pb2.MeasurementList()

    for m in measurements:
        m_pbuf = m.to_buffer()
        pbuf.measurements.append(m_pbuf)

    if notes.notes:
        pbuf.notes = notes.notes

    if notes.author:
        pbuf.author = notes.author

    if notes.location:
        pbuf.location = notes.location

    if notes.software:
        pbuf.software = notes.software

    if order is not None:
        pbuf.order[:] = order

    if testColors is not None:
        if type(testColors) == list:
            testColors = np.array(testColors)
        testColors = cast(np.ndarray, testColors)

        if np.ptp(testColors) > 1 and np.all(np.modf(testColors)[0] < 1e-8):
            for color in testColors:
                tc_buf = measurements_pb2.MeasurementList.TestColor()
                tc_buf.c[:] = [int(value) for value in color.tolist()]
                pbuf.test_colors.append(tc_buf)
        else:
            for color in testColors:
                tc_buf = measurements_pb2.MeasurementList.TestColor()
                tc_buf.f[:] = color
                pbuf.test_colors.append(tc_buf)

    data_string = pbuf.SerializeToString()

    with open(file=file, mode="wb") as f:
        f.write(data_string)


def load_measurements(file: str | Path) -> MeasurementList:
    if isinstance(file, Path):
        file = str(file)

    data_string: bytes
    with open(file, mode="rb") as f:
        data_string = f.read()

    pbuf = measurements_pb2.MeasurementList()
    pbuf.ParseFromString(data_string)

    measurements = []
    for mbuf in pbuf.measurements:
        measurements.append(Measurement(mbuf))
    measurements = np.asarray(measurements)

    tcs = []
    for color in pbuf.test_colors:
        if len(color.f) == 0:
            tcs.append(color.c)
        else:
            tcs.append(color.f)
    tcs = np.array(tcs)

    return MeasurementList(
        measurements=measurements,
        order=np.asarray(pbuf.order),  # type: ignore
        test_colors=tcs,
        metadata=MeasurementList_Notes(
            pbuf.notes, pbuf.author, pbuf.location, pbuf.software
        ),
    )
