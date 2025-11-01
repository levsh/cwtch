import pytest

from .models import *


RANGE = 100


@pytest.mark.benchmark(
    group="asdict",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_dataclasses_asdict(benchmark):
    model = D(**data)

    asdict = dataclasses.asdict

    benchmark(lambda: [asdict(model) for _ in range(RANGE)])


@pytest.mark.benchmark(
    group="asdict",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_cwtch_asdict(benchmark):
    model = C(**data)

    asdict = cwtch.asdict

    benchmark(lambda: [asdict(model, exclude=["f", "li", "d1"]) for _ in range(RANGE)])


@pytest.mark.benchmark(
    group="asdict",
    min_rounds=10,
    # disable_gc=True,
    warmup=True,
)
def test_perf_pydantic_asdict(benchmark):
    model = P(**data)

    model_dump = model.model_dump

    benchmark(lambda: [model_dump(exclude={"f", "li", "d1"}) for _ in range(RANGE)])
