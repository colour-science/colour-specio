from pathlib import Path

import numpy as np
import pytest

from specio._device_implementations.virtual import (
    VirtualColorimeter,
    VirtualSpectrometer,
)
from specio.serialization.csmf import (
    CSMF_Data,
    CSMF_Metadata,
    csmf_data_to_buffer,
    load_csmf_file,
    save_csmf_file,
)


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


@pytest.fixture(scope="class")
def hybrid_data() -> CSMF_Data:
    """A disciplined session's file: bright rows spectral, dark rows
    colorimetric. The colorimeter carries no spectrum at all.
    """
    vspr = VirtualSpectrometer()
    vcol = VirtualColorimeter()

    spectral = [vspr.measure() for _ in range(4)]
    colorimetric = [vcol.measure() for _ in range(3)]
    measurements = [*spectral, *colorimetric]

    test_colors = np.random.uniform(0, 1023, (len(measurements), 3)).astype(np.float32)
    order = np.arange(len(measurements))

    return CSMF_Data(
        measurements=np.asarray(measurements, dtype=object),
        test_colors=test_colors,
        order=order,
        metadata=CSMF_Metadata(notes="Hybrid", software="specio-tests"),
    )


class Test_Colorimeter_Rows:
    def test_colorimeter_rows_round_trip(self, tmp_path: Path, hybrid_data: CSMF_Data):
        """A colorimeter reading survives a save/load cycle.

        The reader previously walked only the spectral rows, so a hybrid
        file came back short and the colorimetric readings vanished
        silently.
        """
        p = save_csmf_file(tmp_path.joinpath("hybrid"), hybrid_data)
        read_data = load_csmf_file(p)

        assert len(read_data.measurements) == len(hybrid_data.measurements)

        kinds = [type(m).__name__ for m in read_data.measurements]
        assert kinds.count("ColorimeterMeasurement") == 3
        assert kinds.count("SPDMeasurement") == 4

    def test_colorimeter_row_values_survive(
        self, tmp_path: Path, hybrid_data: CSMF_Data
    ):
        """The colorimetric rows come back with their tristimulus intact."""
        p = save_csmf_file(tmp_path.joinpath("hybrid"), hybrid_data)
        read_data = load_csmf_file(p)

        for original, restored in zip(
            hybrid_data.measurements, read_data.measurements, strict=True
        ):
            np.testing.assert_allclose(restored.XYZ, original.XYZ, rtol=1e-5)


class Test_Ancillary:
    def test_ancillary_round_trips(self, tmp_path: Path, virtual_data: CSMF_Data):
        """Arbitrary caller bytes survive the file.

        The field is in the schema so a caller can carry provenance the
        format does not model. It was never plumbed through the Python
        surface.
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
