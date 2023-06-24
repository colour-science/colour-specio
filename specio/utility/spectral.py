from typing import cast
from specio import protobuf
from colour import SpectralDistribution, SpectralShape

import numpy as np


def sd_shape_to_buffer(
    shape: SpectralShape, return_pb: bool = False
) -> bytes | protobuf.SpectralShape:
    """Converts SpectralShape to buffer. Defaults to bytes but may optionally
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
    pb = protobuf.SpectralShape()
    pb.start = shape.start
    pb.end = shape.end
    pb.step = shape.interval

    return pb if return_pb else pb.SerializeToString()


def buffer_to_sd_shape(buffer: bytes | protobuf.SpectralShape) -> SpectralShape:
    """Convert buffer back to `SpectralDistribution`
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
    if issubclass(type(buffer), bytes):
        pb = protobuf.SpectralShape()
        pb.ParseFromString(buffer)  # type: ignore
        buffer = pb
    pb = cast(protobuf.SpectralShape, buffer)

    return SpectralShape(start=pb.start, end=pb.end, interval=pb.step)


def sd_to_buffer(
    sd: SpectralDistribution, return_pb: bool = False
) -> bytes | protobuf.SpectralDistribution:
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

    pb = protobuf.SpectralDistribution()
    pb.name = sd.name

    pb.shape.CopyFrom(
        cast(protobuf.SpectralShape, sd_shape_to_buffer(sd.shape, return_pb=True))
    )

    pb.values.extend(sd.values.astype(np.double).tolist())
    pb.name = sd.name

    return pb if return_pb else pb.SerializeToString()


def buffer_to_sd(buffer: bytes | protobuf.SpectralDistribution) -> SpectralDistribution:
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

    if issubclass(type(buffer), bytes):
        pb = protobuf.SpectralDistribution()
        pb.ParseFromString(buffer)  # type: ignore
        buffer = pb
    pb = cast(protobuf.SpectralDistribution, buffer)

    shape = buffer_to_sd_shape(pb.shape)
    values = pb.values if len(pb.values) > 0 else pb.values_old

    return SpectralDistribution(
        data=values,
        domain=shape,
        name=pb.name,
    )


__all__ = ["sd_to_buffer", "buffer_to_sd", "sd_shape_to_buffer", "buffer_to_sd_shape"]

if __name__ == "__main__":
    wl = np.arange(300, 700, 20)
    data = np.random.random(size=wl.shape)
    sd = SpectralDistribution(domain=wl, data=data)

    buffer = sd_to_buffer(sd)

    new_sd = buffer_to_sd(buffer)

    assert sd == new_sd
