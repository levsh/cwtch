import time

import psutil

from cwtch import dataclass, field


@dataclass(extra="ignore")
class CC:
    li1: list[int] = field()
    li2: list[int] = field()
    lf1: list[float] = field()
    lf2: list[float] = field()
    ls1: list[str] = field()
    ti: tuple[int, ...] = field()
    d: dict = field()
    dd: dict[str, int] = field()


@dataclass
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
    ti: tuple[int, ...] = field()
    d: dict = field()
    dd: dict[str, int] = field()
    sub: list[CC]


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
    "ti": tuple(range(RANGE)),
    "d": {},
    "dd": dict(zip(map(str, range(RANGE)), range(RANGE))),
}

data["sub"] = [data for _ in range(10)]


def test_memory_leak():
    p = psutil.Process()

    for _ in range(5):
        [C(**data) for _ in range(1000)]

    memory_start = p.memory_full_info()

    for _ in range(1000):
        [C(**data) for _ in range(1000)]
        time.sleep(0.002)

    memory_end = p.memory_full_info()

    diff = memory_end.rss - memory_start.rss
    assert diff < 4 * 1024**2, (diff, memory_start, memory_end)
