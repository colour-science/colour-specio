"""
Define classes and functions for controlling Konica-Minolta brand spectrometers,
namely the CS2000.
"""

import platform
import struct
import time
from collections.abc import Mapping
from enum import Enum
from functools import cached_property
from textwrap import dedent
from types import MappingProxyType
from typing import Any, NamedTuple, cast, final

import aenum
import serial
from colour import SpectralDistribution, SpectralShape
from serial.tools import list_ports
from serial.tools.list_ports_common import ListPortInfo

from specio.spectrometers.common import RawSPDMeasurement, SpecRadiometer

__all__ = []


class ResponseCode(aenum.MultiValueEnum):
    """Defines various CS2000 response codes and helpful error messages as a
    multivalue enum. Not all Enum instances have a second value. When
    present, the second value is a helpful message for users.

    The canonical value of each instance is the response code in `bytes`
    expected by the CS2000 serial protocol.
    """

    OK = b"OK00"

    MALFORMED_COMMAND = b"ER00", "The command string could not be interpreted"
    RESPONSE_NOT_READY = b"ER02", "Measurement response is not ready yet."
    OVER_EXPOSED = b"ER10", "Radiance too high for measurement mode"
    PARAMETER_ERROR = (
        b"ER17",
        "The command parameters could not be interpreted",
    )

    TEMPURTURE_ABNORMALITY_0 = b"ER51", "Device temperature abnormal. "
    TEMPURTURE_ABNORMALITY_1 = b"ER52", "Device temperature abnormal."

    SYNC_ERROR = b"ER71", "Could not synchronize to light source flicker"
    TARGET_ABNORMALITY = b"ER83", "Measurement Area Abnormality"

    RESERVED = b"ER--", "The response code could not be read by specio"

    @classmethod
    def _missing_(cls, _: object) -> Any:
        return cls.RESERVED


class CommandResponse(NamedTuple):
    """Internal Command Response representation for the CS2000 serial protocol"""

    code: ResponseCode
    data: tuple[bytes, ...]


class WriteCommandError(Exception):
    """Error thrown when there is an issue writing commands to a CS2000"""

    def __init__(
        self, message: str, cr: CommandResponse, *args: object
    ) -> None:
        super().__init__(message, *args)
        self.command_response = cr


class SyncMode(bytes, Enum):
    NO_SYNC = b"0"
    INTERNAL = b"1"
    EXTERNAL = b"2"


class SyncSpeedSetting(NamedTuple):
    mode: SyncMode
    frequency: float | None


class InternalNDMode(bytes, Enum):
    OFF = b"0"
    ON = b"1"
    AUTO = b"2"


class SpeedMode(bytes, Enum):
    NORMAL = b"0"
    FAST = b"1"
    MULTI_NORMAL = b"2"
    MULTI_FAST = b"4"
    MANUAL = b"3"


class SpeedModeSetting:
    @staticmethod
    def from_command_response(cr: CommandResponse):
        blist = cr.data
        mode = SpeedMode(blist[0])
        if mode in (SpeedMode.NORMAL, SpeedMode.FAST):
            nd_mode = InternalNDMode(blist[1])
            time = None
        elif mode in (SpeedMode.MULTI_FAST, SpeedMode.MULTI_NORMAL):
            time = int(blist[1].decode())
            nd_mode = InternalNDMode(blist[2])
        elif mode is SpeedMode.MANUAL:
            time = float(blist[1].decode()) / 1e6
            nd_mode = InternalNDMode(blist[2])

        return SpeedModeSetting(
            mode=mode, nd_mode=nd_mode, integration_time=time
        )

    def __init__(
        self,
        mode: SpeedMode,
        nd_mode: InternalNDMode = InternalNDMode.AUTO,
        integration_time: float | int | None = None,
    ):
        self.mode = mode
        self.nd_mode = nd_mode

        if mode in (SpeedMode.MULTI_NORMAL, SpeedMode.MULTI_FAST):
            if (
                integration_time is None
                or integration_time < 2
                or integration_time > 16
            ):
                raise ValueError(
                    f"""SpeedMode.{mode.name} requires integration_time time
                    to be between 2 and 16 integer seconds."""
                )
            self.time: int = int(round(integration_time))

        elif mode is SpeedMode.MANUAL:
            if (
                integration_time is None
                or integration_time < 0.005
                or integration_time > 120
            ):
                raise ValueError(
                    f"""SpeedMode.{mode.name} requires manual_integration time
                    to be between .005 and 120 seconds."""
                )
            self.time = int(round(integration_time * 1e6))

    def __bytes__(self):
        cmd_bytes = bytearray(self.mode + b",")
        if self.mode in (SpeedMode.MULTI_FAST, SpeedMode.MULTI_NORMAL):
            cmd_bytes += f"{self.time:02d},".encode()
        elif self.mode is SpeedMode.MANUAL:
            cmd_bytes += f"{self.time:09d},".encode()
        cmd_bytes += self.nd_mode
        return bytes(cmd_bytes)


