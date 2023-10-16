from dataclasses import dataclass, field
from textwrap import dedent
from typing import List, cast

import numpy as np
import numpy.typing as npt
from numpy import ndarray
from specio.measurement import Measurement
from specio.protobuf import measurements_pb2

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
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
    order: List[int]
    measurements: npt.NDArray = field(default_factory=lambda: np.zeros(shape=(0, 0)))
    metadata: MeasurementList_Notes = field(default_factory=MeasurementList_Notes)

    def __repr__(self) -> str:
        return dedent(
            f"""MeasurementList
                {self.metadata.notes}"""
        )

    pass


def save_measurements(
    file: str,
    measurements: Measurement | List[Measurement],
    notes: MeasurementList_Notes = MeasurementList_Notes(),
    order: None | List[int] = None,
    testColors: None | ndarray | List[List[float]] = None,
):
    if type(measurements) == Measurement:
        measurements = [measurements]
    measurements = cast(list, measurements)

    pbuf = measurements_pb2.MeasurementList()

    for m in measurements:
        m_pbuf = cast(measurements_pb2.Measurement, m.to_buffer(return_pb=True))
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
    pass


def load_measurements(file: str) -> MeasurementList:
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


if __name__ == "__main__":
    from time import time

    def timer_func(func):
        # This function shows the execution time of
        # the function object passed
        def wrap_func(*args, **kwargs):
            t1 = time()
            result = func(*args, **kwargs)
            t2 = time()
            print(f"Function {func.__name__!r} executed in {(t2-t1):.4f}s")
            return result

        return wrap_func

    measures = []
    for i in range(100):
        measures.append(Measurement())

    file = "/Users/tucker/Downloads/test"

    @timer_func
    def time_save():
        save_measurements(
            file=file,
            measurements=measures,
            notes=MeasurementList_Notes("Hello", "World", "Burbank"),
        )

    time_save()

    @timer_func
    def time_read():
        return load_measurements(file=file)

    m = time_read()
    pass
