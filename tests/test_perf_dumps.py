import pytest

from models import *


RANGE = 100


@pytest.mark.benchmark(
    group="dumps",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_cwtch_json(benchmark):
    model = C(**data)

    dumps = cwtch.dumps

    benchmark(lambda: [dumps(model) for _ in range(RANGE)])


@pytest.mark.benchmark(
    group="dumps",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_pydantic_json(benchmark):
    model = P(**data)

    dumps = model.model_dump_json

    benchmark(lambda: [dumps() for _ in range(RANGE)])


@pytest.mark.benchmark(
    group="dumps",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_msgspec_json(benchmark):
    model = M(**data)

    from msgspec.json import encode

    benchmark(lambda: [encode(model) for _ in range(RANGE)])
