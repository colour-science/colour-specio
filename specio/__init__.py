"""
Specio
======
Provides support for interacting with various hardware spectrometers.
"""

__version__ = "0.2.9"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = (
    "MIT License - https://github.com/tjdcs/specio/blob/main/LICENSE.md"
)
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"


from .spectrometers.common import (
    RawSPDMeasurement,
    SPDMeasurement,
    VirtualSpectrometer,
)

__all__ = [
    "SPDMeasurement",
    "RawSPDMeasurement",
    "VirtualSpectrometer",
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
