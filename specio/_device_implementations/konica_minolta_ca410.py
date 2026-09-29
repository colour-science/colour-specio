"""
Define classes and functions for controlling the Konica Minolta CA-410 display
color analyzer.

The driver talks to a CA-410 probe connected directly over USB or RS-232C, using
the ASCII protocol in the *CA-410 Communication Specifications* published by
Konica Minolta.
"""

# cspell:ignore comports SEVENBITS STOPBITS

from collections.abc import Mapping
from enum import IntEnum, IntFlag
from functools import cached_property
from textwrap import dedent
from types import MappingProxyType
from typing import final

import numpy as np
import serial
from serial.tools import list_ports

from specio.common.colorimeters import Colorimeter, RawColorimeterMeasurement
from specio.common.exceptions import DeviceError
from specio.common.utility import specio_warning

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "CA410",
    "UNKNOWN_EXPOSURE",
    "CA410Error",
    "MeasurementStatus",
    "ZeroCalibrationStatus",
    "candidate_ports",
]

USB_VENDOR_ID = 0x132B
"""Konica Minolta USB vendor ID."""

USB_PRODUCT_ID = 0x210D
"""USB product ID of a CA-410 probe."""

DELIMITER = b"\r"
"""Terminator for every command and reply."""

RESPONSE_TIMEOUT = 35
"""Seconds to wait for a reply.

The specification's worst case for one color measurement is about 30 seconds,
under INTERNAL or EXTERNAL synchronization. Zero calibration takes about 10.
"""

UNKNOWN_EXPOSURE = -1.0
"""Exposure recorded for every measurement, because the CA-410 does not report
its integration time."""

ERROR_MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        "ER10": "Command error",
        "ER20": "EXTERNAL synchronization signal missing or out of range",
        "ER21": "Zero calibration error: light not fully blocked",
        "ER22": "The measurement target is beyond the measurable range",
        "ER24": "Tcp or dominant wavelength cannot be calculated",
        "ER31": "Memory error",
        "ER32": "Memory error",
        "ER50": "FMA flicker exceeded 999.9%",
        "ER51": "FMA flicker synchronization frequency out of range",
        "ER53": "The probe cannot measure flicker",
        "ER99": "Firmware error",
    }
)


