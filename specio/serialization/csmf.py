from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

import numpy as np
import xxhash
from colour.colorimetry.spectrum import MultiSpectralDistributions
from numpy import ndarray

from specio.measurement import SPDMeasurement
from specio.serialization.measurements import (
    spd_measurement_from_bytes,
    spd_measurement_to_proto,
)
from specio.serialization.protobuf import measurements_pb2

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
    """Several metadata strings relating to how a set of measurements was
    conducted.
    """

    notes: None | str = None
    author: None | str = None
    location: None | str = None
    software: None | str = "colour-specio"


@dataclass(kw_only=True)
class Measurement_List:
    """List of measurements, test colors, measurement, order, and metadata.

    Fields
    -------
    _type_
        _description_
    """

    test_colors: ndarray
    order: Iterable[int]
    measurements: Iterable[SPDMeasurement] = field(
        default_factory=lambda: np.zeros(shape=(0, 0))
    )
    metadata: MeasurementList_Notes = field(
        default_factory=MeasurementList_Notes
    )

    @property
    def shortname(self) -> str:
        """A short name, generated by hashing underlying data if metadata.notes
        is empty.

        Returns
        -------
        str
        """
        if self.metadata.notes is None or self.metadata.notes == "":
            spds = MultiSpectralDistributions(
                [m.spd for m in self.measurements]
            )
            return xxhash.xxh32_hexdigest(
                np.ascontiguousarray(spds.values).data
            )
        return self.metadata.notes

    def __repr__(self) -> str:
        return f"Measurement List - {self.shortname}"

    def __eq__(self, value: Self) -> bool:
        return all(
            (
                np.all(self.test_colors == value.test_colors),
                np.all(self.order == value.order),
                np.all(self.measurements == value.measurements),
                self.metadata == value.metadata,
            )
        )


def measurement_list_to_buffer(
    ml: Measurement_List,
) -> measurements_pb2.Measurement_List:
    pbuf = measurements_pb2.Measurement_List()

    for m in ml.measurements:
        m_pbuf = spd_measurement_to_proto(m)
        pbuf.spd_measurements.append(m_pbuf)

    if ml.metadata.notes:
        pbuf.notes = ml.metadata.notes

    if ml.metadata.author:
        pbuf.author = ml.metadata.author

    if ml.metadata.location:
        pbuf.location = ml.metadata.location

    if ml.metadata.software:
        pbuf.software = ml.metadata.software

    if ml.order is not None:
        pbuf.order[:] = ml.order

    if ml.test_colors is not None:
        testColors = np.asarray(ml.test_colors)

        if np.ptp(testColors) > 1 and np.all(np.modf(testColors)[0] < 1e-8):
            # If the test colors are ints, use the int field.
            for color in testColors:
                tc_buf = measurements_pb2.Measurement_List.TestColor()
                tc_buf.c[:] = [int(value) for value in color.tolist()]
                pbuf.test_colors.append(tc_buf)
        else:
            for color in testColors:
                tc_buf = measurements_pb2.Measurement_List.TestColor()
                tc_buf.f[:] = color
                pbuf.test_colors.append(tc_buf)
    return pbuf


def save_csmf_file(
    file: str | Path,
    ml: Measurement_List,
):
    buffer = measurement_list_to_buffer(ml)
    data_string = buffer.SerializeToString()

    if isinstance(file, str):
        file = Path(file)

    file = file.with_suffix(".csmf")

    with open(file=file, mode="wb") as f:
        f.write(data_string)


def load_csmf_file(file: str | Path) -> Measurement_List:
    if isinstance(file, str):
        file = Path(file)
    file = file.with_suffix(".csmf")

    data_string: bytes
    with open(file, mode="rb") as f:
        data_string = f.read()

    pbuf = measurements_pb2.Measurement_List()
    pbuf.ParseFromString(data_string)

    measurements = []
    for mbuf in pbuf.spd_measurements:
        measurements.append(spd_measurement_from_bytes(mbuf))
    measurements = np.asarray(measurements)

    tcs = []
    for color in pbuf.test_colors:
        if len(color.f) == 0:
            tcs.append(color.c)
        else:
            tcs.append(color.f)
    tcs = np.array(tcs)

    return Measurement_List(
        measurements=measurements,
        order=np.asarray(pbuf.order),  # type: ignore
        test_colors=tcs,
        metadata=MeasurementList_Notes(
            pbuf.notes, pbuf.author, pbuf.location, pbuf.software
        ),
    )