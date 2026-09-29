from pathlib import Path

import numpy as np
import pytest

from specio._device_implementations.virtual import (
    VirtualColorimeter,
    VirtualSpectrometer,
)
from specio.scripts import csmf_anonymize
from specio.serialization.csmf import (
    CSMF_Data,
    CSMF_Metadata,
    load_csmf_file,
    save_csmf_file,
)

HYBRID_ROWS = 5
"""Row count of the hybrid fixture, alternating spectral and colorimetric."""


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


@pytest.fixture(scope="class")
def hybrid_data() -> CSMF_Data:
    """A file whose rows alternate spectral and colorimetric, with
    identifying metadata and ancillary bytes.
    """
    vspr = VirtualSpectrometer()
    vcol = VirtualColorimeter()

    measurements = [
        vspr.measure() if i % 2 == 0 else vcol.measure() for i in range(HYBRID_ROWS)
    ]

    return CSMF_Data(
        measurements=np.asarray(measurements, dtype=object),
        test_colors=np.random.uniform(0, 1023, (HYBRID_ROWS, 3)).astype(np.float32),
        order=np.random.permutation(HYBRID_ROWS),
        metadata=CSMF_Metadata(
            notes="Hybrid",
            author="tjdcs",
            location="virtual",
            software="specio-tests",
        ),
        ancillary=b"operator=tjdcs;site=virtual",
    )


class Test_CSMF_Anonymize:
    def test_csmf_anonymize(self, tmp_path: Path, virtual_data: CSMF_Data):
        p = tmp_path.joinpath("test_data")

        p = save_csmf_file(p, virtual_data)

        anon_file_path = csmf_anonymize.main(str(p))

        read_file = load_csmf_file(anon_file_path)

        assert read_file.metadata.notes == ""
        assert read_file.metadata.author == ""
        assert read_file.metadata.location == ""
        assert read_file.metadata.software == "specio:csmf_anonymize"
        assert np.all(read_file.measurements == virtual_data.measurements)
        assert np.all(read_file.order == virtual_data.order)
        assert np.all(read_file.test_colors == virtual_data.test_colors)

    def test_anonymize_colorimeter_rows(self, tmp_path: Path, hybrid_data: CSMF_Data):
        """A file with colorimeter rows keeps its rows, in order, and loses
        its identifying metadata.
        """
        p = save_csmf_file(tmp_path.joinpath("hybrid"), hybrid_data)

        read_file = load_csmf_file(csmf_anonymize.main(str(p)))

        assert read_file.metadata == CSMF_Metadata(
            notes="", author="", location="", software="specio:csmf_anonymize"
        )
        assert [type(m) for m in read_file.measurements] == [
            type(m) for m in hybrid_data.measurements
        ]
        assert np.all(read_file.measurements == hybrid_data.measurements)
        assert np.all(read_file.order == hybrid_data.order)
        assert np.all(read_file.test_colors == hybrid_data.test_colors)

    def test_anonymize_drops_ancillary(self, tmp_path: Path, hybrid_data: CSMF_Data):
        """Ancillary bytes are opaque and may identify the session, so the
        anonymized file carries none.
        """
        spectral_only = CSMF_Data(
            measurements=hybrid_data.measurements[::2],
            test_colors=hybrid_data.test_colors[::2],
            order=np.arange(len(hybrid_data.measurements[::2])),
            ancillary=hybrid_data.ancillary,
        )
        for data in (hybrid_data, spectral_only):
            p = save_csmf_file(tmp_path.joinpath("with_ancillary"), data)
            assert load_csmf_file(p).ancillary == data.ancillary

            read_file = load_csmf_file(csmf_anonymize.main(str(p)))

            assert read_file.ancillary == b""
