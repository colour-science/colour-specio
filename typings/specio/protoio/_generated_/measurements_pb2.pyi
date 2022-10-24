from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Colour_SDS(_message.Message):
    __slots__ = ["name", "shape", "values", "values_double"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SHAPE_FIELD_NUMBER: _ClassVar[int]
    VALUES_DOUBLE_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    name: str
    shape: Spectral_Shape
    values: _containers.RepeatedScalarFieldContainer[float]
    values_double: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, shape: _Optional[_Union[Spectral_Shape, _Mapping]] = ..., values_double: _Optional[_Iterable[float]] = ..., values: _Optional[_Iterable[float]] = ..., name: _Optional[str] = ...) -> None: ...

class Measurement(_message.Message):
    __slots__ = ["XYZ", "anc_data", "cct", "dominant_wl", "exposure", "power", "spd", "spectrometer_id", "time", "xy"]
    ANC_DATA_FIELD_NUMBER: _ClassVar[int]
    CCT_FIELD_NUMBER: _ClassVar[int]
    DOMINANT_WL_FIELD_NUMBER: _ClassVar[int]
    EXPOSURE_FIELD_NUMBER: _ClassVar[int]
    POWER_FIELD_NUMBER: _ClassVar[int]
    SPD_FIELD_NUMBER: _ClassVar[int]
    SPECTROMETER_ID_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    XYZ: XYZ_value
    XYZ_FIELD_NUMBER: _ClassVar[int]
    XY_FIELD_NUMBER: _ClassVar[int]
    anc_data: bytes
    cct: cct_value
    dominant_wl: float
    exposure: float
    power: float
    spd: Colour_SDS
    spectrometer_id: str
    time: Timestamp
    xy: xy_value
    def __init__(self, spd: _Optional[_Union[Colour_SDS, _Mapping]] = ..., exposure: _Optional[float] = ..., XYZ: _Optional[_Union[XYZ_value, _Mapping]] = ..., xy: _Optional[_Union[xy_value, _Mapping]] = ..., cct: _Optional[_Union[cct_value, _Mapping]] = ..., dominant_wl: _Optional[float] = ..., power: _Optional[float] = ..., spectrometer_id: _Optional[str] = ..., time: _Optional[_Union[Timestamp, _Mapping]] = ..., anc_data: _Optional[bytes] = ...) -> None: ...

class Measurement_List(_message.Message):
    __slots__ = ["ancillary", "author", "location", "measurements", "notes", "order", "software", "test_colors"]
    class TestColor(_message.Message):
        __slots__ = ["c", "f"]
        C_FIELD_NUMBER: _ClassVar[int]
        F_FIELD_NUMBER: _ClassVar[int]
        c: _containers.RepeatedScalarFieldContainer[int]
        f: _containers.RepeatedScalarFieldContainer[float]
        def __init__(self, c: _Optional[_Iterable[int]] = ..., f: _Optional[_Iterable[float]] = ...) -> None: ...
    ANCILLARY_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    LOCATION_FIELD_NUMBER: _ClassVar[int]
    MEASUREMENTS_FIELD_NUMBER: _ClassVar[int]
    NOTES_FIELD_NUMBER: _ClassVar[int]
    ORDER_FIELD_NUMBER: _ClassVar[int]
    SOFTWARE_FIELD_NUMBER: _ClassVar[int]
    TEST_COLORS_FIELD_NUMBER: _ClassVar[int]
    ancillary: bytes
    author: str
    location: str
    measurements: _containers.RepeatedCompositeFieldContainer[Measurement]
    notes: str
    order: _containers.RepeatedScalarFieldContainer[int]
    software: str
    test_colors: _containers.RepeatedCompositeFieldContainer[Measurement_List.TestColor]
    def __init__(self, measurements: _Optional[_Iterable[_Union[Measurement, _Mapping]]] = ..., test_colors: _Optional[_Iterable[_Union[Measurement_List.TestColor, _Mapping]]] = ..., order: _Optional[_Iterable[int]] = ..., notes: _Optional[str] = ..., author: _Optional[str] = ..., location: _Optional[str] = ..., software: _Optional[str] = ..., ancillary: _Optional[bytes] = ...) -> None: ...

class Spectral_Shape(_message.Message):
    __slots__ = ["end", "start", "step"]
    END_FIELD_NUMBER: _ClassVar[int]
    START_FIELD_NUMBER: _ClassVar[int]
    STEP_FIELD_NUMBER: _ClassVar[int]
    end: float
    start: float
    step: float
    def __init__(self, start: _Optional[float] = ..., end: _Optional[float] = ..., step: _Optional[float] = ...) -> None: ...

class Timestamp(_message.Message):
    __slots__ = ["timestr"]
    TIMESTR_FIELD_NUMBER: _ClassVar[int]
    timestr: str
    def __init__(self, timestr: _Optional[str] = ...) -> None: ...

class XYZ_value(_message.Message):
    __slots__ = ["X", "Y", "Z"]
    X: float
    X_FIELD_NUMBER: _ClassVar[int]
    Y: float
    Y_FIELD_NUMBER: _ClassVar[int]
    Z: float
    Z_FIELD_NUMBER: _ClassVar[int]
    def __init__(self, X: _Optional[float] = ..., Y: _Optional[float] = ..., Z: _Optional[float] = ...) -> None: ...

class cct_value(_message.Message):
    __slots__ = ["cct", "duv"]
    CCT_FIELD_NUMBER: _ClassVar[int]
    DUV_FIELD_NUMBER: _ClassVar[int]
    cct: float
    duv: float
    def __init__(self, cct: _Optional[float] = ..., duv: _Optional[float] = ...) -> None: ...

class xy_value(_message.Message):
    __slots__ = ["x", "y"]
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ...) -> None: ...
