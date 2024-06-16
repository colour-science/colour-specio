from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SpectralShape(_message.Message):
    __slots__ = ("start", "end", "step")
    START_FIELD_NUMBER: _ClassVar[int]
    END_FIELD_NUMBER: _ClassVar[int]
    STEP_FIELD_NUMBER: _ClassVar[int]
    start: float
    end: float
    step: float
    def __init__(self, start: _Optional[float] = ..., end: _Optional[float] = ..., step: _Optional[float] = ...) -> None: ...

class SpectralDistribution(_message.Message):
    __slots__ = ("shape", "values", "values_old", "name")
    SHAPE_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    VALUES_OLD_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    shape: SpectralShape
    values: _containers.RepeatedScalarFieldContainer[float]
    values_old: _containers.RepeatedScalarFieldContainer[float]
    name: str
    def __init__(self, shape: _Optional[_Union[SpectralShape, _Mapping]] = ..., values: _Optional[_Iterable[float]] = ..., values_old: _Optional[_Iterable[float]] = ..., name: _Optional[str] = ...) -> None: ...

class XYZ_value(_message.Message):
    __slots__ = ("X", "Y", "Z")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    X: float
    Y: float
    Z: float
    def __init__(self, X: _Optional[float] = ..., Y: _Optional[float] = ..., Z: _Optional[float] = ...) -> None: ...

class xy_value(_message.Message):
    __slots__ = ("x", "y")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ...) -> None: ...

class cct_value(_message.Message):
    __slots__ = ("cct", "duv")
    CCT_FIELD_NUMBER: _ClassVar[int]
    DUV_FIELD_NUMBER: _ClassVar[int]
    cct: float
    duv: float
    def __init__(self, cct: _Optional[float] = ..., duv: _Optional[float] = ...) -> None: ...

class Timestamp(_message.Message):
    __slots__ = ("timestr",)
    TIMESTR_FIELD_NUMBER: _ClassVar[int]
    timestr: str
    def __init__(self, timestr: _Optional[str] = ...) -> None: ...
