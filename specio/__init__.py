"""
Specio
======
Provides support for interacting with various hardware spectrometers.
"""
__version__ = "0.2.9"

from .measurement import Measurement, RawMeasurement
from .spectrometer import SpecRadiometer

__all__ = [
    "Measurement",
    "RawMeasurement",
    "SpecRadiometer",
]

__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tuckerd.info"
__status__ = "Development"


def _config__specio_logger() -> None:
    """
    Configure the default specio logger "specio"
    """
    import logging

    log = logging.getLogger("specio")

    stream_handler = logging.StreamHandler()
    stream_handler.formatter = logging.Formatter(
        fmt="[%(asctime)s.%(msecs)d] %(levelname)s - %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log.addHandler(stream_handler)
    log.setLevel("DEBUG")


_config__specio_logger()
