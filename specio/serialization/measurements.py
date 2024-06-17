"""
Provides serialization for Measurement Classes
"""

import datetime
from typing import cast

import numpy as np
from colour import SpectralDistribution, SpectralShape

from specio.colorimeters.common import ColorimeterMeasurement
from specio.serialization.protobuf import common_pb2, measurements_pb2
from specio.spectrometers.common import SPDMeasurement


def colorimeter_measurement_to_proto(
    col: ColorimeterMeasurement,
) -> measurements_pb2.Colorimeter_Measurement:
    buf = measurements_pb2.Colorimeter_Measurement(
        XYZ=common_pb2.XYZ_value(X=col.XYZ[0], Y=col.XYZ[1], Z=col.XYZ[2]),
        xy=common_pb2.xy_value(x=col.xy[0], y=col.xy[1]),
        cct=common_pb2.cct_value(cct=col.cct, duv=col.duv),
        dominant_wl=col.dominant_wl,
        purity=col.purity,
        time=common_pb2.Timestamp(timestr=col.time.isoformat()),
        exposure=col.exposure,
        colorimeter_id=col.device_id,
    )
    return buf


def colorimeter_measurement_to_bytes(col: ColorimeterMeasurement) -> bytes:
    return colorimeter_measurement_to_proto(col).SerializeToString()


def colorimeter_measurement_from_bytes(
    buffer: bytes | measurements_pb2.Colorimeter_Measurement,
    recompute: bool = False,
) -> ColorimeterMeasurement:
    if isinstance(buffer, bytes):
        buffer = measurements_pb2.Colorimeter_Measurement.FromString(buffer)
    buffer = cast(measurements_pb2.Colorimeter_Measurement, buffer)
    cm = ColorimeterMeasurement(
        XYZ=np.asarray((buffer.XYZ.X, buffer.XYZ.Y, buffer.XYZ.Z)),
        exposure=buffer.exposure,
        device_id=buffer.colorimeter_id,
        no_compute=not recompute,
    )

    if not recompute:
        cm.cct = buffer.cct.cct
        cm.duv = buffer.cct.duv
        cm.xy = np.asarray((buffer.xy.x, buffer.xy.y))
        cm.dominant_wl = buffer.dominant_wl
        cm.purity = buffer.purity
    cm.time = datetime.datetime.fromisoformat(buffer.time.timestr)
    return cm


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
        purity=spd.purity,
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
        ret.purity = buffer.purity
        ret.power = buffer.power
    ret.time = datetime.datetime.fromisoformat(buffer.time.timestr)
    return ret
