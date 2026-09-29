from pathlib import Path

import numpy as np
import pytest
from colour import SpectralDistribution, SpectralShape

from specio._device_implementations.virtual import (
    VirtualColorimeter,
    VirtualSpectrometer,
)
from specio.common import ColorimeterMeasurement, SPDMeasurement
from specio.serialization.csmf import (
    CSMF_Data,
    CSMF_Metadata,
    csmf_data_to_buffer,
    load_csmf_file,
    save_csmf_file,
)

HYBRID_ROWS = 7
"""Row count of the hybrid fixture, alternating spectral and colorimetric."""

FIXED_SHORTNAME = "2519f9ba"
"""The shortname of `fixed_spectral_data`.

Spectral-only files are named from this hash, so the value is pinned.
"""


@pytest.fixture(scope="class")
def virtual_data() -> CSMF_Data:
    vspr = VirtualSpectrometer()

    NUM_VIRTUAL = 100
    measurements = [vspr.measure() for _ in range(NUM_VIRTUAL)]
    test_colors = np.random.uniform(0, 1023, (3, NUM_VIRTUAL)).astype(np.float32)
    order = np.random.permutation(NUM_VIRTUAL)

    ml = CSMF_Data(
        measurements=np.asarray(measurements),
        test_colors=test_colors,
        order=order,
        metadata=CSMF_Metadata(
            notes="Random Test Measurements",
            author="tjdcs",
            location="virtual",
            software="specio-tests",
        ),
    )
    return ml


class Test_CSMF_Files:
    def test_csmf_rw(self, tmp_path: Path, virtual_data: CSMF_Data):
        p = tmp_path.joinpath("test_data")

        buffer = csmf_data_to_buffer(virtual_data)
        p = save_csmf_file(p, virtual_data)

        assert p.exists()
        assert p.is_file()
        assert p.read_bytes() == buffer.SerializeToString()

        read_data = load_csmf_file(p)

        assert read_data == virtual_data

    def test_spectral_file_uses_legacy_field(self, virtual_data: CSMF_Data):
        """A spectral-only file puts every row in `spd_measurements`.

        Readers without wrapper support read that field, so they can
        read these files.
        """
        buffer = csmf_data_to_buffer(virtual_data)

        assert len(buffer.spd_measurements) == len(virtual_data.measurements)
        assert len(buffer.measurements) == 0


@pytest.fixture(scope="class")
def hybrid_data() -> CSMF_Data:
    """A file whose rows alternate spectral and colorimetric, starting and
    ending on a spectral row. The colorimeter carries no spectrum at all.
    """
    vspr = VirtualSpectrometer()
    vcol = VirtualColorimeter()

    measurements = [
        vspr.measure() if i % 2 == 0 else vcol.measure() for i in range(HYBRID_ROWS)
    ]

    test_colors = np.random.uniform(0, 1023, (HYBRID_ROWS, 3)).astype(np.float32)
    order = np.random.permutation(HYBRID_ROWS)

    return CSMF_Data(
        measurements=np.asarray(measurements, dtype=object),
        test_colors=test_colors,
        order=order,
        metadata=CSMF_Metadata(
            notes="Hybrid",
            author="tjdcs",
            location="virtual",
            software="specio-tests",
        ),
    )


def row_types(data: CSMF_Data) -> list[type]:
    """List the type of each measurement row, in file order.

    Parameters
    ----------
    data : CSMF_Data
        The file contents to inspect.

    Returns
    -------
    list[type]
        One entry per row.
    """
    return [type(m) for m in data.measurements]


class Test_Colorimeter_Rows:
    def test_hybrid_file_uses_wrapper_field(self, hybrid_data: CSMF_Data):
        """A file with any colorimeter row puts every row in the
        `measurements` wrapper, in order, and none in `spd_measurements`.
        """
        buffer = csmf_data_to_buffer(hybrid_data)

        assert len(buffer.spd_measurements) == 0
        assert len(buffer.measurements) == HYBRID_ROWS

        wrapped = [
            ColorimeterMeasurement if w.HasField("xyz") else SPDMeasurement
            for w in buffer.measurements
        ]
        assert wrapped == row_types(hybrid_data)

    def test_colorimeter_rows_round_trip(self, tmp_path: Path, hybrid_data: CSMF_Data):
        """A file mixing colorimeter and spectral rows reads back equal to
        what was written, with row order and row types intact.
        """
        p = save_csmf_file(tmp_path.joinpath("hybrid"), hybrid_data)
        read_data = load_csmf_file(p)

        assert row_types(read_data) == row_types(hybrid_data)
        for original, restored in zip(
            hybrid_data.measurements, read_data.measurements, strict=True
        ):
            assert restored == original
        assert read_data == hybrid_data


@pytest.fixture()
def fixed_spectral_data() -> CSMF_Data:
    """Three spectral rows with fixed values, so their hash is stable."""
    shape = SpectralShape(380, 780, 5)
    ramp = np.linspace(0.1, 1.0, len(shape.wavelengths))
    measurements = [
        SPDMeasurement(SpectralDistribution(scale * ramp, shape), 1.0, "fixed")
        for scale in (1.0, 2.0, 3.0)
    ]
    return CSMF_Data(
        measurements=np.asarray(measurements, dtype=object),
        test_colors=np.zeros((len(measurements), 3)),
        order=np.arange(len(measurements)),
    )


class Test_Shortname:
    def test_notes_are_the_shortname(self, hybrid_data: CSMF_Data):
        """Non-empty notes name the file."""
        assert hybrid_data.shortname == hybrid_data.metadata.notes

    def test_spectral_shortname_is_stable(self, fixed_spectral_data: CSMF_Data):
        """A spectral-only file without notes hashes to a pinned value."""
        assert fixed_spectral_data.shortname == FIXED_SHORTNAME

    def test_hybrid_shortname_hashes_rows(self, hybrid_data: CSMF_Data):
        """A file with colorimeter rows and no notes still gets a hash name,
        and `repr` works on it.
        """
        unnamed = CSMF_Data(
            measurements=hybrid_data.measurements,
            test_colors=hybrid_data.test_colors,
            order=hybrid_data.order,
        )

        name = unnamed.shortname
        assert len(name) == len(FIXED_SHORTNAME)
        int(name, base=16)
        assert repr(unnamed) == f"Measurement List - {name}"


class Test_Ancillary:
    def test_ancillary_round_trips(self, tmp_path: Path, virtual_data: CSMF_Data):
        """Arbitrary caller bytes survive the file.

        The schema reserves the field so a caller can carry provenance the
        format does not model.
        """
        payload = b"\x00\x01provenance\xff"
        virtual_data.ancillary = payload

        p = save_csmf_file(tmp_path.joinpath("ancillary"), virtual_data)
        read_data = load_csmf_file(p)

        assert read_data.ancillary == payload

    def test_ancillary_defaults_empty(self, tmp_path: Path, virtual_data: CSMF_Data):
        """A file written without ancillary bytes reads back as empty."""
        virtual_data.ancillary = b""
        p = save_csmf_file(tmp_path.joinpath("plain"), virtual_data)

        assert load_csmf_file(p).ancillary == b""
