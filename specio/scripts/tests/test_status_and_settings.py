"""The CSMF scripts keep each row's status and settings."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np

from specio._device_implementations.virtual import (
    VirtualColorimeter,
    VirtualSpectrometer,
)
from specio.common import ReadingStatus
from specio.scripts import csmf_anonymize, csmf_doctor
from specio.serialization.csmf import (
    CSMF_Data,
    CSMF_Metadata,
    load_csmf_file,
    save_csmf_file,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

STATUS = ReadingStatus(
    code="OK04", message="BELOW_GUARANTEED_RANGE", flags=("BELOW_GUARANTEED_RANGE",)
)
SETTINGS = {"measurement_speed": "fast", "sync_mode": "ntsc"}


def recorded_data() -> CSMF_Data:
    """A hybrid file whose first two rows carry status and settings."""
    spd = VirtualSpectrometer().measure()
    col = VirtualColorimeter().measure()
    plain = VirtualColorimeter().measure()
    for row in (spd, col):
        row.status = STATUS
        row.settings = dict(SETTINGS)
    return CSMF_Data(
        measurements=np.asarray([spd, col, plain], dtype=object),
        test_colors=np.zeros((3, 3)),
        order=np.arange(3),
        metadata=CSMF_Metadata(notes="n", author="a", location="l", software="s"),
    )


def assert_recorded(data: CSMF_Data) -> None:
    assert [m.status for m in data.measurements] == [STATUS, STATUS, None]
    assert [dict(m.settings) for m in data.measurements] == [SETTINGS, SETTINGS, {}]


def test_anonymize_leaves_status_and_settings_alone(tmp_path: Path):
    """They hold instrument conditions, not personal data."""
    path = save_csmf_file(tmp_path / "recorded", recorded_data())

    assert_recorded(load_csmf_file(csmf_anonymize.main(str(path))))


def test_doctor_preserves_status_and_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The doctor reloads with ``recompute=True`` and writes the file back."""
    path = save_csmf_file(tmp_path / "recorded", recorded_data())
    monkeypatch.setattr(sys, "argv", ["csmf_doctor", str(path)])

    csmf_doctor.main()

    assert_recorded(load_csmf_file(path))
