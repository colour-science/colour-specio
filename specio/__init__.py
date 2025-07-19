"""
Specio
======
Provides support for interacting with various hardware spectrometers.
"""

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"


from ._device_implementations import konica_minolta
from ._device_implementations.colorimetry_research import colorimetry_research
from .common.colorimeters import ColorimeterMeasurement
from .common.spectrometers import (
    SPDMeasurement,
)

__all__ = [
    "ColorimeterMeasurement",
    "SPDMeasurement",
    "colorimetry_research",
    "konica_minolta",
]


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


_config__specio_logger()
