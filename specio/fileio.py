from dataclasses import dataclass
from typing import List
from specio.common import Measurement

from specio.protoio._generated_ import measurements_pb2


@dataclass()
class MeasurementList_Notes:
    notes: None | str = None
    author: None | str = None
    location: None | str = None
    software: None | str = "colour-specio"


def save_measurements(
    file: str,
    measurements: Measurement | List[Measurement],
    notes: MeasurementList_Notes = MeasurementList_Notes(),
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

    data_string = pbuf.SerializeToString()

    with open(file=file, mode="wb") as f:
        f.write(data_string)
    pass


def load_measurements(file: str) -> List[Measurement]:
    data_string: bytes
    with open(file=file, mode="rb") as f:
        data_string = f.read()

    pbuf = measurements_pb2.Measurement_List()
    pbuf.ParseFromString(data_string)

    measurements: List[Measurement] = []
    for mbuf in pbuf.measurements:
        measurements.append(Measurement(mbuf))
    pass


if __name__ == "__main__":
    measures = []
    for i in range(10):
        measures.append(Measurement())

    file = "/Users/tucker/Downloads/test.csmf"
    save_measurements(file=file, measurements=measures)
    load_measurements(file=file)
