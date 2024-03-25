import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import MISSING
from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, ForwardRef, Generic, List, Literal, Set, Tuple, Type, TypeVar, Union
from unittest import mock

import pytest

from cwtch import (
    asdict,
    dataclass,
    field,
    get_current_parameters,
    make_json_schema,
    validate_args,
    validate_value,
    view,
)
from cwtch.errors import ValidationError
from cwtch.metadata import Ge, Gt, JsonValue, Le, Lt, MaxItems, MaxLen, MinItems, MinLen
from cwtch.types import UNSET, LowerStr, StrictBool, StrictFloat, StrictInt, StrictNumber, StrictStr, UpperStr

T = TypeVar("T")
F = TypeVar("F")


class TestValidateValue:
    def test_none(self):
        assert validate_value(None, None) is None
        for value in (0, 0.0, "a", True, False, UNSET, object(), (), [], {}, int):
            with pytest.raises(ValidationError, match=re.escape("E: value is not a None")):
                validate_value(value, None)

    def test_bool(self):
        for value in (1, "1", "true", "True", "TRUE", "y", "Y", "t", "yes", "Yes", "YES"):
            assert validate_value(value, bool) is True
        for value in (0, "0", "false", "False", "FALSE", "n", "N", "f", "no", "No", "NO"):
            assert validate_value(value, bool) is False
        for value in (-2, 2):
            with pytest.raises(
                ValidationError,
                match=re.escape(
                    "type=[<class 'bool'>] input_type=[<class 'int'>]\n  E: could not convert value to bool"
                ),
            ):
                validate_value(value, bool)
        for value in ("ok", "not ok"):
            with pytest.raises(
                ValidationError,
                match=re.escape(
                    "type=[<class 'bool'>] input_type=[<class 'str'>]\n  E: could not convert value to bool"
                ),
            ):
                validate_value(value, bool)

    def test_int(self):
        assert validate_value(-1, int) == -1
        assert validate_value(0, int) == 0
        assert validate_value(1, int) == 1
        assert validate_value("1", int) == 1
        assert validate_value(True, int) == 1
        assert validate_value(False, int) == 0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[<class 'int'>] input_type=[<class 'str'>]\n  E: invalid literal for int() with base 10: 'a'"
            ),
        ):
            validate_value("a", int)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'int'>] input_type=[<class 'NoneType'>]\n"
                    "  E: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"
                )
            ),
        ):
            validate_value(None, int)

    def test_float(self):
        assert validate_value(-1, float) == -1.0
        assert validate_value(0, float) == 0.0
        assert validate_value(1, float) == 1.0
        assert validate_value("1.1", float) == 1.1
        assert validate_value(True, float) == 1.0
        assert validate_value(False, float) == 0.0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[<class 'float'>] input_type=[<class 'str'>]\n  E: could not convert string to float: 'a'"
            ),
        ):
            validate_value("a", float)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'float'>] input_type=[<class 'NoneType'>]\n"
                    "  E: float() argument must be a string or a real number, not 'NoneType'"
                )
            ),
        ):
            validate_value(None, float)

    def test_str(self):
        assert validate_value(0, str) == "0"
        assert validate_value("a", str) == "a"
        assert validate_value(None, str) == "None"
        assert validate_value(True, str) == "True"
        assert validate_value(False, str) == "False"

    def test_bytes(self):
        assert validate_value(b"b", bytes) == b"b"
        assert validate_value("b", bytes) == b"b"
        assert validate_value(0, bytes) == b""
        assert validate_value(1, bytes) == b"\x00"
        assert validate_value(False, bytes) == b""
        assert validate_value(True, bytes) == b"\x00"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[<class 'bytes'>] input_type=[<class 'float'>]\n  E: cannot convert 'float' object to bytes"
            ),
        ):
            validate_value(1.1, bytes)

    def test_datetime(self):
        assert validate_value(
            "2023-01-01T00:00:00+00:00",
            datetime,
        ) == datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
        assert validate_value(
            datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime,
        ) == datetime(2023, 1, 1, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[<class 'datetime.datetime'>] input_type=[<class 'str'>]\n  E: Invalid isoformat string: '2023'"
            ),
        ):
            validate_value("2023", datetime)

    def test_date(self):
        assert validate_value("2023-01-01", date) == date(2023, 1, 1)
        assert validate_value(date(2023, 1, 1), date) == date(2023, 1, 1)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[<class 'datetime.date'>] input_type=[<class 'str'>]\n  E: Invalid isoformat string: '2023'"
            ),
        ):
            validate_value("2023", date)

    def test_literal(self):
        validate_value("A", Literal["A", "B"])
        validate_value("B", Literal["A", "B"])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[typing.Literal['A', 'B']] input_type=[<class 'str'>]\n  E: value is not a one of ['A', 'B']"
            ),
        ):
            validate_value("C", Literal["A", "B"])
        with pytest.raises(
            ValidationError,
            match=re.escape("type=[typing.Literal['1']] input_type=[<class 'int'>]\n  E: value is not a one of ['1']"),
        ):
            validate_value(1, Literal["1"])
        with pytest.raises(
            ValidationError,
            match=re.escape("type=[typing.Literal[1]] input_type=[<class 'str'>]\n  E: value is not a one of [1]"),
        ):
            validate_value("1", Literal[1])

    def test_enum(self):
        class E(str, Enum):
            A = "a"

        assert isinstance(validate_value("a", E), E)
        assert validate_value("a", E) == E.A
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<enum 'E'>] input_type=[<class 'int'>]\n"
                    "  E: 1 is not a valid TestValidateValue.test_enum.<locals>.E"
                )
            ),
        ):
            validate_value(1, E)

    def test_list(self):
        for T in (list, List):
            assert validate_value([], T) == []
            assert validate_value((), T) == []
            assert validate_value([], T[int]) == []
            assert validate_value((), T[int]) == []
            assert validate_value([0, 1], T) == [0, 1]
            assert validate_value((0, 1), T) == [0, 1]
            assert validate_value([0, 1], T[int]) == [0, 1]
            assert validate_value((0, 1), T[int]) == [0, 1]
            assert validate_value([0, 1], T[str]) == ["0", "1"]
            assert validate_value((0, 1), T[str]) == ["0", "1"]
            assert validate_value([0, "1"], T[int]) == [0, 1]
            assert validate_value((0, "1"), T[int]) == [0, 1]
            assert validate_value([[0], (1,)], T[T[int]]) == [[0], [1]]
            assert validate_value(([0], (1,)), T[T[int]]) == [[0], [1]]
            assert validate_value([[0], ("1",)], T[T[int]]) == [[0], [1]]
            assert validate_value(([0], ("1",)), T[T[int]]) == [[0], [1]]
            assert validate_value([["0"], ("y",)], T[T[bool]]) == [[False], [True]]
            assert validate_value((["0"], ("y",)), T[T[bool]]) == [[False], [True]]

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[list[int]] path=[1] input_type=[<class 'list'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], list[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.List[int]] path=[1] input_type=[<class 'list'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], List[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[list[int]] path=[1] input_type=[<class 'tuple'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), list[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.List[int]] path=[1] input_type=[<class 'tuple'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), List[int])

    def test_tuple(self):
        for T in (tuple, Tuple):
            assert validate_value((), T) == ()
            assert validate_value([], T) == ()
            assert validate_value((), T[int]) == ()
            assert validate_value([], T[int]) == ()
            assert validate_value((0, 1), T) == (0, 1)
            assert validate_value([0, 1], T) == (0, 1)
            assert validate_value((0, 1), T[int, int]) == (0, 1)
            assert validate_value([0, 1], T[int, int]) == (0, 1)
            assert validate_value((0, 1), T[int, str]) == (0, "1")
            assert validate_value([0, 1], T[int, str]) == (0, "1")
            assert validate_value((0, "1"), T[int, ...]) == (0, 1)
            assert validate_value([0, "1"], T[int, ...]) == (0, 1)
            assert validate_value((0, 1, "2"), T[int, ...]) == (0, 1, 2)
            assert validate_value([0, 1, "2"], T[int, ...]) == (0, 1, 2)
            assert validate_value(([0], [1]), T[list[int], list[int]]) == ([0], [1])
            assert validate_value([[0], [1]], T[list[int], list[int]]) == ([0], [1])
            assert validate_value(([0], ["1"]), T[list[int], list[int]]) == ([0], [1])
            assert validate_value([[0], ["1"]], T[list[int], list[int]]) == ([0], [1])
            assert validate_value((["0"], ["y"]), T[list[bool], tuple[bool]]) == ([False], (True,))
            assert validate_value([["0"], ["y"]], T[list[bool], tuple[bool]]) == ([False], (True,))
            assert validate_value(tuple(range(100)), T[int, ...]) == tuple(range(100))
            assert validate_value(list(range(100)), T[int, ...]) == tuple(range(100))

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[tuple[int, int]] path=[1] input_type=[<class 'tuple'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), tuple[int, int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Tuple[int, int]] path=[1] input_type=[<class 'tuple'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), Tuple[int, int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[tuple[int, int]] path=[1] input_type=[<class 'list'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], tuple[int, int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Tuple[int, int]] path=[1] input_type=[<class 'list'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], Tuple[int, int])

    def test_set(self):
        for T in (set, Set):
            assert validate_value(set(), T) == set()
            assert validate_value([], T) == set()
            assert validate_value(set(), T[int]) == set()
            assert validate_value([], T[int]) == set()
            assert validate_value({0, 1}, T) == {0, 1}
            assert validate_value([0, 1], T) == {0, 1}
            assert validate_value({0, 1}, T[int]) == {0, 1}
            assert validate_value([0, 1], T[int]) == {0, 1}
            assert validate_value({"0", "1"}, T[int]) == {0, 1}
            assert validate_value(["0", "1"], T[int]) == {0, 1}
            assert validate_value([{0}, {1}], T[tuple[int]]) == {(0,), (1,)}
            assert validate_value([[0], [1]], T[tuple[int]]) == {(0,), (1,)}
            assert validate_value([{"0"}, {"1"}], T[tuple[int]]) == {(0,), (1,)}
            assert validate_value([["0"], ["1"]], T[tuple[int]]) == {(0,), (1,)}

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[set[int]] path=[1] input_type=[<class 'list'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], set[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Set[int]] path=[1] input_type=[<class 'list'>]\n"
                    "  E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], Set[int])

    def test_mapping(self):
        for T in (dict, Dict, Mapping):
            assert validate_value({}, T) == {}
            assert validate_value({"k": "v"}, T) == {"k": "v"}
            assert validate_value({"k": "v"}, T[str, str]) == {"k": "v"}
            assert validate_value({"0": "1"}, T[int, int]) == {0: 1}
            assert validate_value({}, T) == {}
            assert validate_value({"k": "v"}, T) == {"k": "v"}
            assert validate_value({"k": "v"}, T[str, str]) == {"k": "v"}
            assert validate_value({"0": "1"}, T[int, int]) == {0: 1}

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[dict[str, dict[str, int]]] path=['k', 'kk'] input_type=[<class 'dict'>]\n"
                    "  type=[dict[str, int]] path=['kk'] input_type=[<class 'dict'>]\n"
                    "    E: invalid literal for int() with base 10: 'v'"
                )
            ),
        ):
            assert validate_value({"k": {"kk": "v"}}, dict[str, dict[str, int]])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Dict[str, dict[str, int]]] path=['k', 'kk'] input_type=[<class 'dict'>]\n"
                    "  type=[dict[str, int]] path=['kk'] input_type=[<class 'dict'>]\n"
                    "    E: invalid literal for int() with base 10: 'v'"
                )
            ),
        ):
            assert validate_value({"k": {"kk": "v"}}, Dict[str, dict[str, int]])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[collections.abc.Mapping[str, dict[str, int]]] path=['k', 'kk'] input_type=[<class 'dict'>]\n"
                    "  type=[dict[str, int]] path=['kk'] input_type=[<class 'dict'>]\n"
                    "    E: invalid literal for int() with base 10: 'v'"
                )
            ),
        ):
            assert validate_value({"k": {"kk": "v"}}, Mapping[str, dict[str, int]])

    def test_abcmeta(self):
        assert validate_value([1], Iterable) == [1]
        assert validate_value([1], Iterable[int]) == [1]
        assert validate_value([1], Sequence) == [1]
        assert validate_value([1], Sequence[int]) == [1]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'collections.abc.Iterable'>] input_type=[<class 'int'>]\n"
                    "  E: value is not a valid <class 'collections.abc.Iterable'>"
                )
            ),
        ):
            validate_value(1, Iterable)

    def test_type(self):
        class A:
            pass

        class B(A):
            pass

        class C:
            pass

        assert validate_value(A, Type[A]) == A
        assert validate_value(B, Type[A]) == B
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Type[test_cwtch.TestValidateValue.test_type.<locals>.A]] input_type=[<class 'type'>]\n"
                    "  E: invalid value for typing.Type[test_cwtch.TestValidateValue.test_type.<locals>.A]"
                )
            ),
        ):
            validate_value(C, Type[A])

    def test_union(self):
        assert validate_value(1, int | str) == 1
        assert validate_value(1, Union[int, str]) == 1
        assert validate_value(1, str | int) == 1
        assert validate_value(1, Union[str, int]) == 1
        assert validate_value(1, str | float) == "1"
        assert validate_value(1, Union[str, float]) == "1"
        assert validate_value(1, float | str) == 1.0
        assert validate_value(1, Union[float | str]) == 1.0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[int | float] input_type=[<class 'str'>]\n"
                    "  type=[<class 'int'>] input_type=[<class 'str'>]\n"
                    "    E: invalid literal for int() with base 10: 'a'\n"
                    "  type=[<class 'float'>] input_type=[<class 'str'>]\n"
                    "    E: could not convert string to float: 'a'"
                )
            ),
        ):
            assert validate_value("a", int | float) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Union[int, float]] input_type=[<class 'str'>]\n"
                    "  type=[<class 'int'>] input_type=[<class 'str'>]\n"
                    "    E: invalid literal for int() with base 10: 'a'\n"
                    "  type=[<class 'float'>] input_type=[<class 'str'>]\n"
                    "    E: could not convert string to float: 'a'"
                )
            ),
        ):
            assert validate_value("a", Union[int, float]) == "a"

        T = Annotated[int | float, Ge(1)]
        assert validate_value("a", T | str) == "a"
        assert validate_value("a", Union[T, str]) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Union[typing.Annotated[int | float, Ge(value=1)], bool]] input_type=[<class 'str'>]\n"
                    "  type=[int | float] input_type=[<class 'str'>]\n"
                    "    type=[<class 'int'>] input_type=[<class 'str'>]\n"
                    "      E: invalid literal for int() with base 10: 'a'\n"
                    "    type=[<class 'float'>] input_type=[<class 'str'>]\n"
                    "      E: could not convert string to float: 'a'\n"
                    "  type=[<class 'bool'>] input_type=[<class 'str'>]\n"
                    "    E: could not convert value to bool"
                )
            ),
        ):
            assert validate_value("a", T | bool) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Union[typing.Annotated[int | float, Ge(value=1)], bool]] input_type=[<class 'str'>]\n"
                    "  type=[int | float] input_type=[<class 'str'>]\n"
                    "    type=[<class 'int'>] input_type=[<class 'str'>]\n"
                    "      E: invalid literal for int() with base 10: 'a'\n"
                    "    type=[<class 'float'>] input_type=[<class 'str'>]\n"
                    "      E: could not convert string to float: 'a'\n"
                    "  type=[<class 'bool'>] input_type=[<class 'str'>]\n"
                    "    E: could not convert value to bool"
                )
            ),
        ):
            assert validate_value("a", Union[T, bool]) == "a"

        assert validate_value(1, int | Any) == 1
        assert validate_value(1, Union[int, Any]) == 1
        assert validate_value("1", int | Any) == "1"
        assert validate_value("1", Union[int, Any]) == "1"


