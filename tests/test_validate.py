import re

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, NewType, Set, Tuple, Type, TypeVar, Union

import pytest

from cwtch import validate_value
from cwtch.errors import ValidationError
from cwtch.metadata import Ge
from cwtch.types import UNSET, UnsetType


class TestValidateValue:
    def test_none(self):
        assert validate_value(None, None) is None
        for value in (0, 0.0, 1000, ..., "a", True, False, UNSET, object(), (), [], {}, int):
            with pytest.raises(ValidationError, match=re.escape("ValueError: value is not a None")):
                validate_value(value, None)

    def test_unset(self):
        assert validate_value(UNSET, UnsetType) is UNSET
        for value in (0, 0.0, 1000, ..., "a", True, False, None, object(), (), [], {}, int):
            with pytest.raises(
                ValidationError, match=re.escape("ValueError: value is not a valid <class 'cwtch.core.UnsetType'>")
            ):
                validate_value(value, UnsetType)

    def test_bool(self):
        for value in (1, "1", "true", "True", "TRUE", "y", "Y", "t", "yes", "Yes", "YES"):
            assert validate_value(value, bool) is True
        for value in (0, "0", "false", "False", "FALSE", "n", "N", "f", "no", "No", "NO"):
            assert validate_value(value, bool) is False

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> <class 'bool'>\n"
                    "  Input: -2\n"
                    "  ValueError: could not convert value to bool"
                )
            ),
        ):
            validate_value(-2, bool)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> <class 'bool'>\n"
                    "  Input: 2\n"
                    "  ValueError: could not convert value to bool"
                )
            ),
        ):
            validate_value(2, bool)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> <class 'bool'>\n"
                    "  Input: 'ok'\n"
                    "  ValueError: could not convert value to bool"
                )
            ),
        ):
            validate_value("ok", bool)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> <class 'bool'>\n"
                    "  Input: 'fail'\n"
                    "  ValueError: could not convert value to bool"
                )
            ),
        ):
            validate_value("fail", bool)

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
                (
                    "\n"
                    "  Type: <class 'str'> --> <class 'int'>\n"
                    "  Input: 'a'\n"
                    "  ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value("a", int)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'NoneType'> --> <class 'int'>\n"
                    "  Input: None\n"
                    "  TypeError: int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"
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
                (
                    "\n"
                    "  Type: <class 'str'> --> <class 'float'>\n"
                    "  Input: 'a'\n"
                    "  ValueError: could not convert string to float: 'a'"
                )
            ),
        ):
            validate_value("a", float)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'NoneType'> --> <class 'float'>\n"
                    "  Input: None\n"
                    "  TypeError: float() argument must be a string or a real number, not 'NoneType'"
                )
            ),
        ):
            validate_value(None, float)

    def test_str(self):
        assert validate_value("a", str) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'NoneType'> --> <class 'str'>\n"
                    "  Input: None\n"
                    "  ValueError: value is not a valid <class 'str'>"
                )
            ),
        ):
            validate_value(None, str)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> <class 'str'>\n"
                    "  Input: 0\n"
                    "  ValueError: value is not a valid <class 'str'>"
                )
            ),
        ):
            validate_value(0, str)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'bool'> --> <class 'str'>\n"
                    "  Input: True\n"
                    "  ValueError: value is not a valid <class 'str'>"
                )
            ),
        ):
            validate_value(True, str)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'bool'> --> <class 'str'>\n"
                    "  Input: False\n"
                    "  ValueError: value is not a valid <class 'str'>"
                )
            ),
        ):
            validate_value(False, str)

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
                (
                    "\n"
                    "  Type: <class 'float'> --> <class 'bytes'>\n"
                    "  Input: 1.1\n"
                    "  TypeError: cannot convert 'float' object to bytes"
                )
            ),
        ):
            validate_value(1.1, bytes)

    def test_date(self):
        assert validate_value("2023-01-01", date) == date(2023, 1, 1)
        assert validate_value(date(2023, 1, 1), date) == date(2023, 1, 1)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> <class 'datetime.date'>\n"
                    "  Input: '2023'\n"
                    "  ValueError: Invalid isoformat string: '2023'"
                )
            ),
        ):
            validate_value("2023", date)

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
                (
                    "\n"
                    "  Type: <class 'str'> --> <class 'datetime.datetime'>\n"
                    "  Input: '2023'\n"
                    "  ValueError: Invalid isoformat string: '2023'"
                )
            ),
        ):
            validate_value("2023", datetime)

    def test_literal(self):
        validate_value("A", Literal["A", "B"])
        validate_value("B", Literal["A", "B"])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Literal['A', 'B']\n"
                    "  Input: 'C'\n"
                    "  ValueError: value is not a one of ['A', 'B']"
                )
            ),
        ):
            validate_value("C", Literal["A", "B"])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Literal['1']\n"
                    "  Input: 1\n"
                    "  ValueError: value is not a one of ['1']"
                )
            ),
        ):
            validate_value(1, Literal["1"])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Literal[1]\n"
                    "  Input: '1'\n"
                    "  ValueError: value is not a one of [1]"
                )
            ),
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
                    "\n"
                    "  Type: <class 'int'> --> <enum 'E'>\n"
                    "  Input: 1\n"
                    "  ValueError: 1 is not a valid TestValidateValue.test_enum.<locals>.E"
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
            assert validate_value(["0", "1"], T[str]) == ["0", "1"]
            assert validate_value(("0", "1"), T[str]) == ["0", "1"]
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
                    "\n"
                    "  Type: <class 'list'> --> list[int]\n"
                    "  Input: [0, 'a']\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], list[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> list[int]\n"
                    "  Input: [0, 'a']\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], List[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'tuple'> --> list[int]\n"
                    "  Input: (0, 'a')\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), list[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'tuple'> --> list[int]\n"
                    "  Input: (0, 'a')\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), List[int])

    def test_tuple(self):
        for T in (tuple, Tuple):
            assert validate_value((), T) == ()
            assert validate_value([], T) == ()
            # assert validate_value((), T[int]) == ()
            # assert validate_value([], T[int]) == ()
            assert validate_value((0, 1), T) == (0, 1)
            assert validate_value([0, 1], T) == (0, 1)
            assert validate_value((0, 1), T[int, int]) == (0, 1)
            assert validate_value([0, 1], T[int, int]) == (0, 1)
            assert validate_value((0, "1"), T[int, str]) == (0, "1")
            assert validate_value([0, "1"], T[int, str]) == (0, "1")
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
                    "\n"
                    "  Type: <class 'tuple'> --> tuple[int, int]\n"
                    "  Input: (0, 'a')\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), tuple[int, int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'tuple'> --> tuple[int, int]\n"
                    "  Input: (0, 'a')\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value((0, "a"), Tuple[int, int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> tuple[int, int]\n"
                    "  Input: [0, 'a']\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], tuple[int, int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> tuple[int, int]\n"
                    "  Input: [0, 'a']\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
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
                    "\n"
                    "  Type: <class 'list'> --> set[int]\n"
                    "  Input: [0, 'a']\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value([0, "a"], set[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> set[int]\n"
                    "  Input: [0, 'a']\n"
                    "  Path: [1]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
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
                    "\n"
                    "  Type: <class 'dict'> --> dict[str, dict[str, int]]\n"
                    "  Input: {'k': {'kk': 'v'}}\n"
                    "  Path: ['k', 'kk']\n"
                    "  ValidationError:\n"
                    "    Type: <class 'dict'> --> dict[str, int]\n"
                    "    Input: {'kk': 'v'}\n"
                    "    Path: ['kk']\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'int'>\n"
                    "      Input: 'v'\n"
                    "      ValueError: invalid literal for int() with base 10: 'v'"
                )
            ),
        ):
            assert validate_value({"k": {"kk": "v"}}, dict[str, dict[str, int]])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'dict'> --> dict[str, dict[str, int]]\n"
                    "  Input: {'k': {'kk': 'v'}}\n"
                    "  Path: ['k', 'kk']\n"
                    "  ValidationError:\n"
                    "    Type: <class 'dict'> --> dict[str, int]\n"
                    "    Input: {'kk': 'v'}\n"
                    "    Path: ['kk']\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'int'>\n"
                    "      Input: 'v'\n"
                    "      ValueError: invalid literal for int() with base 10: 'v'"
                )
            ),
        ):
            assert validate_value({"k": {"kk": "v"}}, Dict[str, dict[str, int]])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'dict'> --> collections.abc.Mapping[str, dict[str, int]]\n"
                    "  Input: {'k': {'kk': 'v'}}\n"
                    "  Path: ['k', 'kk']\n"
                    "  ValidationError:\n"
                    "    Type: <class 'dict'> --> dict[str, int]\n"
                    "    Input: {'kk': 'v'}\n"
                    "    Path: ['kk']\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'int'>\n"
                    "      Input: 'v'\n"
                    "      ValueError: invalid literal for int() with base 10: 'v'"
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
                    "\n"
                    "  Type: <class 'int'> --> <class 'collections.abc.Iterable'>\n"
                    "  Input: 1\n"
                    "  ValueError: value is not a valid <class 'collections.abc.Iterable'>"
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
                    "\n"
                    "  Type: <class 'type'> --> Type[test_validate.TestValidateValue.test_type.<locals>.A]\n"
                    "  Input: <class 'test_validate.TestValidateValue.test_type.<locals>.C'>\n"
                    "  ValueError: invalid value for type[test_validate.TestValidateValue.test_type.<locals>.A]"
                )
            ),
        ):
            validate_value(C, Type[A])

    def test_union(self):
        assert validate_value(1, int | str) == 1
        assert validate_value(1, Union[int, str]) == 1
        assert validate_value(1, str | int) == 1
        assert validate_value(1, Union[str, int]) == 1
        assert validate_value("1", str | float) == "1"
        assert validate_value("1", Union[str, float]) == "1"
        assert validate_value(1, float | str) == 1.0
        assert validate_value(1, Union[float | str]) == 1.0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Union[int, float]\n"
                    "  Input: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'float'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: could not convert string to float: 'a'"
                )
            ),
        ):
            assert validate_value("a", int | float) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Union[int, float]\n"
                    "  Input: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'float'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: could not convert string to float: 'a'"
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
                    "\n"
                    "  Type: <class 'str'> --> Union[Annotated[int | float, Ge(value=1)], bool]\n"
                    "  Input: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> int | float\n"
                    "    Input: 'a'\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'int'>\n"
                    "      Input: 'a'\n"
                    "      ValueError: invalid literal for int() with base 10: 'a'\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'float'>\n"
                    "      Input: 'a'\n"
                    "      ValueError: could not convert string to float: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'bool'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: could not convert value to bool"
                )
            ),
        ):
            assert validate_value("a", T | bool) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Union[Annotated[int | float, Ge(value=1)], bool]\n"
                    "  Input: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> int | float\n"
                    "    Input: 'a'\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'int'>\n"
                    "      Input: 'a'\n"
                    "      ValueError: invalid literal for int() with base 10: 'a'\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'float'>\n"
                    "      Input: 'a'\n"
                    "      ValueError: could not convert string to float: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'bool'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: could not convert value to bool"
                )
            ),
        ):
            assert validate_value("a", Union[T, bool]) == "a"

        assert validate_value(1, int | Any) == 1
        assert validate_value(1, Union[int, Any]) == 1
        assert validate_value("1", int | Any) == "1"
        assert validate_value("1", Union[int, Any]) == "1"

        T = Annotated[int, None] | str
        assert validate_value("1", T) == "1"
        T = Annotated[str, None] | int
        assert validate_value(1, T) == 1

        assert validate_value([1], list[int] | list[str]) == [1]
        assert validate_value(["a"], list[int] | list[str]) == ["a"]

    def test_validate_type_var(self):
        T = TypeVar("T")

        TT = list[T]

        assert validate_value(["1"], TT[int]) == [1]
        with pytest.raises(ValidationError):
            assert validate_value(["a"], TT[int])

    def test_validate_new_type(self):
        Int = NewType("Int", int)
        validate_value(1, Int)

        Number = NewType("Number", int | float)
        validate_value(1, Number)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> test_validate.Number\n"
                    "  Input: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'float'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: could not convert string to float: 'a'"
                )
            ),
        ):
            validate_value("a", Number)
