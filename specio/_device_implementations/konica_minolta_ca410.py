"""
Define classes and functions for controlling the Konica Minolta CA-410 display
color analyzer.

The driver talks to a CA-410 probe connected directly over USB or RS-232C, using
the ASCII protocol in the *CA-410 Communication Specifications* published by
Konica Minolta.
"""

# cspell:ignore comports SEVENBITS STOPBITS footlambert

import math
import re
from collections.abc import Mapping
from enum import IntEnum, IntFlag
from functools import cached_property
from textwrap import dedent
from types import MappingProxyType
from typing import NamedTuple, final

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

PRODUCT_NAME = "CA-410"
"""Product name in the first field of the ``IDO`` reply (p. 27)."""

DELIMITER = b"\r"
"""Terminator for every command and reply."""

REPLY_CODE = re.compile(r"(OK|ER)[0-9]{2}")
"""Shape of the response code that opens every reply."""

COMMUNICATION_TIME = 1.5
"""Seconds the specification allows for communication in every reply.

The *Timeout Duration* section of the specification (p. 9) adds this term to
every measurement timeout.
"""

LONGEST_SYNCHRONIZED_MEASUREMENT = 4.0
"""Seconds one color or FMA flicker measurement takes at most.

This is the INTERNAL and EXTERNAL entry of tables A and B (p. 9), and the
longest MANUAL measurement time the ``SCS`` command accepts (p. 39).
"""

LOWEST_JEITA_SAMPLING_FREQUENCY = 0.07
"""Lowest JEITA sampling frequency in hertz that ``JCS`` (p. 51) and ``ACS``
(p. 53) accept, which gives the longest JEITA measurement."""


def _timeout_duration(
    one_measurement: float,
    retries_a: int,
    total_retry_time: float,
    calculation_time: float,
    retries_b: int,
) -> float:
    """Apply the specification's timeout formula for individual measurements.

    The formula is in the *Timeout Duration* section (p. 9). The driver never
    averages, so the number of averaged measurements is 1.

    Parameters
    ----------
    one_measurement : float
        Seconds for one measurement.
    retries_a : int
        Maximum number of retries A.
    total_retry_time : float
        Total retry time in seconds.
    calculation_time : float
        Calculation time in seconds.
    retries_b : int
        Maximum number of retries B.

    Returns
    -------
    float
        Seconds to wait for the reply.
    """
    return (
        one_measurement * retries_a + total_retry_time + calculation_time
    ) * retries_b + COMMUNICATION_TIME


QUERY_TIMEOUT = COMMUNICATION_TIME
"""Seconds to wait for the reply to a query such as ``IDO`` or ``STR``.

A query measures nothing, so only the specification's communication time
(p. 9) applies. A port that is not a CA-410 therefore fails identification
quickly.
"""

MEASURE_TIMEOUT = max(
    _timeout_duration(
        one_measurement=LONGEST_SYNCHRONIZED_MEASUREMENT,
        retries_a=1,
        total_retry_time=0,
        calculation_time=0.01,
        retries_b=7,
    ),
    _timeout_duration(
        one_measurement=LONGEST_SYNCHRONIZED_MEASUREMENT,
        retries_a=7,
        total_retry_time=0.6,
        calculation_time=0.01,
        retries_b=1,
    ),
    _timeout_duration(
        one_measurement=1 / LOWEST_JEITA_SAMPLING_FREQUENCY,
        retries_a=5,
        total_retry_time=0.6,
        calculation_time=1,
        retries_b=1,
    ),
)
"""Seconds to wait for the reply to ``MES``.

The rows of the timeout table (p. 9) give about 30 seconds for color, 30 for
FMA flicker and 75 for JEITA flicker at the lowest sampling frequency. A
simultaneous color and flicker measurement needs the longer of its two
timeouts (p. 9), and the color result waits for the JEITA measurement to
finish (``MMS``, p. 45; ``MES``, p. 102). The driver doesn't change the stored
flicker settings, so it allows the longest row.
"""

ZERO_CALIBRATION_TIMEOUT = MEASURE_TIMEOUT
"""Seconds to wait for the reply to ``ZRC``.

The specification gives no duration for zero calibration (p. 75), so the driver
allows it the measurement worst case. A CA-VP427A takes about 10 seconds.
"""

FOOT = 0.3048
"""Metres in one international foot (NIST SP 811, Appendix B.8)."""

CANDELAS_PER_SQUARE_METRE_PER_FOOTLAMBERT = 1 / (math.pi * FOOT**2)
"""Candelas per square metre in one footlambert.

A footlambert is 1/π candela per square foot, about 3.426 cd/m². NIST SP 811,
Appendix B.8, lists the factor as 3.426 259.
"""

LUMINANCE_SCALE: Mapping[str, float] = MappingProxyType(
    {"0": CANDELAS_PER_SQUARE_METRE_PER_FOOTLAMBERT, "1": 1.0}
)
"""Factor that converts a reply in each ``STR,6`` luminance unit to cd/m².

``STR,6`` returns 0 for fL and 1 for cd/m² (p. 62).
"""