class TestMetadata:
    def test_ge(self):
        assert validate_value(1, Annotated[int, Ge(1)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[typing.Annotated[int, Ge(value=1)]] input_type=[<class 'int'>]\n  E: value should be >= 1"
            ),
        ):
            validate_value(0, Annotated[int, Ge(1)])

        assert validate_value(1, Annotated[Annotated[int, Ge(0)], Ge(1)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[int, Ge(value=2), Ge(value=1)]] input_type=[<class 'int'>]\n"
                    "  E: value should be >= 2"
                )
            ),
        ):
            validate_value(1, Annotated[Annotated[int, Ge(2)], Ge(1)])

    def test_gt(self):
        assert validate_value(1, Annotated[int, Gt(0)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[typing.Annotated[int, Gt(value=0)]] input_type=[<class 'int'>]\n  E: value should be > 0"
            ),
        ):
            validate_value(0, Annotated[int, Gt(0)])

        assert validate_value(2, Annotated[Annotated[int, Gt(0)], Gt(1)]) == 2
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[int, Gt(value=2), Gt(value=1)]] input_type=[<class 'int'>]\n"
                    "  E: value should be > 2"
                )
            ),
        ):
            validate_value(2, Annotated[Annotated[int, Gt(2)], Gt(1)])

    def test_le(self):
        assert validate_value(1, Annotated[int, Le(1)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[typing.Annotated[int, Le(value=1)]] input_type=[<class 'int'>]\n  E: value should be <= 1"
            ),
        ):
            validate_value(2, Annotated[int, Le(1)])

        assert validate_value(0, Annotated[Annotated[int, Le(0)], Le(1)]) == 0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[int, Le(value=1), Le(value=2)]] input_type=[<class 'int'>]\n"
                    "  E: value should be <= 1"
                )
            ),
        ):
            validate_value(2, Annotated[Annotated[int, Le(1)], Le(2)])

    def test_lt(self):
        assert validate_value(0, Annotated[int, Lt(1)]) == 0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                "type=[typing.Annotated[int, Lt(value=0)]] input_type=[<class 'int'>]\n  E: value should be < 0"
            ),
        ):
            validate_value(0, Annotated[int, Lt(0)])

        assert validate_value(0, Annotated[Annotated[int, Lt(1)], Lt(2)]) == 0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[int, Lt(value=0), Lt(value=1)]] input_type=[<class 'int'>]\n"
                    "  E: value should be < 0"
                )
            ),
        ):
            validate_value(0, Annotated[Annotated[int, Lt(0)], Lt(1)])

    def test_validate_min_len(self):
        assert validate_value([0], Annotated[list, MinLen(1)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MinLen(value=1)]] input_type=[<class 'list'>]\n"
                    "  E: value length should be >= 1"
                )
            ),
        ):
            validate_value([], Annotated[list, MinLen(1)])

        assert validate_value([0, 1], Annotated[Annotated[list, MinLen(2)], MinLen(1)]) == [0, 1]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MinLen(value=2), MinLen(value=1)]] input_type=[<class 'list'>]\n"
                    "  E: value length should be >= 2"
                )
            ),
        ):
            validate_value([0], Annotated[Annotated[list, MinLen(2)], MinLen(1)])

    def test_validate_max_len(self):
        assert validate_value([0], Annotated[list, MaxLen(1)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MaxLen(value=1)]] input_type=[<class 'list'>]\n"
                    "  E: value length should be <= 1"
                )
            ),
        ):
            validate_value([0, 1], Annotated[list, MaxLen(1)])

        assert validate_value([0], Annotated[Annotated[list, MaxLen(1)], MaxLen(2)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MaxLen(value=1), MaxLen(value=2)]] input_type=[<class 'list'>]\n"
                    "  E: value length should be <= 1"
                )
            ),
        ):
            validate_value([0, 1], Annotated[Annotated[list, MaxLen(1)], MaxLen(2)])

    def test_validate_min_items(self):
        assert validate_value([0], Annotated[list, MinItems(1)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MinItems(value=1)]] input_type=[<class 'list'>]\n"
                    "  E: items count should be >= 1"
                )
            ),
        ):
            validate_value([], Annotated[list, MinItems(1)])

        assert validate_value([0, 1], Annotated[Annotated[list, MinItems(2)], MinItems(1)]) == [0, 1]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MinItems(value=2), MinItems(value=1)]] input_type=[<class 'list'>]\n"
                    "  E: items count should be >= 2"
                )
            ),
        ):
            validate_value([0], Annotated[Annotated[list, MinItems(2)], MinItems(1)])

    def test_validate_max_items(self):
        assert validate_value([0], Annotated[list, MaxItems(1)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MaxItems(value=1)]] input_type=[<class 'list'>]\n"
                    "  E: items count should be <= 1"
                )
            ),
        ):
            validate_value([0, 1], Annotated[list, MaxItems(1)])

        assert validate_value([0], Annotated[Annotated[list, MaxItems(1)], MaxItems(2)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[list, MaxItems(value=1), MaxItems(value=2)]] input_type=[<class 'list'>]\n"
                    "  E: items count should be <= 1"
                )
            ),
        ):
            validate_value([0, 1], Annotated[Annotated[list, MaxItems(1)], MaxItems(2)])

    def test_validate_annotated_complex(self):
        assert validate_value([1, 2], list[Annotated[int, Ge(1)]]) == [1, 2]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[list[typing.Annotated[int, Ge(value=1)]]] path=[2] input_type=[<class 'list'>]\n"
                    "  E: value should be >= 1"
                )
            ),
        ):
            validate_value([1, 2, 0], list[Annotated[int, Ge(1)]])

        assert validate_value((1, 2), list[Annotated[int, Ge(1)]]) == [1, 2]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[list[typing.Annotated[int, Ge(value=1)]]] path=[2] input_type=[<class 'tuple'>]\n"
                    "  E: value should be >= 1"
                )
            ),
        ):
            validate_value((1, 2, 0), list[Annotated[int, Ge(1)]])

    def test_lower(self):
        assert validate_value("A", LowerStr) == "a"
        assert validate_value(1, LowerStr) == "1"

    def test_upper(self):
        assert validate_value("a", UpperStr) == "A"
        assert validate_value(1, UpperStr) == "1"

    def test_strict_int(self):
        assert validate_value(1, StrictInt) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[int, Strict(type=[<class 'int'>])]] input_type=[<class 'str'>]\n"
                    "  E: invalid value for <class 'int'>"
                )
            ),
        ):
            validate_value("1", StrictInt)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[int, Strict(type=[<class 'int'>])]] input_type=[<class 'bool'>]\n"
                    "  E: invalid value for <class 'int'>"
                )
            ),
        ):
            validate_value(True, StrictInt)

    def test_strict_float(self):
        assert validate_value(1.1, StrictFloat) == 1.1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[float, Strict(type=[<class 'float'>])]] input_type=[<class 'int'>]\n"
                    "  E: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value(1, StrictFloat)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[float, Strict(type=[<class 'float'>])]] input_type=[<class 'bool'>]\n"
                    "  E: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value(True, StrictFloat)

    def test_strict_number(self):
        assert validate_value(1, StrictNumber) == 1
        assert validate_value(1.1, StrictNumber) == 1.1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Union[typing.Annotated[int, Strict(type=[<class 'int'>])], "
                    "typing.Annotated[float, Strict(type=[<class 'float'>])]]] input_type=[<class 'str'>]\n"
                    "  type=[typing.Annotated[int, Strict(type=[<class 'int'>])]] input_type=[<class 'str'>]\n"
                    "    E: invalid value for <class 'int'>\n"
                    "  type=[typing.Annotated[float, Strict(type=[<class 'float'>])]] input_type=[<class 'str'>]\n"
                    "    E: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value("1", StrictNumber)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Union[typing.Annotated[int, Strict(type=[<class 'int'>])], "
                    "typing.Annotated[float, Strict(type=[<class 'float'>])]]] input_type=[<class 'bool'>]\n"
                    "  type=[typing.Annotated[int, Strict(type=[<class 'int'>])]] input_type=[<class 'bool'>]\n"
                    "    E: invalid value for <class 'int'>\n"
                    "  type=[typing.Annotated[float, Strict(type=[<class 'float'>])]] input_type=[<class 'bool'>]\n"
                    "    E: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value(True, StrictNumber)

    def test_strict_str(self):
        assert validate_value("a", StrictStr) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[str, Strict(type=[<class 'str'>])]] input_type=[<class 'int'>]\n"
                    "  E: invalid value for <class 'str'>"
                )
            ),
        ):
            validate_value(1, StrictStr)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[str, Strict(type=[<class 'str'>])]] input_type=[<class 'bool'>]\n"
                    "  E: invalid value for <class 'str'>"
                )
            ),
        ):
            validate_value(True, StrictStr)

    def test_strict_bool(self):
        assert validate_value(True, StrictBool) is True
        assert validate_value(False, StrictBool) is False
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[typing.Annotated[bool, Strict(type=[<class 'bool'>])]] input_type=[<class 'int'>]\n"
                    "  E: invalid value for <class 'bool'>"
                )
            ),
        ):
            validate_value(1, StrictBool)


