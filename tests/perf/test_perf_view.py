import pytest

from cwtch import dataclass, view


@dataclass
class Sub:
    i: int


@view(Sub, "V")
class SubV:
    pass


@dataclass
class M:
    i: int
    s: str
    b: bool
    l: list[Sub]


@view(M, "V")
class MV:
    pass


@pytest.mark.benchmark(
    group="view",
    min_rounds=10,
    disable_gc=True,
    warmup=True,
)
def test_view_from_class(benchmark):
    benchmark(lambda: [M.V(i=1, s="s", b=True, l=[{"i": 1} for _ in range(100)]) for _ in range(100)])


@pytest.mark.benchmark(
    group="view",
    min_rounds=10,
    disable_gc=True,
    warmup=True,
)
def test_view_from_obj(benchmark):
    m = M(i=1, s="s", b=True, l=[{"i": 1} for _ in range(100)])
    benchmark(lambda: [m.V() for _ in range(100)])