UNKNOWN_EXPOSURE = -1.0
"""Exposure recorded for every measurement, because the CA-410 does not report
its integration time."""

ERROR_MESSAGES: Mapping[str, str] = MappingProxyType(
    {
        "ER03": "Invalid color difference or user calibration target value",
        "ER05": "User calibration failed: values were not all entered",
        "ER06": "User calibration failed: invalid measurement or target value",
        "ER10": "Command error, or zero calibration has not been executed",
        "ER16": "Calibration channel write failed: invalid data",
        "ER20": "EXTERNAL synchronization signal missing or out of range",
        "ER21": "Zero calibration error: light not fully blocked",
        "ER22": "The measurement target is beyond the measurable range",
        "ER24": "Tcp or dominant wavelength cannot be calculated",
        "ER31": "Memory error",
        "ER32": "Memory error",
        "ER50": "FMA flicker exceeded 999.9%",
        "ER51": "FMA flicker synchronization frequency out of range",
        "ER53": "The probe cannot measure flicker",
        "ER91": "Periodical calibration recommended date not set",
        "ER99": "Firmware error",
    }
)


class CA410Error(DeviceError):
    """Raised when the CA-410 sends no reply, an error code or a malformed reply."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class _UnidentifiedPortError(CA410Error):
    """Raised when a port does not identify itself as a CA-410."""


class Command(NamedTuple):
    """A command the driver sends, and the shape of its successful reply."""

    text: str
    """The command without its delimiter, for example ``"MES,2"``."""

    fields: int
    """Number of fields that follow the response code in an ``OK`` reply."""

    timeout: float
    """Seconds to wait for the reply."""


IDENTIFY = Command("IDO,0,1", fields=6, timeout=QUERY_TIMEOUT)
"""Read the product, variation, model, firmware, serial and custom numbers."""

GET_LUMINANCE_UNIT = Command("STR,6", fields=1, timeout=QUERY_TIMEOUT)
"""Read the luminance unit that replies use."""

GET_ZERO_CALIBRATION_STATUS = Command("STR,23", fields=1, timeout=QUERY_TIMEOUT)
"""Read the zero calibration state."""

ZERO_CALIBRATE = Command("ZRC", fields=0, timeout=ZERO_CALIBRATION_TIMEOUT)
"""Run zero calibration."""

MEASURE = Command("MES,2", fields=10, timeout=MEASURE_TIMEOUT)
"""Measure, and append absolute X, Y and Z to the reply."""

XYZ_FIELDS = slice(7, 10)
"""Positions of X, Y and Z among the fields of an ``MES,2`` reply.