class TestModel:
    def test_model_simple(self):
        @dataclass
        class M:
            i: int
            s: str

        assert validate_value({"i": 1, "s": "s"}, M) == M(i=1, s="s")

    def test_model(self):
        @dataclass(slots=True)
        class A:
            i: int
            s: str
            b: bool
            l: list
            t: tuple
            li: list[int]
            ti: tuple[int, ...]
            d: dict
            dd: dict[str, int]
            ai: Annotated[int, Ge(0)]
            al: Annotated[list[int], MinLen(1)]

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

        @dataclass
        class M:
            i: int
            s: str = "s"

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'test_cwtch.TestModel.test_model.<locals>.M'>] path=['i'] input_type=[<class 'str'>]\n"
                    "  type=[<class 'int'>] input_type=[<class 'str'>]\n"
                    "    E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            M(i="a")

    def test_list(self):
        @dataclass
        class M:
            i: int

        assert validate_value(({"i": 0}, {"i": 1}), list[M]) == [M(i=0), M(i=1)]

    def test_tuple(self):
        @dataclass
        class M:
            i: int

        assert validate_value([{"i": 0}, {"i": 1}], tuple[M, M]) == (M(i=0), M(i=1))

    def test_set(self):
        @dataclass
        class M:
            i: int

            def __hash__(self):
                return hash(self.i)

        assert validate_value([{"i": 0}, {"i": 1}], set[M]) == {M(i=0), M(i=1)}

    def test_mapping(self):
        @dataclass
        class M:
            i: int

        assert validate_value({"m": {"i": 0}}, dict[str, M]) == {"m": M(i=0)}

    def test_forward_ref(self):
        B = ForwardRef("B")

        @dataclass
        class A:
            a1: "B"
            a2: B

        @dataclass
        class B:
            i: int

        A.cwtch_update_forward_refs(globals(), locals())

        a = validate_value({"a1": {"i": 1}, "a2": {"i": 2}}, A)
        assert a.a1.i == 1
        assert a.a2.i == 2

    def test_ignore_extra(self):
        @dataclass(ignore_extra=True)
        class A:
            i: int

        aa = A(i="1", s="a", b="false")
        assert aa.i == 1

    def test_env_prefix(self):
        @dataclass(env_prefix="TEST_", slots=True)
        class M:
            i: int = field(default=0, env_var=True)
            j: int = field(default_factory=lambda: 7, env_var=True)

        env = {}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 0
            assert M().j == 7

        env = {"TEST_I": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 1
            assert M().j == 7

        env = {"TEST_J": "0"}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 0
            assert M().j == 0

    def test_inheritance(self):
        @dataclass(slots=True)
        class A:
            i: int

        @dataclass(slots=True)
        class B(A):
            i: float
            s: str

        assert B.__dataclass_fields__["i"].type == float
        assert B.__dataclass_fields__["s"].type == str

    def test_generic(self):
        @dataclass
        class C(Generic[T]):
            x: list[T]

        assert validate_value({"x": ["1"]}, C[int]).x == [1]
        assert C[int](x=["1"]).x == [1]

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'test_cwtch.TestModel.test_generic.<locals>.C'>] path=['x'] input_type=[<class 'list'>]\n"
                    "  type=[list[int]] path=[0] input_type=[<class 'list'>]\n"
                    "    E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value({"x": ["a"]}, C[int])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'test_cwtch.TestModel.test_generic.<locals>.C'>] path=['x'] input_type=[<class 'list'>]\n"
                    "  type=[list[int]] path=[0] input_type=[<class 'list'>]\n"
                    "    E: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            C[int](x=["a"])

    def test_init(self):
        @dataclass
        class M:
            i: int

        M(i=0)

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'test_cwtch.TestModel.test_init.<locals>.M'>] "
                    "path=['i'] input_type=[<class 'dataclasses._MISSING_TYPE'>]\n"
                    "  E: TestModel.test_init.<locals>.M.__init__() missing required keyword-only argument: 'i'"
                )
            ),
        ):
            M()

        with pytest.raises(
            TypeError,
            match=re.escape("TestModel.test_init.<locals>.M.__init__() takes 1 positional argument but 2 were given"),
        ):
            M(0)

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type=[<class 'test_cwtch.TestModel.test_init.<locals>.M'>] "
                    "path=['M.__init__'] input_type=[<class 'dict'>]\n"
                    "  E: TestModel.test_init.<locals>.M.__init__() got an unexpected keyword argument 's'"
                )
            ),
        ):
            M(i=0, s="s")

    def test_post_init(self):
        @dataclass(slots=True)
        class A:
            x: int
            s: str | None = None

        @dataclass(slots=True)
        class B(A):
            x: float

            def __post_init__(self):
                super(B, self).__init__(x=self.x, s="s")

        b = B(x=1.1)
        assert b.x == 1.1
        assert b.s == "s"


