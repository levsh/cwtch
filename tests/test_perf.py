import time

import attrs
from cattrs import structure
from msgspec import Struct, convert
from pydantic import BaseModel

from cwtch import dataclass


@dataclass(slots=True, ignore_extra=True)
class CC:
    li1: list[int]
    li2: list[int]
    lf1: list[float]
    lf2: list[float]
    ls1: list[str]
    ti: tuple[int, ...]
    d: dict
    dd: dict[str, int]


@dataclass(slots=True)
class C:
    i: int
    f: float
    s: str
    b: bool
    l: list
    t: tuple
    li1: list[int]
    li2: list[int]
    lf1: list[float]
    lf2: list[float]
    ls1: list[str]
    # ls2: list[str]
    ti: tuple[int, ...]
    d: dict
    dd: dict[str, int]
    sub1: list[CC]
    sub2: list[CC]


@attrs.define
class AA:
    li1: list[int] = attrs.field()
    li2: list[int] = attrs.field()
    lf1: list[float] = attrs.field()
    lf2: list[float] = attrs.field()
    ls1: list[str] = attrs.field()
    ti: tuple[int, ...] = attrs.field()
    d: dict = attrs.field()
    dd: dict[str, int] = attrs.field()


@attrs.define
class A:
    i: int = attrs.field()
    f: float = attrs.field()
    s: str = attrs.field()
    b: bool = attrs.field()
    l: list = attrs.field()
    t: tuple = attrs.field()
    li1: list[int] = attrs.field()
    li2: list[int] = attrs.field()
    lf1: list[float] = attrs.field()
    lf2: list[float] = attrs.field()
    ls1: list[str] = attrs.field()
    # ls2: list[str] = attrs.field()
    ti: tuple[int, ...] = attrs.field()
    d: dict = attrs.field()
    dd: dict[str, int] = attrs.field()
    sub1: list[AA] = attrs.field()
    sub2: list[AA] = attrs.field()


class PP(BaseModel):
    li1: list[int]
    li2: list[int]
    lf1: list[float]
    lf2: list[float]
    ls1: list[str]
    ti: tuple[int, ...]
    d: dict
    dd: dict[str, int]


class P(BaseModel, extra="forbid"):
    i: int
    f: float
    s: str
    b: bool
    l: list
    t: tuple
    li1: list[int]
    li2: list[int]
    lf1: list[float]
    lf2: list[float]
    ls1: list[str]
    # ls2: list[str]
    ti: tuple[int, ...]
    d: dict
    dd: dict[str, int]
    sub1: list[PP]
    sub2: list[PP]


class MM(Struct):
    li1: list[int]
    li2: list[int]
    lf1: list[float]
    lf2: list[float]
    ls1: list[str]
    ti: tuple[int, ...]
    d: dict
    dd: dict[str, int]


class M(Struct):
    i: int
    f: float
    s: str
    b: bool
    l: list
    t: tuple
    li1: list[int]
    li2: list[int]
    lf1: list[float]
    lf2: list[float]
    ls1: list[str]
    # ls2: list[str]
    ti: tuple[int, ...]
    d: dict
    dd: dict[str, int]
    sub1: list[MM]
    sub2: list[MM]


RANGE = 25

sub_data = {
    "li1": list(range(RANGE)),
    "li2": list(map(str, range(RANGE))),
    "lf1": list(map(float, range(RANGE))),
    "lf2": list(map(str, map(float, range(RANGE)))),
    "ls1": list(map(str, range(RANGE))),
    # "ls2": list(range(RANGE)),
    "ti": tuple(range(RANGE)),
    "d": {},
    "dd": dict(zip(map(str, range(RANGE)), range(RANGE))),
}

data = {
    "i": 0,
    "f": 1.1,
    "s": "s",
    "b": True,
    "l": list(range(RANGE)),
    "t": tuple(tuple(range(RANGE))),
    "li1": list(range(RANGE)),
    "li2": list(map(str, range(RANGE))),
    "lf1": list(map(float, range(RANGE))),
    "lf2": list(map(str, map(float, range(RANGE)))),
    "ls1": list(map(str, range(RANGE))),
    # "ls2": list(range(RANGE)),
    "ti": tuple(range(RANGE)),
    "d": {},
    "dd": dict(zip(map(str, range(RANGE)), range(RANGE))),
    "sub1": [sub_data for _ in range(10)],
    "sub2": [sub_data for _ in range(10)],
}


def test_perf_warm(benchmark):
    time.sleep(1)
    benchmark(lambda: [convert(data, M, strict=False) for _ in range(1000)])


def test_perf_msgspec(benchmark):
    time.sleep(1)
    benchmark(lambda: [convert(data, M, strict=False) for _ in range(1000)])


def test_perf_pydantic(benchmark):
    time.sleep(1)
    benchmark(lambda: [P(**data) for _ in range(1000)])


def test_perf_cwtch(benchmark):
    time.sleep(1)
    benchmark(lambda: [C(**data) for _ in range(1000)])


# def test_perf_cattrs(benchmark):
#     time.sleep(1)
#     benchmark(lambda: [structure(data, A) for _ in range(1000)])
