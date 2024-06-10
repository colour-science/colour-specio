from specio.serialization.measurements import (
    spd_measurement_from_bytes,
    spd_measurement_to_bytes,
)
from specio.spectrometers.common import VirtualSpectrometer


class TestSPDMeasurementSerialization:
    def test_spd_to_bytes(self):
        vs = VirtualSpectrometer()
        m = vs.measure()
        result = spd_measurement_to_bytes(m)

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_round_trip(self):
        vs = VirtualSpectrometer()
        m = vs.measure()

        result = spd_measurement_to_bytes(m)

        m2 = spd_measurement_from_bytes(result)
        assert m2 == m