class TestView:
    def test_view(self):
        @dataclass
        class A:
            i: int
            j: int
            s: str
            b: bool
            l: list[int]

            @view(include={"i", "j"})
            class V1:
                j: int = 0

            @view(exclude={"s", "b", "l"})
            class V2:
                j: int = 0

            @view
            class V3:
                f: float

            def foo(self):
                pass

        assert A.V1
        assert A.V1.__cwtch_view_name__ == "V1"
        assert A.V1.__cwtch_view_base__ == A
        assert A.V1.__annotations__ == {"j": int}

        assert A.V2
        assert A.V2.__cwtch_view_name__ == "V2"
        assert A.V2.__cwtch_view_base__ == A
        assert A.V2.__annotations__ == {"j": int}

        assert A.V3
        assert A.V3.__cwtch_view_name__ == "V3"
        assert A.V3.__cwtch_view_base__ == A
        assert A.V3.__annotations__ == {"f": float}

        aa = A(i="1", j="2", s="a", b="n", l=["1", "2"])
        assert aa.i == 1
        assert aa.j == 2
        assert aa.V1

        v1 = aa.V1()
        assert v1.__cwtch_view_name__ == "V1"
        assert v1.__cwtch_view_base__ == A
        assert v1.i == 1
        assert v1.j == 2

        v2 = aa.V2()
        assert v2.__cwtch_view_name__ == "V2"
        assert v2.__cwtch_view_base__ == A
        assert v2.i == 1
        assert v2.j == 2

        assert asdict(v1) == asdict(v2) == {"i": 1, "j": 2}

        v2 = A.V2(i=1)
        assert v2.i == 1
        assert v2.j == 0
        assert asdict(v2) == {"i": 1, "j": 0}

        v3 = A.V3(i=1, j=2, s="a", b=False, l=[], f=1.1)

    def test_ignore_extra(self):
        @dataclass
        class A:
            i: int

            @view(ignore_extra=True)
            class V:
                pass

        v = A.V(i="1", s="a", b="n")
        assert v.i == 1

    def test_validate(self):
        @dataclass
        class A:
            i: int

            @view
            class V1:
                pass

            @view(validate=False)
            class V2:
                pass

        assert A.V1(i="1").i == 1
        assert A.V2(i="1").i == "1"

    def test_recursive(self):
        @dataclass
        class A:
            i: int | None = None
            s: str | None = None

            @view(include={"i"})
            class V:
                pass

        @dataclass
        class B:
            a: list[A] | None

            @view(recursive=True)
            class V:
                pass

        B(a=[A()])

        assert B.__dataclass_fields__["a"].type == list[A] | None
        assert B.V.__dataclass_fields__["a"].type == list[A.V] | None

    def test_inheritance(self):
        @dataclass(slots=True)
        class A:
            i: int

            @view
            class V1:
                pass

        @dataclass(slots=True)
        class B(A):
            s: str

            @view
            class V2:
                pass


