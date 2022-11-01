from dataclasses import dataclass
import re
from typing import List

import numpy as np
from numpy import ndarray
from specio.common import Measurement

from specio.protobuf import measurements_pb2

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"

FILE_EXTENSION = ".csmf"


@dataclass
class MeasurementList_Notes:
    notes: None | str = None
    author: None | str = None
    location: None | str = None
    software: None | str = "colour-specio"


@dataclass
class MeasurementList:
    measurements: List[Measurement]
    metadata: MeasurementList_Notes = MeasurementList_Notes()
    test_colors: ndarray | None = None
    order: List[int] | None = None
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

    pbuf = measurements_pb2.Measurement_List()

    m: Measurement
    for m in measurements:
        m_pbuf = m.to_protobuf()[1]
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
                tc_buf = measurements_pb2.Measurement_List.TestColor()
                tc_buf.c[:] = [int(value) for value in color.tolist()]
                pbuf.colors.append(tc_buf)
        else:
            for color in testColors:
                tc_buf = measurements_pb2.Measurement_List.TestColor()
                tc_buf.f[:] = color
                pbuf.colors.append(tc_buf)

    data_string = pbuf.SerializeToString()

    with open(file=file + FILE_EXTENSION, mode="wb") as f:
        f.write(data_string)
    pass


def load_measurements(file: str) -> MeasurementList:
    data_string: bytes
    file = re.sub(".csmf", "", file)
    with open(file=file + FILE_EXTENSION, mode="rb") as f:
        data_string = f.read()

    pbuf = measurements_pb2.Measurement_List()
    pbuf.ParseFromString(data_string)

    measurements: List[Measurement] = []
    for mbuf in pbuf.measurements:
        measurements.append(Measurement(mbuf))

    measurements: MeasurementList = MeasurementList(
        measurements=measurements, order=pbuf.order, test_colors=pbuf.test_colors
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
        save_measurements(file=file, measurements=measures)

    time_save()

    @timer_func
    def time_read():
        load_measurements(file=file)

    time_read()
