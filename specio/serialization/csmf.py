from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import xxhash
from colour.colorimetry.spectrum import MultiSpectralDistributions
from colour.hints import NDArray
from numpy import ndarray

from specio.common import ColorimeterMeasurement, SPDMeasurement
from specio.serialization.measurements import (
    colorimeter_measurement_from_bytes,
    colorimeter_measurement_to_proto,
    spd_measurement_from_bytes,
    spd_measurement_to_proto,
)
from specio.serialization.protobuf import measurements_pb2

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"
__all__ = [
    "CSMF_Data",
    "CSMF_Metadata",
    "csmf_data_to_buffer",
    "load_csmf_file",
    "save_csmf_file",
]


@dataclass()
class CSMF_Metadata:
    """Several metadata strings relating to how a set of measurements was
    conducted.
    """

    notes: None | str = None
    author: None | str = None
    location: None | str = None
    software: None | str = "colour-specio"


@dataclass(kw_only=True)
class CSMF_Data:
    """The contents of a CSMF file: measurement rows, the test colors they
    measured, the order they were measured in, and metadata.

    Attributes
    ----------
    test_colors : ndarray
        The test colors the rows measured.
    order : Iterable[int]
        The measurement order of the rows, as integer indices.
    measurements : NDArray
        The measurement rows, in file order. Each row is an
        :class:`SPDMeasurement` or a :class:`ColorimeterMeasurement`.
    metadata : CSMF_Metadata
        Notes, author, location, and software strings.
    ancillary : bytes
        Opaque caller bytes carried through the file. The schema reserves
        the field so a caller can attach provenance CSMF does not model.
        specio neither interprets nor validates it. Empty by default.

    Notes
    -----
    A file of spectral rows alone stores them in the ``spd_measurements``
    field. A file with any colorimeter row stores every row in the
    ``measurements`` wrapper field instead, so one ordered list keeps the
    correspondence with ``order`` and ``test_colors``. A reader without
    wrapper support sees zero measurements in such a file.
    """

    test_colors: ndarray
    order: Iterable[int]
    measurements: NDArray = field(
        default_factory=lambda: np.empty_like(prototype=SPDMeasurement)
    )
    metadata: CSMF_Metadata = field(default_factory=CSMF_Metadata)
    ancillary: bytes = b""

    @property
    def shortname(self) -> str:
        """A short name: ``metadata.notes`` if set, else a hash of the rows.

        A file of spectral rows alone hashes its spectra. A file with any
        colorimeter row hashes the XYZ of every row, which both row types
        carry.

        Returns
        -------
        str
        """
        if self.metadata.notes is None or self.metadata.notes == "":
            if any(isinstance(m, ColorimeterMeasurement) for m in self.measurements):
                XYZ = np.asarray([m.XYZ for m in self.measurements], dtype=np.float64)
                return xxhash.xxh32_hexdigest(np.ascontiguousarray(XYZ).data)
            spds = MultiSpectralDistributions([m.spd for m in self.measurements])
            return xxhash.xxh32_hexdigest(np.ascontiguousarray(spds.values).data)
        return self.metadata.notes

    def __repr__(self) -> str:
        return f"Measurement List - {self.shortname}"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, CSMF_Data):
            return all(
                (
                    np.all(self.test_colors == value.test_colors),
                    np.all(self.order == value.order),
                    np.all(self.measurements == value.measurements),
                    self.metadata == value.metadata,
                    self.ancillary == value.ancillary,
                )
            )
        return False


def csmf_data_to_buffer(  # noqa: C901
    ml: CSMF_Data,
) -> measurements_pb2.CSFM_File:
    pbuf = measurements_pb2.CSFM_File()

    # A colorimeter reading has no spectrum, so it cannot go in
    # `spd_measurements`. The `measurements` wrapper holds either kind and
    # keeps them in one ordered list, which is what `order` and
    # `test_colors` index into.
    #
    # Files of spectral readings alone use the legacy field, so readers
    # without wrapper support can read them.
    if any(isinstance(m, ColorimeterMeasurement) for m in ml.measurements):
        for m in ml.measurements:
            wrapper = measurements_pb2.CSFM_File.Measurement()
            if isinstance(m, ColorimeterMeasurement):
                wrapper.xyz.CopyFrom(colorimeter_measurement_to_proto(m))
            else:
                wrapper.spd.CopyFrom(spd_measurement_to_proto(m))
            pbuf.measurements.append(wrapper)
    else:
        for m in ml.measurements:
            m_pbuf = spd_measurement_to_proto(m)
            pbuf.spd_measurements.append(m_pbuf)

    if ml.ancillary:
        pbuf.ancillary = ml.ancillary

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
                tc_buf = measurements_pb2.CSFM_File.TestColor()
                tc_buf.c[:] = [int(value) for value in color.tolist()]
                pbuf.test_colors.append(tc_buf)
        else:
            for color in testColors:
                tc_buf = measurements_pb2.CSFM_File.TestColor()
                tc_buf.f[:] = color
                pbuf.test_colors.append(tc_buf)
    return pbuf


def save_csmf_file(
    file: str | Path,
    ml: CSMF_Data,
) -> Path:
    buffer = csmf_data_to_buffer(ml)
    data_string = buffer.SerializeToString()

    if isinstance(file, str):
        file = Path(file)

    file = file.with_suffix(".csmf")

    with open(file=file, mode="wb") as f:
        f.write(data_string)

    return file


def load_csmf_file(file: str | Path, recompute: bool = False) -> CSMF_Data:
    """Load measurement data from a file.

    Parameters
    ----------
    file : str | Path
        The csmf file to read.
    recompute : bool, optional
        Recomputes derived data from each row's source data: XYZ, CCT, and
        the rest from a spectral row's spectrum, and CCT, xy, and the rest
        from a colorimeter row's XYZ. Slow for large files. By default False.

    Returns
    -------
    CSMF_Data
        The file contents. Its rows are :class:`SPDMeasurement` and
        :class:`ColorimeterMeasurement` objects in file order.
    """
    if isinstance(file, str):
        file = Path(file)
    file = file.with_suffix(".csmf")

    data_string: bytes
    with open(file, mode="rb") as f:
        data_string = f.read()

    pbuf = measurements_pb2.CSFM_File()
    pbuf.ParseFromString(data_string)

    # Prefer the wrapper: it is the only field that can carry a
    # colorimeter reading, and a writer that uses it puts every row there.
    # Files of spectral readings alone use the legacy field.
    measurements = []
    if len(pbuf.measurements) > 0:
        for wrapper in pbuf.measurements:
            if wrapper.HasField("xyz"):
                measurements.append(
                    colorimeter_measurement_from_bytes(wrapper.xyz, recompute=recompute)
                )
            else:
                measurements.append(
                    spd_measurement_from_bytes(wrapper.spd, recompute=recompute)
                )
    else:
        for mbuf in pbuf.spd_measurements:
            measurements.append(spd_measurement_from_bytes(mbuf, recompute=recompute))
    measurements = np.asarray(measurements, dtype=object)

    tcs = []
    for color in pbuf.test_colors:
        if len(color.f) == 0:
            tcs.append(color.c)
        else:
            tcs.append(color.f)
    tcs = np.array(tcs)

    return CSMF_Data(
        measurements=measurements,
        order=np.asarray(pbuf.order),
        test_colors=tcs,
        metadata=CSMF_Metadata(pbuf.notes, pbuf.author, pbuf.location, pbuf.software),
        ancillary=pbuf.ancillary,
    )