class TestGeneric:
    def test_generic(self):
        @dataclass
        class C(Generic[T]):
            x: T

            @view
            class V1(Generic[F]):
                y: F

            @view(exclude={"x"})
            class V2:
                y: float

            @view(exclude={"x"})
            class V3(Generic[F]):
                y: F

            @view
            class V4:
                x: T = 0

            @view
            class V5(V4):
                pass

        assert C[int](x="1").x == 1
        assert C.V1[int, float](x="1", y="2.2").x == 1
        assert C.V1[int, float](x="1", y="2.2").y == 2.2
        assert C.V2(y="2.2").y == 2.2
        assert C.V3[float](y="2.2").y == 2.2
        assert C.V4[int](x="1").x == 1
        assert C.V4[int]().x == 0
        assert C.V5[int](x="1").x == 1
        assert C.V5[int]().x == 0

    def test_inheritance(self):
        @dataclass(slots=True)
        class A(Generic[T, F]):
            a: T
            b: Type[T] = T
            c: T = field(default_factory=T)
            d: T
            f: F

            @view
            class V1:
                d: str

            @view
            class V2:
                a: float = field(default_factory=T)

        @dataclass(slots=True)
        class B(A[int, float]):
            d: bool
            e: T

            @view
            class V2(A.V2):
                d: float
                f: float = 1.1

        assert A.V1.__annotations__ == {"d": str}
        assert A.V2.__annotations__ == {"a": float}

        assert B.V1.__annotations__ == {}
        assert B.V2.__annotations__ == {"d": float, "f": float}

        assert B.__dataclass_fields__["a"].type == int
        assert B.__dataclass_fields__["a"].default == MISSING
        assert B.__dataclass_fields__["a"].default_factory == MISSING
        assert B.__dataclass_fields__["b"].type == Type[int]
        assert B.__dataclass_fields__["b"].default == int
        assert B.__dataclass_fields__["b"].default_factory == MISSING
        assert B.__dataclass_fields__["c"].type == int
        assert B.__dataclass_fields__["c"].default == MISSING
        assert B.__dataclass_fields__["c"].default_factory == int
        assert B.__dataclass_fields__["d"].type == bool
        assert B.__dataclass_fields__["d"].default == MISSING
        assert B.__dataclass_fields__["d"].default_factory == MISSING
        assert B.__dataclass_fields__["e"].type == T
        assert B.__dataclass_fields__["e"].default == MISSING
        assert B.__dataclass_fields__["e"].default_factory == MISSING
        assert B.__dataclass_fields__["f"].type == float
        assert B.__dataclass_fields__["f"].default == MISSING
        assert B.__dataclass_fields__["f"].default_factory == MISSING

        assert B.V1.__dataclass_fields__["a"].type == int
        assert B.V1.__dataclass_fields__["a"].default == MISSING
        assert B.V1.__dataclass_fields__["a"].default_factory == MISSING
        assert B.V1.__dataclass_fields__["b"].type == Type[int]
        assert B.V1.__dataclass_fields__["b"].default == int
        assert B.V1.__dataclass_fields__["b"].default_factory == MISSING
        assert B.V1.__dataclass_fields__["c"].type == int
        assert B.V1.__dataclass_fields__["c"].default == MISSING
        assert B.V1.__dataclass_fields__["c"].default_factory == int
        assert B.V1.__dataclass_fields__["d"].type == bool
        assert B.V1.__dataclass_fields__["d"].default == MISSING
        assert B.V1.__dataclass_fields__["d"].default_factory == MISSING
        assert B.V1.__dataclass_fields__["e"].type == T
        assert B.V1.__dataclass_fields__["e"].default == MISSING
        assert B.V1.__dataclass_fields__["e"].default_factory == MISSING
        assert B.V1.__dataclass_fields__["f"].type == float
        assert B.V1.__dataclass_fields__["f"].default == MISSING
        assert B.V1.__dataclass_fields__["f"].default_factory == MISSING

        assert B.V2.__dataclass_fields__["a"].type == float
        assert B.V2.__dataclass_fields__["a"].default == MISSING
        assert B.V2.__dataclass_fields__["a"].default_factory == int
        assert B.V2.__dataclass_fields__["b"].type == Type[int]
        assert B.V2.__dataclass_fields__["b"].default == int
        assert B.V2.__dataclass_fields__["b"].default_factory == MISSING
        assert B.V2.__dataclass_fields__["c"].type == int
        assert B.V2.__dataclass_fields__["c"].default == MISSING
        assert B.V2.__dataclass_fields__["c"].default_factory == int
        assert B.V2.__dataclass_fields__["d"].type == float
        assert B.V2.__dataclass_fields__["d"].default == MISSING
        assert B.V2.__dataclass_fields__["d"].default_factory == MISSING
        assert B.V2.__dataclass_fields__["e"].type == T
        assert B.V2.__dataclass_fields__["e"].default == MISSING
        assert B.V2.__dataclass_fields__["e"].default_factory == MISSING
        assert B.V2.__dataclass_fields__["f"].type == float
        assert B.V2.__dataclass_fields__["f"].default == 1.1
        assert B.V2.__dataclass_fields__["f"].default_factory == MISSING


