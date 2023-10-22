import attrs
from cattrs import structure
from msgspec import Struct, convert
from pydantic import BaseModel

from cwtch import define, field


@define
class C:
    i: int = field()
    f: float = field()
    s: str = field()
    b: bool = field()
    l: list = field()
    t: tuple = field()
    li1: list[int] = field()
    li2: list[int] = field()
    lf1: list[float] = field()
    lf2: list[float] = field()
    ls1: list[str] = field()
    # ls2: list[str] = field()
    ti: tuple[int, ...] = field()
    d: dict = field()
    dd: dict[str, int] = field()


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
    # ls2: list[str] = field()
    ti: tuple[int, ...] = attrs.field()
    d: dict = attrs.field()
    dd: dict[str, int] = attrs.field()


class P(BaseModel):
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


RANGE = 25

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
}


def test_perf_cwtch(benchmark):
    benchmark(lambda: [C(**data) for _ in range(1000)])


def test_perf_cattrs(benchmark):
    benchmark(lambda: [structure(data, A) for _ in range(1000)])


def test_perf_pydantic(benchmark):
    benchmark(lambda: [P(**data) for _ in range(1000)])


def test_perf_msgspec(benchmark):
    benchmark(lambda: [convert(data, M, strict=False) for _ in range(1000)])
