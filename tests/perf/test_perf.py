import time

import pytest

from .models import *


RANGE = 1000


@pytest.mark.benchmark(
    group="general",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_msgspec(benchmark):
    time.sleep(0.1)
    benchmark(lambda: [msgspec.convert(data, M, strict=False) for _ in range(RANGE)])


@pytest.mark.benchmark(
    group="general",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_pydantic(benchmark):
    time.sleep(0.1)
    benchmark(lambda: [P(**data) for _ in range(RANGE)])


@pytest.mark.benchmark(
    group="general",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_cwtch(benchmark):
    time.sleep(0.1)
    benchmark(lambda: [C(**data) for _ in range(RANGE)])
