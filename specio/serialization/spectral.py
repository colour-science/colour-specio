from typing import cast

import numpy as np
from colour import SpectralDistribution, SpectralShape

from specio.serialization.protobuf import common_pb2

__all__ = [
    "sd_to_buffer",
    "buffer_to_sd",
    "sd_shape_to_buffer",
    "buffer_to_sd_shape",
]


def sd_shape_to_buffer(shape: SpectralShape) -> common_pb2.SpectralShape:
    """Convert SpectralShape to buffer. Defaults to bytes but may optionally
    return protobuf object

    Parameters
    ----------
    shape : SpectralShape
        The spectral shape to convert
    return_pb : bool, optional
        Change return type, by default False

    Returns
    -------
    bytes | protobuf.SpectralShape
        SpectralShape, serialized to `bytes` unless `return_pb` is True

    See Also
    --------
    `buffer_to_sd_shape`
    """
    pb = common_pb2.SpectralShape()
    pb.start = shape.start
    pb.end = shape.end
    pb.step = shape.interval

    return pb


def buffer_to_sd_shape(
    buffer: bytes | common_pb2.SpectralShape,
) -> SpectralShape:
    """
    Convert buffer back to `SpectralDistribution`

    Parameters
    ----------
    buffer : bytes | protobuf.SpectralShape
        the buffer to convert. Buffer must be serialized by sd_shape_to_buffer
        or compatible external program.

    Returns
    -------
    SpectralShape

    See Also
    --------
    `sd_shape_to_buffer`
    """

    if isinstance(buffer, bytes):
        buffer = common_pb2.SpectralShape.FromString(buffer)
    buffer = cast(common_pb2.SpectralShape, buffer)

    return SpectralShape(start=buffer.start, end=buffer.end, interval=buffer.step)


def sd_to_buffer(
    sd: SpectralDistribution, return_pb: bool = False
) -> bytes | common_pb2.SpectralDistribution:
    """Convert a `SpectralDistribution` object to a buffer.

    Parameters
    ----------
    sd : SpectralDistribution
        The spectral distribution to convert
    return_pb: bool = False
        changes return type to python protobuf object

    Returns
    -------
    bytes
        a byte or proto buffer that can be decoded back into a SpectralDistribution
        object via `specio.io.sd_from_buffer`
    """

    pb = common_pb2.SpectralDistribution()
    pb.name = sd.name

    pb.shape = sd_shape_to_buffer(sd.shape)

    pb.values.extend(sd.values.astype(np.double).tolist())
    pb.name = sd.name

    return pb if return_pb else pb.SerializeToString()


def buffer_to_sd(
    buffer: bytes | common_pb2.SpectralDistribution,
) -> SpectralDistribution:
    """Try to convert a byte buffer to SpectralDistribution

    Parameters
    ----------
    buffer : bytes
        The buffer to convert. Must come from `sd_to_buffer`

    Returns
    -------
    SpectralDistribution
        The spectral distribution

    Raises
    ------
    NotImplementedError
        _description_
    """

    if isinstance(buffer, bytes):
        pb = common_pb2.SpectralDistribution()
        pb.ParseFromString(buffer)
        buffer = pb
    pb = cast(common_pb2.SpectralDistribution, buffer)

    shape = buffer_to_sd_shape(pb.shape)
    values = pb.values if len(pb.values) > 0 else pb.values_old

    return SpectralDistribution(
        data=values,
        domain=shape,
        name=pb.name,
    )
