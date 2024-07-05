from specio.serialization.protobuf import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Colorimeter_Measurement(_message.Message):
    __slots__ = ("XYZ", "xy", "cct", "dominant_wl", "purity", "time", "exposure", "colorimeter_id")
    XYZ_FIELD_NUMBER: _ClassVar[int]
    XY_FIELD_NUMBER: _ClassVar[int]
    CCT_FIELD_NUMBER: _ClassVar[int]
    DOMINANT_WL_FIELD_NUMBER: _ClassVar[int]
    PURITY_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    EXPOSURE_FIELD_NUMBER: _ClassVar[int]
    COLORIMETER_ID_FIELD_NUMBER: _ClassVar[int]
    XYZ: _common_pb2.XYZ_value
    xy: _common_pb2.xy_value
    cct: _common_pb2.cct_value
    dominant_wl: float
    purity: float
    time: _common_pb2.Timestamp
    exposure: float
    colorimeter_id: str
    def __init__(self, XYZ: _Optional[_Union[_common_pb2.XYZ_value, _Mapping]] = ..., xy: _Optional[_Union[_common_pb2.xy_value, _Mapping]] = ..., cct: _Optional[_Union[_common_pb2.cct_value, _Mapping]] = ..., dominant_wl: _Optional[float] = ..., purity: _Optional[float] = ..., time: _Optional[_Union[_common_pb2.Timestamp, _Mapping]] = ..., exposure: _Optional[float] = ..., colorimeter_id: _Optional[str] = ...) -> None: ...

class SPD_Measurement(_message.Message):
    __slots__ = ("spd", "exposure", "XYZ", "xy", "cct", "dominant_wl", "purity", "power", "spectrometer_id", "time")
    SPD_FIELD_NUMBER: _ClassVar[int]
    EXPOSURE_FIELD_NUMBER: _ClassVar[int]
    XYZ_FIELD_NUMBER: _ClassVar[int]
    XY_FIELD_NUMBER: _ClassVar[int]
    CCT_FIELD_NUMBER: _ClassVar[int]
    DOMINANT_WL_FIELD_NUMBER: _ClassVar[int]
    PURITY_FIELD_NUMBER: _ClassVar[int]
    POWER_FIELD_NUMBER: _ClassVar[int]
    SPECTROMETER_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    spd: _common_pb2.SpectralDistribution
    exposure: float
    XYZ: _common_pb2.XYZ_value
    xy: _common_pb2.xy_value
    cct: _common_pb2.cct_value
    dominant_wl: float
    purity: float
    power: float
    spectrometer_id: str
    time: _common_pb2.Timestamp
    def __init__(self, spd: _Optional[_Union[_common_pb2.SpectralDistribution, _Mapping]] = ..., exposure: _Optional[float] = ..., XYZ: _Optional[_Union[_common_pb2.XYZ_value, _Mapping]] = ..., xy: _Optional[_Union[_common_pb2.xy_value, _Mapping]] = ..., cct: _Optional[_Union[_common_pb2.cct_value, _Mapping]] = ..., dominant_wl: _Optional[float] = ..., purity: _Optional[float] = ..., power: _Optional[float] = ..., spectrometer_id: _Optional[str] = ..., time: _Optional[_Union[_common_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CSFM_File(_message.Message):
    __slots__ = ("measurements", "spd_measurements", "test_colors", "order", "notes", "author", "location", "software", "ancillary")
    class Measurement(_message.Message):
        __slots__ = ("spd", "xyz")
        SPD_FIELD_NUMBER: _ClassVar[int]
        XYZ_FIELD_NUMBER: _ClassVar[int]
        spd: SPD_Measurement
        xyz: Colorimeter_Measurement
        def __init__(self, spd: _Optional[_Union[SPD_Measurement, _Mapping]] = ..., xyz: _Optional[_Union[Colorimeter_Measurement, _Mapping]] = ...) -> None: ...
    class TestColor(_message.Message):
        __slots__ = ("c", "f")
        C_FIELD_NUMBER: _ClassVar[int]
        F_FIELD_NUMBER: _ClassVar[int]
        c: _containers.RepeatedScalarFieldContainer[int]
        f: _containers.RepeatedScalarFieldContainer[float]
        def __init__(self, c: _Optional[_Iterable[int]] = ..., f: _Optional[_Iterable[float]] = ...) -> None: ...
    MEASUREMENTS_FIELD_NUMBER: _ClassVar[int]
    SPD_MEASUREMENTS_FIELD_NUMBER: _ClassVar[int]
    TEST_COLORS_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    SOFTWARE_FIELD_NUMBER: _ClassVar[int]
    ANCILLARY_FIELD_NUMBER: _ClassVar[int]
    measurements: _containers.RepeatedCompositeFieldContainer[CSFM_File.Measurement]
    spd_measurements: _containers.RepeatedCompositeFieldContainer[SPD_Measurement]
    test_colors: _containers.RepeatedCompositeFieldContainer[CSFM_File.TestColor]
    order: _containers.RepeatedScalarFieldContainer[int]
    notes: str
    author: str
    location: str
    software: str
    ancillary: bytes
    def __init__(self, measurements: _Optional[_Iterable[_Union[CSFM_File.Measurement, _Mapping]]] = ..., spd_measurements: _Optional[_Iterable[_Union[SPD_Measurement, _Mapping]]] = ..., test_colors: _Optional[_Iterable[_Union[CSFM_File.TestColor, _Mapping]]] = ..., order: _Optional[_Iterable[int]] = ..., notes: _Optional[str] = ..., author: _Optional[str] = ..., location: _Optional[str] = ..., software: _Optional[str] = ..., ancillary: _Optional[bytes] = ...) -> None: ...