class TestJsonSchema:
    def test_make_json_schema(self):
        assert make_json_schema(int) == ({"type": "integer"}, {})
        assert make_json_schema(str) == ({"type": "string"}, {})
        assert make_json_schema(float) == ({"type": "number"}, {})
        assert make_json_schema(bool) == ({"type": "boolean"}, {})
        assert make_json_schema(list) == ({"type": "array"}, {})
        assert make_json_schema(list[int]) == ({"type": "array", "items": {"type": "integer"}}, {})
        assert make_json_schema(tuple) == ({"type": "array", "items": False}, {})
        assert make_json_schema(tuple[int, str]) == (
            {"type": "array", "prefixItems": [{"type": "integer"}, {"type": "string"}], "items": False},
            {},
        )
        assert make_json_schema(set) == ({"type": "array", "uniqueItems": True}, {})
        assert make_json_schema(set[int]) == ({"type": "array", "items": {"type": "integer"}, "uniqueItems": True}, {})
        assert make_json_schema(dict) == ({"type": "object"}, {})
        assert make_json_schema(Literal["A", 1]) == ({"enum": ["A", 1]}, {})
        assert make_json_schema(Annotated[int, Ge(1), Le(10)]) == ({"type": "integer", "minimum": 1, "maximum": 10}, {})
        assert make_json_schema(Annotated[int, Gt(1), Lt(10)]) == (
            {"type": "integer", "exclusiveMinimum": True, "minimum": 1, "exclusiveMaximum": True, "maximum": 10},
            {},
        )
        assert make_json_schema(Annotated[str, MinLen(1), MaxLen(10)]) == (
            {"type": "string", "minLength": 1, "maxLength": 10},
            {},
        )

        @dataclass
        class Model:
            i: Annotated[int, Ge(1), Lt(10)]
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

        @dataclass
        class GenericModel(Generic[T, F]):
            a: T
            b: list[F]

        assert make_json_schema(GenericModel[int, str]) == (
            {"$ref": "#/$defs/GenericModel"},
            {
                "GenericModel": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "array", "items": {"type": "string"}}},
                    "required": ["a", "b"],
                }
            },
        )

    def test_json_value_metadata(self):
        JsonList = Annotated[list, JsonValue()]
        JsonDict = Annotated[dict, JsonValue()]

        @dataclass
        class M:
            args: JsonList | None = None
            kwds: JsonDict | None = None

        m = M(args="[]", kwds="{}")
        assert m.args == []
        assert m.kwds == {}


def test_validate_call():
    def foo(s: str, i: int = None):
        pass

    assert validate_args(foo, ("a", 1), {}) == (("a", 1), {})
    assert validate_args(foo, ("a", "1"), {}) == (("a", 1), {})
    with pytest.raises(TypeError):
        validate_args(foo, ("a",), {"i": "a"})


def test_get_current_parameters():
    @dataclass
    class M(Generic[T]):
        v: T = field(default_factory=lambda: get_current_parameters()[T]())

    M[int]().v == 0
    M[float]().v == 0.0
    M[str]().v == ""
