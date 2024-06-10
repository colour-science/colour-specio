from pathlib import Path

import numpy as np
import pytest

from specio.serialization.csmf import (
    Measurement_List,
    MeasurementList_Notes,
    load_csmf_file,
    measurement_list_to_buffer,
    save_csmf_file,
)
from specio.spectrometers.common import VirtualSpectrometer


@pytest.fixture(scope="class")
def virtual_data() -> Measurement_List:
    vspr = VirtualSpectrometer()

    NUM_VIRTUAL = 100
    measurements = [vspr.measure() for _ in range(NUM_VIRTUAL)]
    test_colors = np.random.uniform(0, 1023, (3, NUM_VIRTUAL)).astype(
        np.float32
    )
    order = np.random.permutation(NUM_VIRTUAL)

    ml = Measurement_List(
        measurements=np.asarray(measurements),
        test_colors=test_colors,
        order=order,
        metadata=MeasurementList_Notes(
            notes="Random Test Measurements",
            author="tjdcs",
            location="virtual",
            software="specio-tests",
        ),
    )
    return ml


class Test_CSMF_Files:
    def test_write_measurements(self, tmp_path: Path, virtual_data):

        p = tmp_path.joinpath("test_data")

        buffer = measurement_list_to_buffer(virtual_data)
        save_csmf_file(p, virtual_data)

        read_file = load_csmf_file(p)

        assert read_file == virtual_data
