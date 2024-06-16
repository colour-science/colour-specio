"""
Provides serialization for Measurement Classes
"""

import datetime
from typing import cast

import numpy as np
from colour import SpectralDistribution, SpectralShape

from specio.measurement import SPDMeasurement
from specio.serialization.protobuf import common_pb2, measurements_pb2


def spd_measurement_to_proto(
    spd: SPDMeasurement,
) -> measurements_pb2.SPD_Measurement:
    """
    Transform input :class:SPDMeasurement to a protobuf. Proto defined by
    specio/serialization/protobuf/measurements.proto

    Parameters
    ----------
    spd : SPDMeasurement
        A complete measurement object

    Returns
    -------
    measurements_pb2.SPD_Measurement
        proto handle for serializing the SPD Data.
    """
    shape_buf = common_pb2.SpectralShape(
        start=spd.spd.shape.start,
        end=spd.spd.shape.end,
        step=spd.spd.shape.interval,
    )
    spd_buf = common_pb2.SpectralDistribution(
        shape=shape_buf, values=spd.spd.values, name=spd.spd.name
    )

    buf = measurements_pb2.SPD_Measurement(
        spd=spd_buf,
        exposure=spd.exposure,
        XYZ=common_pb2.XYZ_value(X=spd.XYZ[0], Y=spd.XYZ[1], Z=spd.XYZ[2]),
        xy=common_pb2.xy_value(x=spd.xy[0], y=spd.xy[1]),
        cct=common_pb2.cct_value(cct=spd.cct, duv=spd.duv),
        dominant_wl=spd.dominant_wl,
        power=spd.power,
        spectrometer_id=spd.spectrometer_id,
        time=common_pb2.Timestamp(timestr=spd.time.isoformat()),
    )
    return buf


def spd_measurement_to_bytes(spd: SPDMeasurement) -> bytes:
    """Transform input :class:SPDMeasurement to a bytes string. Returned byte
    string is readable as a protobuf defined by
    specio/serialization/protobuf/measurements.proto

    Parameters
    ----------
    spd : SPDMeasurement
        A complete measurement object

    Returns
    -------
    bytes
        a string of bytes serialized via measurements.proto
    """

    return spd_measurement_to_proto(spd).SerializeToString()


def spd_measurement_from_bytes(
    buffer: bytes | measurements_pb2.SPD_Measurement, recompute: bool = False
) -> SPDMeasurement:
    """Transform a bytes string or protobuffer handle to a SPDMeasurements
    object.

    Parameters
    ----------
    buffer : bytes | measurements_pb2.SPD_Measurement
        data string or protobuffer handle object.
    recompute : bool, optional
        Optionally recompute derivable data from the spectral data. Does not read
        XYZ, CCT, etc... from the data string. Default False

    Returns
    -------
    SPDMeasurement
        The measurement data de-serialized.

    See Also
    --------
    spd_measurement_to_bytes
    """
    if isinstance(buffer, bytes):
        buffer = measurements_pb2.SPD_Measurement.FromString(buffer)
    buffer = cast(measurements_pb2.SPD_Measurement, buffer)

    spd = SpectralDistribution(
        (
            buffer.spd.values
            if len(buffer.spd.values) > 0
            else buffer.spd.values_old
        ),
        domain=SpectralShape(
            buffer.spd.shape.start, buffer.spd.shape.end, buffer.spd.shape.step
        ),
    )

    ret = SPDMeasurement(
        spd, buffer.exposure, buffer.spectrometer_id, no_compute=not recompute
    )
    if not recompute:
        ret.cct = buffer.cct.cct
        ret.duv = buffer.cct.duv
        ret.XYZ = np.asarray((buffer.XYZ.X, buffer.XYZ.Y, buffer.XYZ.Z))
        ret.xy = np.asarray((buffer.xy.x, buffer.xy.y))
        ret.dominant_wl = buffer.dominant_wl
        ret.power = buffer.power
    ret.time = datetime.datetime.fromisoformat(buffer.time.timestr)
    return ret