DEFAULT_SPEED_MODE_SETTING = SpeedModeSetting(
    SpeedMode.NORMAL, InternalNDMode.AUTO, integration_time=None
)
HIGH_ACCURACY_MODE_SETTING = SpeedModeSetting(
    SpeedMode.MULTI_NORMAL, InternalNDMode.AUTO, integration_time=16
)


@final
class CS2000(SpecRadiometer):
    CS2000_SERIAL_KWARGS: Mapping = MappingProxyType(
        {
            "baudrate": 115200,
            "bytesize": 8,
            "parity": "N",
            "rtscts": True,
            "timeout": 1,
        }
    )

    @classmethod
    def discover(cls) -> "CS2000":
        """Attempt automatic discovery of the CS2000 serial port and return the
        CS2000 object.

        Returns
        -------
        CS2000
            A successfully automatic CS2000 object.

        Raises
        ------
        serial.SerialException
            If no serial port can be automatically linked.
        """

        if platform.system() == "Darwin":
            possible_ports = list_ports.grep("CS-2000")
        else:
            raise NotImplementedError(
                f"CS2000 device discovery is not implemented for {platform.system()}"
            )

        for p in possible_ports:
            p = cast(ListPortInfo, p)  # Typing for `Serial` is wrong

            sp = serial.Serial(p.device, **cls.CS2000_SERIAL_KWARGS)
            sp.read_all()
            sp.write(b"RMTS,1\n")
            response = sp.readline()

            if response == b"OK00\n":
                return CS2000(sp)

            # Normally called during gc but it's better to be explicit here.
            sp.close()

        raise serial.SerialException(
            dedent(
                """Couldn't find serial port automatically. Make sure the device is
                plugged in. Try finding the serial port manually with
                serial.list_ports.comports() or resetting the device."""
            )
        )

    def __init__(self, port: serial.Serial | str):
        """Connect to the CS2000 device at the specified serial port. Provides
        spectral measurement functionality and various functions for specifying
        the behavior / speed / etc... of the CS2000.

        Parameters
        ----------
        port : serial.Serial | str
            The serial port that the CS2000 should be connected on.
        """
        if isinstance(port, str):
            port = serial.Serial(port, **self.CS2000_SERIAL_KWARGS)

        self._port = port
        self._clear_buffer()
        self._write_cmd("RMTS,1")
        (
            self._manufacturer,
            self._model,
            self._serial_number,
        ) = self._get_identity()

    def _get_identity(self) -> tuple[str, str, str]:
        """
        Write the identify command and parse the results.

        Returns
        -------
        str
            The manufacturer string
        str
            The model string, should be one of "CS-2000" or "CS-2000A"
        str
            The serial number
        """
        _, identity_data = self._write_cmd("IDDR")

        make = "Konica-Minolta"

        if int(identity_data[1]) == 1:
            model = "CS-2000"
        elif int(identity_data[1]) == 2:
            model = "CS-2000A"
        else:
            model = identity_data[0].decode()

        sn = identity_data[2].decode()

        return make, model, sn

    def _clear_buffer(self):
        self._port.read_all()

    def _write_cmd(
        self, cmd: str | bytes, time_out: float = 0
    ) -> CommandResponse:
        if time_out > 0:
            old_timeout = self._port.timeout
            self._port.timeout = time_out

        encoded_cmd = bytearray(cmd.encode() if isinstance(cmd, str) else cmd)

        if encoded_cmd[-1] != b"\n":
            encoded_cmd = encoded_cmd + b"\n"

        self._port.write(encoded_cmd)
        response = self._port.readline()[:-1]
        response = response.split(b",")

        code = ResponseCode(response[0])
        data = response[1:]

        command_response = CommandResponse(code, tuple(data))

        if time_out > 0:
            self._port.timeout = old_timeout

        if code.value[0:2] != b"OK":
            additional_info = (
                code.values[1] if len(code.values) >= 2 else code.value
            )
            raise WriteCommandError(
                "There was an error with the CS2000 command. "
                + additional_info,
                command_response,
            )

        return command_response

    @property
    def serial_number(self) -> str:
        """The device serial number"""
        return self._serial_number

    @property
    def manufacturer(self) -> str:
        """
        The device manufacturer. Should be "Konica-Minolta"
        """
        return self._manufacturer

    @cached_property
    def model(self) -> str:
        """The model name"""
        return self._model

    @property
    def syncmode(self) -> SyncSpeedSetting:
        if hasattr(self, "_sync_speed_setting"):
            return self._sync_speed_setting

        _, data = self._write_cmd("SCMR")
        mode = SyncMode(data[0])
        frequency = float(data[1]) / 100 if mode is SyncMode.INTERNAL else None
        self._sync_speed_setting = SyncSpeedSetting(mode, frequency)

        return self._sync_speed_setting

    @syncmode.setter
    def syncmode(self, new_mode: SyncSpeedSetting):
        update_cmd_str = bytearray(b"SCMS," + new_mode.mode)
        if new_mode.mode is SyncMode.INTERNAL:
            if (
                new_mode.frequency is None
                or new_mode.frequency < 20
                or new_mode.frequency > 200
            ):
                raise ValueError(
                    "Sync mode Internal requires frequency between 20Hz and 200Hz"
                )

            update_cmd_str += (
                b"," + f"{round(new_mode.frequency * 100):.0f}".encode()
            )

        del self._sync_speed_setting
        self._write_cmd(update_cmd_str)

    @property
    def speedmode(self):
        if hasattr(self, "_cur_sms"):
            return self._cur_sms
        cr = self._write_cmd(b"SPMR")
        self._cur_sms = SpeedModeSetting.from_command_response(cr)
        return self._cur_sms

    @speedmode.setter
    def speedmode(self, cr: SpeedModeSetting):
        code, _ = self._write_cmd(b"SPMS," + bytes(cr))

    def _raw_measure(self) -> RawSPDMeasurement:
        # Additional timeout recommended by KM manual
        response = self._write_cmd("MEAS,1", time_out=10)
        wait_time = int(response.data[0])  # KM estimated measurement time
        time.sleep(wait_time + 0.1)

        while True:
            try:
                self._clear_buffer()
                _, conditions = self._write_cmd("MEDR,0,0,1")
                break
            except WriteCommandError as e:
                if e.command_response.code is ResponseCode.RESPONSE_NOT_READY:
                    time.sleep(0.5)
                    continue
                else:
                    raise e  # noqa: TRY201 Transparently re-raise original exception

        _, spd0 = self._write_cmd("MEDR,1,1,1")
        _, spd1 = self._write_cmd("MEDR,1,1,2")
        _, spd2 = self._write_cmd("MEDR,1,1,3")
        _, spd3 = self._write_cmd("MEDR,1,1,4")

        spd_data = [
            *[struct.unpack(">f", bytes.fromhex(d.decode()))[0] for d in spd0],
            *[struct.unpack(">f", bytes.fromhex(d.decode()))[0] for d in spd1],
            *[struct.unpack(">f", bytes.fromhex(d.decode()))[0] for d in spd2],
            *[struct.unpack(">f", bytes.fromhex(d.decode()))[0] for d in spd3],
        ]
        spd = SpectralDistribution(spd_data, SpectralShape(380, 780, 1))
        exposure = float(conditions[2]) * 1e-6

        return RawSPDMeasurement(
            spd=spd, exposure=exposure, spectrometer_id=self.readable_id
        )
