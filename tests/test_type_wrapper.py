import datetime

from typing import Callable

import pytest

from cwtch import TypeWrapper, ValidationError, dataclass, dumps_json, validate_value, view
from cwtch.core import make_json_schema


def test_TypeWrapper():
    class DateTime(TypeWrapper[datetime.datetime]): ...

    assert DateTime.utcnow()
    assert issubclass(datetime.datetime, DateTime)
    assert make_json_schema(DateTime) == ({"type": "string", "format": "date-time"}, {})


def test_validate_value():
    class DateTime(TypeWrapper[datetime.datetime]):
        def __cwtch_asjson__(self, **kwds):
            return "ABC"

    for input_value in (datetime.datetime(1970, 1, 1), DateTime(datetime.datetime(1970, 1, 1))):
        value = validate_value(input_value, DateTime)
        assert value == datetime.datetime(1970, 1, 1)
        assert type(value) == DateTime
        assert value.__class__ == datetime.datetime
        assert isinstance(value, DateTime)
        assert isinstance(value, datetime.datetime)
        assert str(value) == "1970-01-01 00:00:00"
        assert value.__cwtch_asjson__() == "ABC"
        assert dumps_json(value) == b'"ABC"'

    value = DateTime(datetime.datetime(1970, 1, 1))
    assert id(value) == id(validate_value(value, DateTime))


def test_model():
    class DateTime(TypeWrapper[datetime.datetime]):
        def __cwtch_asjson__(self, **kwds):
            return "ABC"

    @dataclass
    class M:
        dt: DateTime

    @view(M)
    class V:
        dt: datetime.datetime

    m = M("1970-01-01")
    assert type(m.dt) == DateTime

    v = m.V()
    assert type(v.dt) == datetime.datetime

    assert dumps_json(M("1970-01-01")) == b'{"dt":"ABC"}'


def test_str():
    class String(TypeWrapper[str]): ...

    s = "abc"

    assert s == String(s)
    assert id(s) != id(String(s))
    assert id(s) == id(f"{String(s)}")


def test_callable():
    class T(TypeWrapper[Callable]):
        def __cwtch_asjson__(self, **kwds):
            return "ABC"

    @dataclass
    class M:
        t: T

    M(t=lambda x: x)

    assert dumps_json(M(t=lambda x: x)) == b'{"t":"ABC"}'

    with pytest.raises(ValidationError):
        M(t=1)

    M(t=lambda x: x).t("t") == "t"
