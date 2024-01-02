import os
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timezone
from typing import Annotated, Any, ForwardRef, Generic, Literal, TypeVar
from unittest import mock

import attrs
import msgspec
import pytest
from cattrs import structure
from pydantic import BaseModel

from cwtch import (
    Meta,
    SecretStr,
    SecretUrl,
    ValidationError,
    asdict,
    define,
    field,
    make_json_schema,
    validate_args,
    validate_value,
    view,
)

T = TypeVar("T")


def test_validate_none():
    assert validate_value(None, None) is None
    for value in (0, 0.0, "a", True, False, object()):
        with pytest.raises(ValidationError, match=re.escape("value is not a None")):
            validate_value(value, None)


def test_validate_int():
    assert validate_value(-1, int) == -1
    assert validate_value(0, int) == 0
    assert validate_value(1, int) == 1
    assert validate_value("1", int) == 1
    with pytest.raises(
        ValidationError,
        match=re.escape("validation error for <class 'int'>\n  - invalid literal for int() with base 10: 'a'"),
    ):
        validate_value("a", int)
    with pytest.raises(
        ValidationError,
        match=re.escape(
            (
                "validation error for <class 'int'>\n"
                "  - int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"
            )
        ),
    ):
        validate_value(None, int)


def test_validate_float():
    assert validate_value(-1, float) == -1.0
    assert validate_value(0, float) == 0.0
    assert validate_value(1, float) == 1.0
    assert validate_value("1.1", float) == 1.1
    with pytest.raises(
        ValidationError,
        match=re.escape("validation error for <class 'float'>\n  - could not convert string to float: 'a'"),
    ):
        validate_value("a", float)


def test_validate_str():
    assert validate_value(0, str) == "0"
    assert validate_value("a", str) == "a"
    assert validate_value(None, str) == "None"
    assert validate_value(True, str) == "True"
    assert validate_value(False, str) == "False"


def test_validate_bool():
    for value in (1, "1", "true", "True", "TRUE", "y", "Y", "t", "yes", "Yes", "YES"):
        assert validate_value(value, bool) is True
    for value in (0, "0", "false", "False", "FALSE", "n", "N", "f", "no", "No", "NO"):
        assert validate_value(value, bool) is False
    for value in (-1, 2, "a"):
        with pytest.raises(
            ValidationError,
            match=re.escape("validation error for <class 'bool'>\n  - invalid value for <class 'bool'>"),
        ):
            validate_value(value, bool)


def test_validate_datetime():
    assert validate_value(
        "2023-01-01T00:00:00+00:00",
        datetime,
    ) == datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert validate_value(
        datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
        datetime,
    ) == datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)


def test_validate_date():
    assert validate_value("2023-01-01", date) == date(2023, 1, 1)
    assert validate_value(date(2023, 1, 1), date) == date(2023, 1, 1)


def test_validate_literal():
    validate_value("A", Literal["A", "B"])
    validate_value("B", Literal["A", "B"])
    with pytest.raises(
        ValidationError,
        match=re.escape("validation error for typing.Literal['A', 'B']\n  - value is not a one of ['A', 'B']"),
    ):
        validate_value("C", Literal["A", "B"])
    with pytest.raises(
        ValidationError,
        match=re.escape("validation error for typing.Literal['1']\n  - value is not a one of ['1']"),
    ):
        validate_value(1, Literal["1"])
    with pytest.raises(
        ValidationError,
        match=re.escape("validation error for typing.Literal[1]\n  - value is not a one of [1]"),
    ):
        validate_value("1", Literal[1])


def test_validate_annotated():
    assert validate_value(1, Annotated[int, Meta(ge=1)]) == 1
    with pytest.raises(
        ValidationError,
        match=re.escape(("validation error for typing.Annotated[int, msgspec.Meta(ge=1)]\n  - value should be >= 1")),
    ):
        validate_value(0, Annotated[int, Meta(ge=1)])
    assert validate_value(1, Annotated[Annotated[int, Meta(ge=0)], Meta(ge=1)]) == 1
    with pytest.raises(
        ValidationError,
        match=re.escape(
            "validation error for typing.Annotated[int, msgspec.Meta(ge=2), msgspec.Meta(ge=1)]\n  - value should be >= 2"
        ),
    ):
        validate_value(1, Annotated[Annotated[int, Meta(ge=2)], Meta(ge=1)])


