"""
Data serialization and persistence for specio measurements.
"""

from .csmf import (
    CSMF_Data,
    CSMF_Metadata,
    csmf_data_to_buffer,
    load_csmf_file,
    save_csmf_file,
)
from .measurements import (
    colorimeter_measurement_from_bytes,
    colorimeter_measurement_to_bytes,
    colorimeter_measurement_to_proto,
    spd_measurement_from_bytes,
    spd_measurement_to_bytes,
    spd_measurement_to_proto,
)
from .spectral import buffer_to_sd, buffer_to_sd_shape, sd_shape_to_buffer, sd_to_buffer

__version__ = "0.4.1.post0"
__author__ = "Tucker Downs"
__copyright__ = "Copyright 2022 Specio Developers"
__license__ = "BSD-3-Clause"
__maintainer__ = "Tucker Downs"
__email__ = "tucker@tjdcs.dev"
__status__ = "Development"

__all__ = [
    "CSMF_Data",
    "CSMF_Metadata",
    "buffer_to_sd",
    "buffer_to_sd_shape",
    "colorimeter_measurement_from_bytes",
    "colorimeter_measurement_to_bytes",
    "colorimeter_measurement_to_proto",
    "csmf_data_to_buffer",
    "load_csmf_file",
    "save_csmf_file",
    "sd_shape_to_buffer",
    "sd_to_buffer",
    "spd_measurement_from_bytes",
    "spd_measurement_to_bytes",
    "spd_measurement_to_proto",
]
