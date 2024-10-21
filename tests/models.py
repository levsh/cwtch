import dataclasses

import msgspec
import pydantic

import cwtch


@dataclasses.dataclass
class DD:
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    d1: dict
    d2: dict[str, int]


@dataclasses.dataclass
class D:
    i1: int
    i2: int
    f1: float
    f2: float
    s1: str
    b1: bool
    b2: bool
    l: list
    t: tuple
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    tf: tuple[float, ...]
    ts: tuple[str, ...]
    d1: dict
    d2: dict[str, int]
    sub: DD
    subl: list[DD]
    subt: tuple[DD, ...]
    subd: dict[str, DD]


@cwtch.dataclass
class CC:
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    d1: dict
    d2: dict[str, int]


@cwtch.dataclass
class C:
    i1: int
    i2: int
    f1: float
    f2: float
    s1: str
    b1: bool
    b2: bool
    l: list
    t: tuple
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    tf: tuple[float, ...]
    ts: tuple[str, ...]
    d1: dict
    d2: dict[str, int]
    sub: CC
    subl: list[CC]
    subt: tuple[CC, ...]
    subd: dict[str, CC]


class PP(pydantic.BaseModel):
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    d1: dict
    d2: dict[str, int]


class P(pydantic.BaseModel):
    i1: int
    i2: int
    f1: float
    f2: float
    s1: str
    b1: bool
    b2: bool
    l: list
    t: tuple
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    tf: tuple[float, ...]
    ts: tuple[str, ...]
    d1: dict
    d2: dict[str, int]
    sub: PP
    subl: list[PP]
    subt: tuple[PP, ...]
    subd: dict[str, PP]


class MM(msgspec.Struct):
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    d1: dict
    d2: dict[str, int]


class M(msgspec.Struct):
    i1: int
    i2: int
    f1: float
    f2: float
    s1: str
    b1: bool
    b2: bool
    l: list
    t: tuple
    li: list[int]
    lf: list[float]
    ls: list[str]
    ti: tuple[int, ...]
    tf: tuple[float, ...]
    ts: tuple[str, ...]
    d1: dict
    d2: dict[str, int]
    sub: MM
    subl: list[MM]
    subt: tuple[MM, ...]
    subd: dict[str, MM]


RANGE = 50
SUB_RANGE = 25


sub_data = {
    "li": list(range(RANGE)),
    "lf": list(map(float, range(RANGE))),
    "ls": list(map(str, range(RANGE))),
    "ti": tuple(range(RANGE)),
    "d1": {},
    "d2": dict(zip(map(str, range(RANGE)), range(RANGE))),
}

data = {
    "i1": 0,
    "i2": "0",
    "f1": 1.1,
    "f2": "1.1",
    "s1": "s",
    "b1": True,
    "b2": 1,
    "l": list(range(RANGE)),
    "t": tuple(tuple(range(RANGE))),
    "li": list(range(RANGE)),
    "lf": list(map(float, range(RANGE))),
    "ls": list(map(str, range(RANGE))),
    "ti": tuple(range(RANGE)),
    "tf": tuple(range(RANGE)),
    "ts": tuple(map(str, range(RANGE))),
    "d1": {},
    "d2": dict(zip(map(str, range(RANGE)), range(RANGE))),
    "sub": sub_data,
    "subl": [sub_data for _ in range(SUB_RANGE)],
    "subt": tuple([sub_data for _ in range(SUB_RANGE)]),
    "subd": {f"{i}": sub_data for i in range(SUB_RANGE)},
}