def test_validate_model_simple():
    @attrs.define
    class M:
        i: int
        s: str

    assert validate_value({"i": 1, "s": "s"}, M) == M(i=1, s="s")


def test_validate_list():
    @attrs.define
    class M:
        i: int

    assert validate_value((), list) == []
    assert validate_value((), list[int]) == []
    assert validate_value((0, 1), list) == [0, 1]
    assert validate_value((0, 1), list[int]) == [0, 1]
    assert validate_value((0, 1), list[str]) == ["0", "1"]
    assert validate_value((0, "1"), list[int]) == [0, 1]
    assert validate_value(([0], (1,)), list[list[int]]) == [[0], [1]]
    assert validate_value(([0], ("1",)), list[list[int]]) == [[0], [1]]
    assert validate_value((["0"], ("y",)), list[list[bool]]) == [[False], [True]]
    assert validate_value(({"i": 0},), list[M]) == [M(i=0)]

    with pytest.raises(
        ValidationError,
        match=re.escape("validation error for list[int] path=[1]\n  - invalid literal for int() with base 10: 'a'"),
    ):
        validate_value([0, "a"], list[int])


def test_validate_tuple():
    @attrs.define
    class M:
        i: int

    assert validate_value([], tuple) == ()
    assert validate_value([], tuple[int]) == ()
    assert validate_value([0, 1], tuple) == (0, 1)
    assert validate_value([0, 1], tuple[int, int]) == (0, 1)
    assert validate_value([0, 1], tuple[int, str]) == (0, "1")
    assert validate_value([0, "1"], tuple[int, ...]) == (0, 1)
    assert validate_value([0, 1, "2"], tuple[int, ...]) == (0, 1, 2)
    assert validate_value([[0], [1]], tuple[list[int], list[int]]) == ([0], [1])
    assert validate_value([[0], ["1"]], tuple[list[int], list[int]]) == ([0], [1])
    assert validate_value([["0"], ["y"]], tuple[list[bool], tuple[bool]]) == ([False], (True,))
    assert validate_value(list(range(100)), tuple[int, ...]) == tuple(range(100))
    assert validate_value([{"i": 0}], tuple[M]) == (M(i=0),)


def test_validate_mapping():
    @attrs.define
    class M:
        i: int

    for T in (dict, Mapping):
        assert validate_value({}, T) == {}
        assert validate_value({"k": "v"}, T) == {"k": "v"}
        assert validate_value({"k": "v"}, T[str, str]) == {"k": "v"}
        assert validate_value({"0": "1"}, T[int, int]) == {0: 1}
        assert validate_value({}, T) == {}
        assert validate_value({"k": "v"}, T) == {"k": "v"}
        assert validate_value({"k": "v"}, T[str, str]) == {"k": "v"}
        assert validate_value({"0": "1"}, T[int, int]) == {0: 1}
        assert validate_value({"m": {"i": 0}}, T[str, M]) == {"m": M(i=0)}

    with pytest.raises(
        ValidationError,
        match=re.escape(
            (
                "validation error for dict[str, dict[str, int]] path=['k', 'kk']\n"
                "  validation error for dict[str, int] path=['kk']\n"
                "    - invalid literal for int() with base 10: 'v'"
            )
        ),
    ):
        assert validate_value({"k": {"kk": "v"}}, dict[str, dict[str, int]])


