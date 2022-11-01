from .CRSpectrometer import CRSpectrometer
from .CR_Definitions import (
    CommandError,
    CommandResponse,
    InstrumentType,
    MeasurementSpeed,
    Model,
    ResponseCode,
)

__all__ = [
    "CRSpectrometer",
    "CommandError",
    "CommandResponse",
    "InstrumentType",
    "MeasurementSpeed",
    "Model",
    "ResponseCode",
]

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"