class CA410Error(DeviceError):
    """Raised when the CA-410 replies with an error code or does not reply."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class MeasurementStatus(IntFlag):
    """Conditions reported by a successful reply.

    The number in an ``OKnn`` reply is the sum of these flags, so ``OK06`` means
    both a temperature shift and a reading below the guaranteed range.
    """

    CALIBRATION_PROBE_MISMATCH = 1
    TEMPERATURE_SHIFT = 2
    BELOW_GUARANTEED_RANGE = 4
    NO_PERIODICITY = 8
    BATTERY_LOW = 64


class ZeroCalibrationStatus(IntEnum):
    """Zero calibration state reported by ``STR,23``."""

    NOT_EXECUTED = 0
    RECOMMENDED = 1
    COMPLETED = 2


def candidate_ports() -> list[str]:
    """List serial ports whose USB vendor and product IDs match a CA-410 probe.

    Returns
    -------
    list[str]
        Device paths of matching ports.
    """
    return [
        p.device
        for p in list_ports.comports()
        if p.vid == USB_VENDOR_ID and p.pid == USB_PRODUCT_ID
    ]


@final
class CA410(Colorimeter):
    """A Konica Minolta CA-410 probe connected directly to the host.

    Connecting reads the probe identity. If the probe has not been zero
    calibrated since power-on, connecting also runs zero calibration, because
    the probe rejects measurements until it has one.
    """

    SERIAL_KWARGS: Mapping = MappingProxyType(
        {
            "baudrate": 38400,
            "bytesize": serial.SEVENBITS,
            "parity": serial.PARITY_EVEN,
            "stopbits": serial.STOPBITS_TWO,
            "rtscts": True,
            "timeout": RESPONSE_TIMEOUT,
        }
    )

    @classmethod
    def discover(cls) -> "CA410":
        """Connect to the first CA-410 probe found by USB vendor and product ID.

        Returns
        -------
        CA410
            The connected probe.

        Raises
        ------
        serial.SerialException
            If no matching port answers the identity command.
        """
        for device in candidate_ports():
            try:
                return cls(device)
            except (CA410Error, serial.SerialException):
                continue

        raise serial.SerialException(
            dedent(
                """Couldn't find a CA-410 automatically. Make sure the probe is
                plugged in, or pass its port name to CA410()."""
            )
        )

    def __init__(self, port: serial.Serial | str) -> None:
        """Connect to a CA-410 probe and read its identity.

        Parameters
        ----------
        port : serial.Serial | str
            An open serial port, or the name of the port to open with
            :attr:`SERIAL_KWARGS`.

        Raises
        ------
        CA410Error
            If the probe does not answer or reports an error.
        """
        if isinstance(port, str):
            port = serial.Serial(port, **self.SERIAL_KWARGS)

        self._port = port
        self._port.reset_input_buffer()

        identity = self._write_cmd("IDO,0,1")
        self._product = identity[0]
        self._probe_model = identity[2].strip()
        self._firmware = identity[3]
        self._serial_number = identity[4]

        status = self.zero_calibration_status
        if status is ZeroCalibrationStatus.NOT_EXECUTED:
            self.zero_calibrate()
        elif status is ZeroCalibrationStatus.RECOMMENDED:
            specio_warning(
                "The CA-410 recommends zero calibration. Call zero_calibrate()."
            )

    def _write_cmd(self, cmd: str) -> list[str]:
        """Send one command and return the fields of its reply.

        Parameters
        ----------
        cmd : str
            The command without its delimiter, for example ``"MES,2"``.

        Returns
        -------
        list[str]
            The reply fields after the response code.

        Raises
        ------
        CA410Error
            If the reply is missing or carries an ``ER`` code.
        """
        self._port.write(cmd.encode() + DELIMITER)
        reply = self._port.read_until(DELIMITER)

        if not reply.endswith(DELIMITER):
            raise CA410Error(f"No response from the CA-410 to {cmd!r}")

        code, *fields = reply.removesuffix(DELIMITER).decode().split(",")

        if code.startswith("ER"):
            message = ERROR_MESSAGES.get(code, "Unknown error")
            raise CA410Error(f"CA-410 {code} on {cmd!r}: {message}", code)

        status = MeasurementStatus(int(code.removeprefix("OK")))
        if status:
            specio_warning(f"CA-410 {code} on {cmd!r}: {status!r}")

        return fields

    @property
    def serial_number(self) -> str:
        """The probe serial number."""
        return self._serial_number

    @property
    def manufacturer(self) -> str:
        """The device manufacturer, "Konica Minolta"."""
        return "Konica Minolta"

    @cached_property
    def model(self) -> str:
        """The product and probe model, for example "CA-410 CA-VP427A"."""
        return f"{self._product} {self._probe_model}"

    @property
    def firmware(self) -> str:
        """The probe firmware version, for example "Ver.1.80.0002"."""
        return self._firmware

    @property
    def zero_calibration_status(self) -> ZeroCalibrationStatus:
        """The zero calibration state of the probe."""
        return ZeroCalibrationStatus(int(self._write_cmd("STR,23")[0]))

    def zero_calibrate(self) -> None:
        """Run zero calibration, which closes and reopens the probe shutter.

        Raises
        ------
        CA410Error
            If the shutter does not block all light (``ER21``).
        """
        self._write_cmd("ZRC")

    def _raw_measure(self) -> RawColorimeterMeasurement:
        """Measure once and return absolute XYZ.

        ``MES,2`` appends X, Y and Z to the reply whatever the display mode, so
        the driver never changes the stored display mode.

        Returns
        -------
        RawColorimeterMeasurement
            XYZ in the probe's luminance unit, with :data:`UNKNOWN_EXPOSURE`.
        """
        fields = self._write_cmd("MES,2")
        XYZ = np.asarray([float(v) for v in fields[-3:]])

        return RawColorimeterMeasurement(
            XYZ=XYZ, exposure=UNKNOWN_EXPOSURE, device_id=self.readable_id
        )