def test_validate_annotated_complex():
    assert validate_value([1, 2], list[Annotated[int, Meta(ge=1)]]) == [1, 2]
    with pytest.raises(
        ValidationError,
        match=re.escape(
            "validation error for list[typing.Annotated[int, msgspec.Meta(ge=1)]] path=[2]\n  - value should be >= 1"
        ),
    ):
        validate_value([1, 2, 0], list[Annotated[int, Meta(ge=1)]])
    assert validate_value((1, 2), list[Annotated[int, Meta(ge=1)]]) == [1, 2]
    with pytest.raises(
        ValidationError,
        match=re.escape(
            "validation error for list[typing.Annotated[int, msgspec.Meta(ge=1)]] path=[2]\n  - value should be >= 1"
        ),
    ):
        validate_value((1, 2, 0), list[Annotated[int, Meta(ge=1)]])


def test_validate_union():
    assert validate_value(1, int | str) == 1
    assert validate_value(1, str | int) == 1
    assert validate_value(1, str | float) == "1"
    assert validate_value(1, float | str) == 1.0
    with pytest.raises(ValidationError):
        assert validate_value("a", int | float) == "a"
    T = Annotated[int | float, Meta(ge=1)]
    assert validate_value("a", T | str) == "a"
    with pytest.raises(
        ValidationError,
        match=re.escape(
            (
                "validation error for typing.Union[typing.Annotated[int | float, msgspec.Meta(ge=1)], bool]\n"
                "  - invalid literal for int() with base 10: 'a'\n"
                "  - could not convert string to float: 'a'\n"
                "  - invalid value for <class 'bool'>"
            )
        ),
    ):
        assert validate_value("a", T | bool) == "a"
    assert validate_value(1, int | Any) == 1
    assert validate_value("1", int | Any) == "1"


def test_validate_abcmeta():
    assert validate_value([1], Iterable) == [1]
    assert validate_value([1], Iterable[int]) == [1]
    assert validate_value([1], Sequence) == [1]
    assert validate_value([1], Sequence[int]) == [1]


def test_model():
    @define
    class A:
        i: int = field()
        s: str = field()
        b: bool = field()
        l: list = field()
        t: tuple = field()
        li: list[int] = field()
        ti: tuple[int, ...] = field()
        d: dict = field()
        dd: dict[str, int] = field()
        ai: Annotated[int, Meta(ge=0)] = field()
        al: Annotated[list[int], Meta(min_length=1)] = field()

    # assert A.__base__ == Base

    a = A(
        i="1",
        s=1,
        b="y",
        l=(0, "1"),
        t=["0", 1],
        li=(0, "1"),
        ti=["0", 1],
        d={},
        dd={"0": 0, 1: "1"},
        ai="1",
        al=[0, "1"],
    )
    assert a.i == 1
    assert a.s == "1"
    assert a.b is True
    assert a.l == [0, "1"]
    assert a.t == ("0", 1)
    assert a.li == [0, 1]
    assert a.ti == (0, 1)
    assert a.d == {}
    assert a.dd == {"0": 0, "1": 1}
    assert a.ai == 1
    assert a.al == [0, 1]

    @define
    class M:
        i: int = field()
        s: str = field(default="s")

    with pytest.raises(
        ValidationError,
        match=re.escape(
            (
                "validation error for <class 'test_cwtch.M'> path=['i']\n"
                "  validation error for <class 'int'>\n"
                "    - invalid literal for int() with base 10: 'a'"
            )
        ),
    ):
        M(i="a")


def test_forward_ref():
    B = ForwardRef("B")

    @define
    class A:
        a1: "B" = field()
        a2: B = field()

    @define
    class B:
        i: int = field()

    attrs.resolve_types(A, globals(), locals())

    a = validate_value({"a1": {"i": 1}, "a2": {"i": 2}}, A)
    assert a.a1.i == 1
    assert a.a2.i == 2


def test_post_init():
    flag = False

    @define
    class A:
        i: int = field()

        def __attrs_post_init__(self):
            nonlocal flag
            flag = True

    A(i=1)
    assert flag


def test_ignore_extra():
    @define(ignore_extra=True)
    class A:
        i: int = field()

    aa = A(i="1", s="a", b="n")
    assert aa.i == 1


def test_inheritance():
    @define
    class A:
        i: int = field()

    @define
    class B(A):
        j: int = field()

    @define(ignore_extra=True)
    class C(A):
        j: int = field()


