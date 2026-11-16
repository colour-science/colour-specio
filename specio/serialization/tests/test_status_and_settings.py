"""The CSMF file carries a reading's status and settings, and old files and
old readers keep working.

The ``*_BYTES`` constants below are the serialized form of fixed measurements,
captured from the code before the status and settings fields existed. A
measurement without either must still serialize to exactly those bytes.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import numpy as np
from colour import SpectralDistribution, SpectralShape
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from specio.common import ColorimeterMeasurement, ReadingStatus, SPDMeasurement
from specio.serialization.csmf import (
    CSMF_Data,
    CSMF_Metadata,
    csmf_data_to_buffer,
    load_csmf_file,
    save_csmf_file,
)
from specio.serialization.measurements import (
    colorimeter_measurement_from_bytes,
    colorimeter_measurement_to_bytes,
    spd_measurement_from_bytes,
    spd_measurement_to_bytes,
)
from specio.serialization.protobuf import common_pb2, measurements_pb2

if TYPE_CHECKING:
    from pathlib import Path

FIXED_TIME = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.UTC)
STATUS = ReadingStatus(
    code="OK06",
    message="TEMPERATURE_SHIFT, BELOW_GUARANTEED_RANGE",
    flags=("TEMPERATURE_SHIFT", "BELOW_GUARANTEED_RANGE"),
)
METADATA = CSMF_Metadata(notes="n", author="a", location="l", software="s")
SETTINGS = {"measurement_speed": "fast", "sync_mode": "internal"}

COLORIMETER_BYTES = bytes.fromhex(
    "0a1b090000000000002440110000000000003440190000000000003e40121209"
    "000000000000d03f11000000000000e03f2a1209000000000064b94011fa7e6a"
    "bc7493683f3100000000003081403a1b0a19323032342d30312d30325430333a"
    "30343a30352b30303a3030419a9999999999d93f8101000000000000e03f8a01"
    "0946495845442d434f4c"
)

SPD_BYTES = bytes.fromhex(
    "0a3e0a1b090000000000007940110000000000407a4019000000000000244012"
    "18000000000000f03f000000000000004000000000000008401a056669786564"
    "11000000000000d03f1a1b090000000000002440110000000000003440190000"
    "000000003e40221209000000000000d03f11000000000000e03f2a1209000000"
    "000064b94011fa7e6abc7493683f310000000000308140390000000000001840"
    "420946495845442d5350444a1b0a19323032342d30312d30325430333a30343a"
    "30352b30303a3030519a9999999999d93f"
)


def fixed_colorimeter(**kwargs: object) -> ColorimeterMeasurement:
    """A colorimeter reading with fixed values and no recomputation."""
    m = ColorimeterMeasurement(
        np.array([10.0, 20.0, 30.0]), 0.5, "FIXED-COL", no_compute=True, **kwargs  # type: ignore[arg-type]
    )
    m.xy = np.array([0.25, 0.5])
    m.cct = 6500.0
    m.duv = 0.003
    m.dominant_wl = 550.0
    m.purity = 0.4
    m.time = FIXED_TIME
    return m


def fixed_spd(**kwargs: object) -> SPDMeasurement:
    """A spectral reading with fixed values and no recomputation."""
    spd = SpectralDistribution(
        [1.0, 2.0, 3.0], domain=SpectralShape(400, 420, 10), name="fixed"
    )
    m = SPDMeasurement(spd, 0.25, "FIXED-SPD", no_compute=True, **kwargs)  # type: ignore[arg-type]
    m.XYZ = np.array([10.0, 20.0, 30.0])
    m.xy = np.array([0.25, 0.5])
    m.cct = 6500.0
    m.duv = 0.003
    m.dominant_wl = 550.0
    m.purity = 0.4
    m.power = 6.0
    m.time = FIXED_TIME
    return m


class TestByteCompatibility:
    def test_colorimeter_without_either_serializes_to_the_old_bytes(self):
        assert colorimeter_measurement_to_bytes(fixed_colorimeter()) == COLORIMETER_BYTES

    def test_spd_without_either_serializes_to_the_old_bytes(self):
        assert spd_measurement_to_bytes(fixed_spd()) == SPD_BYTES

    def test_empty_settings_and_no_status_write_nothing(self):
        proto = measurements_pb2.Colorimeter_Measurement.FromString(
            colorimeter_measurement_to_bytes(fixed_colorimeter(settings={}))
        )
        assert not proto.HasField("status")
        assert len(proto.settings) == 0

    def test_a_status_adds_bytes(self):
        with_status = colorimeter_measurement_to_bytes(
            fixed_colorimeter(status=STATUS)
        )
        assert with_status != COLORIMETER_BYTES
        assert len(with_status) > len(COLORIMETER_BYTES)

    def test_old_colorimeter_bytes_read_without_status_or_settings(self):
        m = colorimeter_measurement_from_bytes(COLORIMETER_BYTES)
        assert m.status is None
        assert dict(m.settings) == {}
        assert m == fixed_colorimeter()

    def test_old_spd_bytes_read_without_status_or_settings(self):
        m = spd_measurement_from_bytes(SPD_BYTES)
        assert m.status is None
        assert dict(m.settings) == {}
        assert m == fixed_spd()

    def test_old_hybrid_file_reads_without_status_or_settings(self, tmp_path: Path):
        file = measurements_pb2.CSFM_File()
        file.measurements.add().xyz.CopyFrom(
            measurements_pb2.Colorimeter_Measurement.FromString(COLORIMETER_BYTES)
        )
        file.measurements.add().spd.CopyFrom(
            measurements_pb2.SPD_Measurement.FromString(SPD_BYTES)
        )
        path = tmp_path / "old.csmf"
        path.write_bytes(file.SerializeToString())

        data = load_csmf_file(path)

        assert [m.status for m in data.measurements] == [None, None]
        assert [dict(m.settings) for m in data.measurements] == [{}, {}]


class TestRoundTrip:
    def test_colorimeter(self):
        m = fixed_colorimeter(status=STATUS, settings=SETTINGS)

        restored = colorimeter_measurement_from_bytes(colorimeter_measurement_to_bytes(m))

        assert restored.status == STATUS
        assert dict(restored.settings) == SETTINGS
        assert restored == m

    def test_spd(self):
        m = fixed_spd(status=STATUS, settings=SETTINGS)

        restored = spd_measurement_from_bytes(spd_measurement_to_bytes(m))

        assert restored.status == STATUS
        assert dict(restored.settings) == SETTINGS
        assert restored == m

    def test_status_alone(self):
        restored = colorimeter_measurement_from_bytes(
            colorimeter_measurement_to_bytes(fixed_colorimeter(status=STATUS))
        )
        assert restored.status == STATUS
        assert dict(restored.settings) == {}

    def test_settings_alone(self):
        restored = spd_measurement_from_bytes(
            spd_measurement_to_bytes(fixed_spd(settings=SETTINGS))
        )
        assert restored.status is None
        assert dict(restored.settings) == SETTINGS

    def test_a_bare_status_is_not_lost(self):
        """A clean ``OK00`` reply is a status, so it must not read back as None."""
        restored = colorimeter_measurement_from_bytes(
            colorimeter_measurement_to_bytes(
                fixed_colorimeter(status=ReadingStatus(code="OK00"))
            )
        )
        assert restored.status == ReadingStatus(code="OK00")

    def test_recompute_keeps_both(self):
        col = colorimeter_measurement_from_bytes(
            colorimeter_measurement_to_bytes(
                fixed_colorimeter(status=STATUS, settings=SETTINGS)
            ),
            recompute=True,
        )
        spd = spd_measurement_from_bytes(
            spd_measurement_to_bytes(fixed_spd(status=STATUS, settings=SETTINGS)),
            recompute=True,
        )

        for restored in (col, spd):
            assert restored.status == STATUS
            assert dict(restored.settings) == SETTINGS

    def test_legacy_spd_list_file(self, tmp_path: Path):
        rows = [fixed_spd(status=STATUS, settings=SETTINGS), fixed_spd()]
        data = CSMF_Data(
            measurements=np.asarray(rows, dtype=object),
            test_colors=np.zeros((2, 3)),
            order=np.arange(2),
            metadata=METADATA,
        )
        buffer = csmf_data_to_buffer(data)
        assert len(buffer.spd_measurements) == 2
        assert len(buffer.measurements) == 0

        restored = load_csmf_file(save_csmf_file(tmp_path / "legacy", data))

        assert restored.measurements[0].status == STATUS
        assert dict(restored.measurements[0].settings) == SETTINGS
        assert restored.measurements[1].status is None
        assert dict(restored.measurements[1].settings) == {}
        assert restored == data

    def test_hybrid_wrapper_file(self, tmp_path: Path):
        rows = [
            fixed_spd(status=STATUS, settings=SETTINGS),
            fixed_colorimeter(status=STATUS, settings=SETTINGS),
            fixed_colorimeter(),
        ]
        data = CSMF_Data(
            measurements=np.asarray(rows, dtype=object),
            test_colors=np.zeros((3, 3)),
            order=np.arange(3),
            metadata=METADATA,
        )
        assert len(csmf_data_to_buffer(data).measurements) == 3

        restored = load_csmf_file(save_csmf_file(tmp_path / "hybrid", data))

        assert [m.status for m in restored.measurements] == [STATUS, STATUS, None]
        assert [dict(m.settings) for m in restored.measurements] == [
            SETTINGS,
            SETTINGS,
            {},
        ]
        assert restored == data

    def test_recompute_load_of_a_file_keeps_both(self, tmp_path: Path):
        data = CSMF_Data(
            measurements=np.asarray(
                [fixed_colorimeter(status=STATUS, settings=SETTINGS)], dtype=object
            ),
            test_colors=np.zeros((1, 3)),
            order=np.arange(1),
        )
        path = save_csmf_file(tmp_path / "recompute", data)

        row = load_csmf_file(path, recompute=True).measurements[0]

        assert row.status == STATUS
        assert dict(row.settings) == SETTINGS


class TestShortname:
    def test_status_and_settings_stay_out_of_the_hash(self):
        shape = SpectralShape(380, 780, 5)
        ramp = np.linspace(0.1, 1.0, len(shape.wavelengths))

        def data(**kwargs: object) -> CSMF_Data:
            rows = [
                SPDMeasurement(
                    SpectralDistribution(scale * ramp, shape), 1.0, "fixed", **kwargs  # type: ignore[arg-type]
                )
                for scale in (1.0, 2.0, 3.0)
            ]
            return CSMF_Data(
                measurements=np.asarray(rows, dtype=object),
                test_colors=np.zeros((3, 3)),
                order=np.arange(3),
            )

        assert (
            data(status=STATUS, settings=SETTINGS).shortname == data().shortname
        )

    def test_pinned_name_is_unchanged(self):
        from specio.serialization.tests.test_csmf import FIXED_SHORTNAME

        assert FIXED_SHORTNAME == "2519f9ba"


def old_schema_file_class() -> type:
    """Build the CSFM_File message class from the schema before this change.

    The descriptor comes from the current one with the status and settings
    fields and the ``Reading_Status`` message removed, in a separate pool, so
    the class parses like a reader that predates them.
    """
    pool = descriptor_pool.DescriptorPool()
    common = descriptor_pb2.FileDescriptorProto()
    common_pb2.DESCRIPTOR.CopyToProto(common)
    pool.Add(common)

    proto = descriptor_pb2.FileDescriptorProto()
    measurements_pb2.DESCRIPTOR.CopyToProto(proto)
    new_fields = {"Colorimeter_Measurement": {18, 19}, "SPD_Measurement": {11, 12}}
    kept_messages = []
    for message in proto.message_type:
        if message.name == "Reading_Status":
            continue
        if message.name in new_fields:
            kept = [f for f in message.field if f.number not in new_fields[message.name]]
            assert len(kept) == len(message.field) - 2
            del message.field[:]
            message.field.extend(kept)
            del message.nested_type[:]  # drops the map entry types
        kept_messages.append(message)
    del proto.message_type[:]
    proto.message_type.extend(kept_messages)
    pool.Add(proto)
    return message_factory.GetMessageClass(
        pool.FindMessageTypeByName("specio.proto.CSFM_File")
    )


class TestOldReader:
    def test_old_schema_ignores_and_preserves_the_new_fields(self):
        OldFile = old_schema_file_class()
        fields = {f.number for f in OldFile.DESCRIPTOR.fields_by_name["measurements"].message_type.fields}
        assert fields == {1, 2}

        data = CSMF_Data(
            measurements=np.asarray(
                [
                    fixed_spd(status=STATUS, settings=SETTINGS),
                    fixed_colorimeter(status=STATUS, settings=SETTINGS),
                ],
                dtype=object,
            ),
            test_colors=np.zeros((2, 3)),
            order=np.arange(2),
        )
        new_bytes = csmf_data_to_buffer(data).SerializeToString()

        old = OldFile.FromString(new_bytes)

        spd_row, col_row = old.measurements
        assert spd_row.spd.spectrometer_id == "FIXED-SPD"
        assert col_row.xyz.colorimeter_id == "FIXED-COL"
        assert col_row.xyz.XYZ.Y == 20.0
        assert not hasattr(col_row.xyz, "status")
        assert not hasattr(col_row.xyz, "settings")
        # An old reader that rewrites the file keeps what it didn't know
        assert len(old.SerializeToString()) == len(new_bytes)
        rewritten = measurements_pb2.CSFM_File.FromString(old.SerializeToString())
        assert rewritten.measurements[1].xyz.status.code == "OK06"
        assert dict(rewritten.measurements[1].xyz.settings) == SETTINGS