X, Y and Z are receive parameters [8] to [10] (p. 101-102).
"""

NO_VALUE = -99999999.0
"""Value the CA-410 sends in a reply field that holds no result (p. 101)."""


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

    Measurements are always in cd/m². The probe stores its luminance unit
    across power cycles (``LUS``, p. 74), and replies use that unit, so
    connecting reads it (``STR,6``, p. 62) and the driver converts fL replies
    to cd/m².
    """

    SERIAL_KWARGS: Mapping = MappingProxyType(
        {
            "baudrate": 38400,
            "bytesize": serial.SEVENBITS,
            "parity": serial.PARITY_EVEN,
            "stopbits": serial.STOPBITS_TWO,
            "rtscts": True,
            "timeout": QUERY_TIMEOUT,
        }
    )

    @classmethod
    def discover(cls) -> "CA410":
        """Connect to the first CA-410 probe found by USB vendor and product ID.

        Ports that can't be opened, or that don't identify themselves as a
        CA-410, are skipped. Once a port identifies as a CA-410, errors from
        connecting to it propagate.

        Returns
        -------
        CA410
            The connected probe.

        Raises
        ------
        serial.SerialException
            If no matching port identifies itself as a CA-410.
        CA410Error
            If a CA-410 fails to connect, for example because zero calibration
            fails.
        """
        for device in candidate_ports():
            try:
                port = serial.Serial(device, **cls.SERIAL_KWARGS)
            except serial.SerialException:
                continue

            try:
                return cls(port)
            except BaseException as e:
                port.close()
                if not isinstance(e, _UnidentifiedPortError):
                    raise

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
            :attr:`SERIAL_KWARGS`. The driver sets the port timeout before
            each command. If the driver opened the port and connecting fails,
            it closes the port again.

        Raises
        ------
        CA410Error
            If the device is not a CA-410, does not answer, answers with a
            malformed reply, or reports an error.
        """
        opened_here = isinstance(port, str)
        if isinstance(port, str):
            port = serial.Serial(port, **self.SERIAL_KWARGS)

        self._port = port
        try:
            self._connect()
        except BaseException:
            if opened_here:
                port.close()
            raise

    def _connect(self) -> None:
        """Identify the probe, read its luminance unit, and zero calibrate it.

        Raises
        ------
        CA410Error
            If the device does not identify itself as a CA-410, reports an
            undefined luminance unit, or zero calibration fails.
        """
        try:
            identity = self._write_cmd(IDENTIFY)
        except CA410Error as e:
            raise _UnidentifiedPortError(
                f"{self._port.name} did not identify as a CA-410: {e}", e.code
            ) from e

        if identity[0] != PRODUCT_NAME:
            raise _UnidentifiedPortError(
                f"{self._port.name} identifies as {identity[0]!r}, not a CA-410"
            )

        self._product = identity[0]
        self._probe_model = identity[2].strip()
        self._firmware = identity[3]
        self._serial_number = identity[4]

        (unit,) = self._write_cmd(GET_LUMINANCE_UNIT)
        try:
            self._luminance_scale = LUMINANCE_SCALE[unit]
        except KeyError as e:
            raise CA410Error(f"Undefined CA-410 luminance unit {unit!r}") from e

        status = self.zero_calibration_status
        if status is ZeroCalibrationStatus.NOT_EXECUTED:
            self.zero_calibrate()
        elif status is ZeroCalibrationStatus.RECOMMENDED:
            specio_warning(
                "The CA-410 recommends zero calibration. Call zero_calibrate()."
            )

    def _write_cmd(self, cmd: Command) -> list[str]:
        """Send one command and return the fields of its reply.

        Input left over from an earlier command is discarded first, so a stale
        reply can't answer this command. A reply whose shape doesn't match the
        command raises instead of being parsed.

        Parameters
        ----------
        cmd : Command
            The command to send.

        Returns
        -------
        list[str]
            The reply fields after the response code.

        Raises
        ------
        CA410Error
            If the reply is missing, malformed, or carries an ``ER`` code.
        """
        self._port.reset_input_buffer()
        self._port.timeout = cmd.timeout
        self._port.write(cmd.text.encode() + DELIMITER)
        reply = self._port.read_until(DELIMITER)

        if not reply.endswith(DELIMITER):
            raise CA410Error(f"No response from the CA-410 to {cmd.text!r}: {reply!r}")

        malformed = f"Malformed reply from the CA-410 to {cmd.text!r}: {reply!r}"
        try:
            code, *fields = reply.removesuffix(DELIMITER).decode("ascii").split(",")
        except UnicodeDecodeError as e:
            raise CA410Error(malformed) from e

        if not REPLY_CODE.fullmatch(code):
            raise CA410Error(malformed)

        if code.startswith("ER"):
            message = ERROR_MESSAGES.get(code, "Unknown error")
            raise CA410Error(f"CA-410 {code} on {cmd.text!r}: {message}", code)

        if len(fields) != cmd.fields:
            raise CA410Error(f"{malformed}, expected {cmd.fields} fields")

        status = MeasurementStatus(int(code.removeprefix("OK")))
        if status:
            specio_warning(f"CA-410 {code} on {cmd.text!r}: {status!r}")

        return fields

    @property
    def serial_number(self) -> str:
        """The probe serial number."""
        return self._serial_number

    @property
    def manufacturer(self) -> str:
        """The device manufacturer, "Konica-Minolta"."""
        return "Konica-Minolta"

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
        (value,) = self._write_cmd(GET_ZERO_CALIBRATION_STATUS)
        try:
            return ZeroCalibrationStatus(int(value))
        except ValueError as e:
            raise CA410Error(
                f"Undefined CA-410 zero calibration status {value!r}"
            ) from e

    def zero_calibrate(self) -> None:
        """Run zero calibration, which closes and reopens the probe shutter.

        Raises
        ------
        CA410Error
            If the shutter does not block all light (``ER21``).
        """
        self._write_cmd(ZERO_CALIBRATE)

    def _raw_measure(self) -> RawColorimeterMeasurement:
        """Measure once and return absolute XYZ in cd/m².

        ``MES,2`` appends X, Y and Z to the reply whatever the display mode, so
        the driver never changes the stored display mode. If the probe's
        luminance unit is fL, the driver converts XYZ to cd/m².

        Returns
        -------
        RawColorimeterMeasurement
            XYZ in cd/m², with :data:`UNKNOWN_EXPOSURE`.

        Raises
        ------
        CA410Error
            If the reply is malformed, reports an error, or holds
            :data:`NO_VALUE` in place of X, Y or Z.
        """
        fields = self._write_cmd(MEASURE)
        try:
            XYZ = np.asarray([float(v) for v in fields[XYZ_FIELDS]])
        except ValueError as e:
            raise CA410Error(f"Non-numeric XYZ from the CA-410: {fields!r}") from e

        if np.any(XYZ == NO_VALUE):
            raise CA410Error(f"The CA-410 returned no value for XYZ: {fields!r}")

        return RawColorimeterMeasurement(
            XYZ=XYZ * self._luminance_scale,
            exposure=UNKNOWN_EXPOSURE,
            device_id=self.readable_id,
        )
