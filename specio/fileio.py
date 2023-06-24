from dataclasses import dataclass, field
import re
from textwrap import dedent
from typing import List
from click import File

import numpy as np
from numpy import ndarray
from specio.measurement import Measurement

from specio.protobuf import measurements_pb2

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"

FILE_EXTENSION = ".csmf"


@dataclass()
class MeasurementList_Notes:
    notes: None | str = None
    author: None | str = None
    location: None | str = None
    software: None | str = "colour-specio"


@dataclass()
class MeasurementList:
    measurements: List[Measurement] = field(default_factory=list)
    metadata: MeasurementList_Notes = field(default_factory=MeasurementList_Notes)
    test_colors: ndarray | None = None
    order: List[int] | None = None

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

    pbuf = measurements_pb2.MeasurementList()

    m: Measurement
    for m in measurements:
        m_pbuf = m.to_buffer(return_pb=True)
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
        if np.ptp(testColors) > 1 and np.all(np.modf(testColors)[0] < 1e-8):
            for color in testColors:
                tc_buf = measurements_pb2.MeasurementList.TestColor()
                tc_buf.c[:] = [int(value) for value in color.tolist()]
                pbuf.test_colors.append(tc_buf)
        else:
            for color in testColors:
                tc_buf = measurements_pb2.Measurement_List.TestColor()
                tc_buf.f[:] = color
                pbuf.test_colors.append(tc_buf)

    data_string = pbuf.SerializeToString()

    if file[-5:] != ".csmf":
        file += FILE_EXTENSION

    with open(file=file, mode="wb") as f:
        f.write(data_string)
    pass


def load_measurements(file: str) -> MeasurementList:
    data_string: bytes
    with open(file, mode="rb") as f:
        data_string = f.read()

    pbuf = measurements_pb2.MeasurementList()
    pbuf.ParseFromString(data_string)

    measurements: List[Measurement] = []
    for mbuf in pbuf.measurements:
        measurements.append(Measurement(mbuf))

    tcs = []
    for color in pbuf.test_colors:
        tcs.append(color.c)
    tcs = np.array(tcs)

    measurements: MeasurementList = MeasurementList(
        measurements=measurements,
        order=pbuf.order,
        test_colors=tcs,
        metadata=MeasurementList_Notes(
            pbuf.notes, pbuf.author, pbuf.location, pbuf.software
        ),
    )

    return measurements


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
