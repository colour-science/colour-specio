from typing import Any

from aenum import Enum, MultiValueEnum
from dataclasses import dataclass

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"


class InstrumentType(MultiValueEnum):
    """
    Identifies the type of instrument
    =====
    0: Photometer
    1: Colorimeter
    2: Spectroradiometer
    """

    PHOTOMETER = 0, "0"
    COLORIMETER = 1, "1"
    SPECTRORADIOMETER = 2, "2"


class MeasurementSpeed(MultiValueEnum):
    """
    Controls the measurement speed when the CR Exposure Mode is set to "auto"
    """

    SLOW = 0, "0", "slow"
    NORMAL = 1, "1", "normal"
    FAST = 2, "2", "fast"
    FAST_2X = 3, "3", "2x fast"


class Model(Enum):
    """
    Identifies the CR model
    =====
    Values are based on the response to "RC Model" command.
    """

    CR300 = "CR-300"
    CR250 = "CR-250"


class ResponseType(Enum):
    """
    Identifies the success / failure of any CR command.
    """

    error = "ER"
    ok = "OK"


class ResponseCode(MultiValueEnum):
    """
    Error codes for Colorimetry Research CR-300 and other model spectrometers
    =====
    """

    OK = 0
    INVALID_COMMAND = -500

    TOO_DARK = 100
    CANT_SYNC_CONST = 101
    CANT_SYNC_AUTO = 102
    SYNC_TOO_LOW = 103

    INVALID_SYNC_MODE = -300, -521
    INVALID_SYNC_PERIOD = -301
    CANT_SYNC_TO_LIGHT = -302

    LIGHT_INTENSITY_FLUCTUATION = -303
    LIGHT_INTENSITY_TOO_LOW = -304
    LIGHT_INTENSITY_UNMEASURABLE = -305
    LIGHT_INTENSITY_TOO_HIGH = -306

    HARDWARE_MALFUNCTION = -331
    MATRIX_VERSION_MISMATCH = -332
    INVALID_MATRIX_INDEX = -333

    NO_CIE_TABLES = -334
    NO_CMF_TABLES = -335

    NO_MATRIX_FOR_ID = -336

    DUPLICATE_FILTER_SELECTION = -505
    NO_ACCESSORY_FOR_INDEX = -506
    NO_FILTER_FOR_INDEX = -507
    INDEX_NOT_VALID_ACCESSORY = -508
    INDEX_NOT_VALID_FILTER = -509, -510, -511

    INVALID_RANGE_MODE = -512
    INVALID_RANGE_INDEX = -513
    INVALID_EXPOSURE_MULTIPLIER = -514

    INDEX_DOESNT_SELECT_APERTURE = -515

    INVALID_EXPOSURE_MODE = -518
    INVALID_EXPOSURE_VALUE = -519

    INVALID_SYNC_FREQUENCY = -522

    INVALID_MATRIX_MODE = -552
    INVALID_MATRIX_ID = -553
    INVALID_MATRIX_NAME = -555

    ERRROR_SAVING_MATRIX_FLASH = -559
    INVALID_USER_CALIBRATION_MODE = -560

    RESERVED = -999

    @classmethod
    def _missing_(cls, _: object) -> Any:
        """
        Set the default error code to RESERVED
        =======================================
        """
        return cls.RESERVED


@dataclass
class CommandResponse:
    """
    Response data from Colorimetry Research
    """

    type: ResponseCode
    code: ResponseCode
    description: str
    arguments: list[str]


class CommandError(Exception):
    """
    Describes an issue with sending a command to CR
    """

    def __init__(self, response: CommandResponse, *args: object) -> None:
        self.response = response
        super().__init__(*args)
