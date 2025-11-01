import re

from typing import Annotated

import annotated_types
import pytest

# from cwtch.metadata import Ge, Le, Match, MaxLen, MinItems, MinLen
from cwtch import dataclass, field, metadata
from cwtch.core import get_validator, validate_value


pydantic = pytest.importorskip("pydantic")
from pydantic import BaseModel, Field


@dataclass
class AddressCwtch:
    street: Annotated[str, metadata.MinLen(1), metadata.MaxLen(100)]
    city: Annotated[str, metadata.MinLen(1), metadata.MaxLen(50)]
    zip: str


@dataclass
class PersonCwtch:
    name: Annotated[str, metadata.MinLen(1), metadata.MaxLen(50)]
    age: Annotated[int, metadata.Ge(0), metadata.Le(150)]
    addresses: Annotated[list[AddressCwtch], metadata.MinItems(1)]


@pytest.fixture(scope="session")
def cwtch_validator():
    return get_validator(PersonCwtch)


class AddressPydantic(BaseModel):
    street: Annotated[str, annotated_types.MinLen(1), annotated_types.MaxLen(100)]
    city: Annotated[str, annotated_types.MinLen(1), annotated_types.MaxLen(50)]
    zip: str


class PersonPydantic(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=150)
    addresses: list[AddressPydantic] = Field(min_length=1)


@pytest.fixture(scope="session")
def pydantic_validator():
    return pydantic.TypeAdapter(PersonPydantic).validate_python


@pytest.fixture(params=[10])
def size(request):
    return request.param


@pytest.fixture
def person_data(size):
    addresses = []
    for i in range(size):
        addresses.append(
            {
                "street": f"Street {i}",
                "city": f"City {i}",
                "zip": "12345",
            }
        )
    return {
        "name": "John Doe",
        "age": 30,
        "addresses": addresses,
    }


@pytest.mark.benchmark(
    group="small",
    min_rounds=10,
    disable_gc=True,
    warmup=True,
)
def test_cwtch_validate_value(benchmark, cwtch_validator, person_data):
    benchmark(lambda: [cwtch_validator(person_data, PersonCwtch) for _ in range(10)])


@pytest.mark.benchmark(
    group="small",
    min_rounds=10,
    disable_gc=True,
    warmup=True,
)
def test_pydantic_validate_python(benchmark, pydantic_validator, person_data):
    benchmark(lambda: [pydantic_validator(person_data) for _ in range(10)])
