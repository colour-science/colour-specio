from pathlib import Path

import numpy as np
import pytest

from specio.scripts import csmf_anonymize
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


class Test_CSMF_Anonymize:
    def test_csmf_anonymize(self, tmp_path: Path, virtual_data):
        p = tmp_path.joinpath("test_data")

        buffer = csmf_data_to_buffer(virtual_data)
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