def test_env_prefix():
    @define(env_prefix="TEST_")
    class M:
        i: int = field(default=0, env_var=True)

    assert M.__cwtch_env_prefixes__ == ["TEST_"]
    assert M.__cwtch_env_source__ is not None

    env = {}
    with mock.patch.dict(os.environ, env, clear=True):
        assert M().i == 0

    env = {"TEST_I": "1"}
    with mock.patch.dict(os.environ, env, clear=True):
        assert M().i == 1


def test_view():
    validator_calls = []

    @define
    class A:
        i: int = field()
        j: int
        s: str = field()
        b: bool = field()
        l: list[int] = field()

        @view(include={"i", "j"})
        class V1:
            j: int = 0

        @view(exclude={"s", "b", "l"}, lc=locals())
        class V2:
            j: int = 0

        @view
        class V3:
            f: float

        @i.validator
        def validator1(*args):
            validator_calls.append("validator1")

        @i.validator
        def validator2(*args):
            validator_calls.append("validator2")

        @V2.i.validator
        def validator_V2(*args):
            validator_calls.append("validator_V2")

    assert A.V1
    assert A.V1.__cwtch_view_name__ == "V1"
    assert A.V1.__cwtch_view_base__ == A

    assert A.V2
    assert A.V2.__cwtch_view_name__ == "V2"
    assert A.V2.__cwtch_view_base__ == A

    aa = A(i="1", j="2", s="a", b="n", l=["1", "2"])
    assert aa.i == 1
    assert aa.j == 2
    assert aa.V1
    assert validator_calls == ["validator1", "validator2"]
    validator_calls.clear()

    v1 = aa.V1()
    assert v1.__cwtch_view_name__ == "V1"
    assert v1.__cwtch_view_base__ == A
    assert v1.i == 1
    assert v1.j == 2
    assert validator_calls == ["validator1", "validator2"]
    validator_calls.clear()

    v2 = aa.V2()
    assert v2.__cwtch_view_name__ == "V2"
    assert v2.__cwtch_view_base__ == A
    assert v2.i == 1
    assert v2.j == 2
    assert validator_calls == ["validator1", "validator2", "validator_V2"]
    validator_calls.clear()

    assert asdict(v1) == asdict(v2) == {"i": 1, "j": 2}

    v2 = A.V2(i=1)
    assert v2.i == 1
    assert v2.j == 0
    assert asdict(v2) == {"i": 1, "j": 0}

    v3 = A.V3(i=1, j=2, s="a", b=False, l=[], f=1.1)


def test_view_ignore_extra():
    @define
    class A:
        i: int = field()

        @view(ignore_extra=True)
        class V:
            pass

    v = A.V(i="1", s="a", b="n")
    assert v.i == 1


def test_view_validate():
    @define
    class A:
        i: int = field()

        @view
        class V1:
            pass

        @view(validate=False)
        class V2:
            pass

    assert A.V1(i="1").i == 1
    assert A.V2(i="1").i == "1"


def test_generics():
    @define
    class C(Generic[T]):
        x: list[T] = field()

    assert validate_value({"x": ["1"]}, C[int]).x == [1]
    assert C[int](x=["1"]).x == [1]

    with pytest.raises(
        ValidationError,
        match=re.escape(
            (
                "validation error for <class 'test_cwtch.C'> path=['x']\n"
                "  validation error for list[~T] parameters=[<class 'int'>] path=[0]\n"
                "    - invalid literal for int() with base 10: 'a'"
            )
        ),
    ):
        assert validate_value({"x": ["a"]}, C[int]).x == [1]
    with pytest.raises(
        ValidationError,
        match=re.escape(
            (
                "validation error for <class 'test_cwtch.C'> path=['x']\n"
                "  validation error for list[~T] parameters=[<class 'int'>] path=[0]\n"
                "    - invalid literal for int() with base 10: 'a'"
            )
        ),
    ):
        assert C[int](x=["a"]).x == [1]


