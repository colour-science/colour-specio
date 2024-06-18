from pathlib import Path

import numpy as np
import pytest

from specio.serialization.csmf import (
    CSMF_Data,
    CSMF_Metadata,
    csmf_data_to_buffer,
    load_csmf_file,
    save_csmf_file,
)
from specio.spectrometers.common import VirtualSpectrometer


@pytest.fixture(scope="class")
def virtual_data() -> CSMF_Data:
    vspr = VirtualSpectrometer()

    NUM_VIRTUAL = 100
    measurements = [vspr.measure() for _ in range(NUM_VIRTUAL)]
    test_colors = np.random.uniform(0, 1023, (3, NUM_VIRTUAL)).astype(np.float32)
    order = np.random.permutation(NUM_VIRTUAL)

    ml = CSMF_Data(
        measurements=np.asarray(measurements),  # type: ignore
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
    def test_csmf_rw(self, tmp_path: Path, virtual_data):
        p = tmp_path.joinpath("test_data")

        buffer = csmf_data_to_buffer(virtual_data)
        p = save_csmf_file(p, virtual_data)

        assert p.exists()
        assert p.is_file()
        assert p.read_bytes() == buffer.SerializeToString()

        read_data = load_csmf_file(p)

        assert read_data == virtual_data