@pytest.mark.skip
def test_json_value_metadata():
    JsonList = Annotated[list, JsonValue()]
    JsonDict = Annotated[dict, JsonValue()]

    @define
    class M:
        args: JsonList | None = field(default=None)
        kwds: JsonDict | None = field(default=None)

    m = M(args="[]", kwds="{}")
    assert m.args == []
    assert m.kwds == {}


def test_view_recursive():
    @define
    class A:
        i: int | None = None
        s: str | None = None

        @view(include={"i"})
        class V:
            pass

    @define
    class B:
        a: A

        @view(recursive=True)
        class V:
            pass

    B(a=A())

    assert B.__annotations__["a"] == A
    assert B.V.__annotations__["a"] == A.V


def test_json_schema():
    @define
    class SubModel:
        i: int

    @define
    class Model:
        i: int = field()
        m: SubModel

    msgspec.json.schema_components([Model, SubModel])


def test_validate_call():
    def foo(s: str, i: int = None):
        pass

    assert validate_args(foo, ("a", 1), {}) == (("a", 1), {})
    assert validate_args(foo, ("a", "1"), {}) == (("a", 1), {})
    with pytest.raises(TypeError):
        validate_args(foo, ("a",), {"i": "a"})


def test_SecretStr():
    s = SecretStr("secret")
    assert s != "secret"
    assert s != SecretStr("secret")
    assert str(s) == "SecretStr(***)"
    assert repr(s) == "SecretStr(***)"
    assert s.get_secret_value() == "secret"
    assert hash(s) == hash(s.get_secret_value())


def test_SecretUrl():
    s = SecretUrl("http://user:pass@localhost")
    assert s != "http://user:pass@localhost"
    assert str(s) == "SecretUrl(http://***@localhost)"
    assert repr(s) == "SecretUrl(http://***@localhost)"
    assert s.get_secret_value() == "http://user:pass@localhost"
    assert hash(s) == hash(s.get_secret_value())


def test_make_json_schema():
    assert make_json_schema(int) == ({"type": "integer"}, {})
    assert make_json_schema(str) == ({"type": "string"}, {})
    assert make_json_schema(float) == ({"type": "number"}, {})
    assert make_json_schema(bool) == ({"type": "boolean"}, {})
    assert make_json_schema(list) == ({"type": "array"}, {})
    assert make_json_schema(list[int]) == ({"type": "array", "items": {"type": "integer"}}, {})
    assert make_json_schema(tuple) == ({"type": "array"}, {})
    assert make_json_schema(tuple[int, str]) == (
        {"type": "array", "prefixItems": [{"type": "integer"}, {"type": "string"}]},
        {},
    )
    assert make_json_schema(set) == ({"type": "array"}, {})
    assert make_json_schema(set[int]) == ({"type": "array", "items": {"type": "integer"}}, {})
    assert make_json_schema(dict) == ({"type": "object"}, {})
    assert make_json_schema(Literal["A", 1]) == ({"enum": ["A", 1]}, {})
    assert make_json_schema(Annotated[int, Meta(ge=1, le=10)]) == ({"type": "integer", "minimum": 1, "maximum": 10}, {})
    assert make_json_schema(Annotated[int, Meta(gt=1, lt=10)]) == (
        {"type": "integer", "exclusiveMinimum": True, "minimum": 1, "exclusiveMaximum": True, "maximum": 10},
        {},
    )
    assert make_json_schema(Annotated[str, Meta(min_length=1, max_length=10)]) == (
        {"type": "string", "minLength": 1, "maxLength": 10},
        {},
    )

    @define
    class Model:
        i: Annotated[int, Meta(ge=1, lt=10)]
        s: str
        l: list
        f: list[float]

    assert make_json_schema(list[Model]) == (
        {"type": "array", "items": {"$ref": "#/$defs/Model"}},
        {
            "Model": {
                "type": "object",
                "properties": {
                    "i": {"type": "integer", "minimum": 1, "exclusiveMaximum": True, "maximum": 10},
                    "s": {"type": "string"},
                    "l": {"type": "array"},
                    "f": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["i", "s", "l", "f"],
            }
        },
    )
