import re
import sys

from typing import Annotated

import pytest

from cwtch import validate_value
from cwtch.errors import ValidationError
from cwtch.metadata import Ge, Gt, Le, Lt, MaxItems, MaxLen, MinItems, MinLen
from cwtch.types import LowerStr, Number, Strict, UpperStr


class TestMetadata:
    def test_ge(self):
        assert validate_value(1, Annotated[int, Ge(1)]) == 1
        assert validate_value(1, Annotated[Annotated[int, Ge(0)], Ge(1)]) == 1

    def test_ge_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Ge(value=1)]\n"
                    "  Input: 0\n"
                    "  ValueError: value should be >= 1"
                )
            ),
        ):
            validate_value(0, Annotated[int, Ge(1)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Ge(value=2), Ge(value=1)]\n"
                    "  Input: 1\n"
                    "  ValueError: value should be >= 2"
                )
            ),
        ):
            validate_value(1, Annotated[Annotated[int, Ge(2)], Ge(1)])

    def test_gt(self):
        assert validate_value(1, Annotated[int, Gt(0)]) == 1
        assert validate_value(2, Annotated[Annotated[int, Gt(0)], Gt(1)]) == 2

    def test_gt_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Gt(value=0)]\n"
                    "  Input: 0\n"
                    "  ValueError: value should be > 0"
                )
            ),
        ):
            validate_value(0, Annotated[int, Gt(0)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Gt(value=2), Gt(value=1)]\n"
                    "  Input: 2\n"
                    "  ValueError: value should be > 2"
                )
            ),
        ):
            validate_value(2, Annotated[Annotated[int, Gt(2)], Gt(1)])

    def test_le(self):
        assert validate_value(1, Annotated[int, Le(1)]) == 1
        assert validate_value(0, Annotated[Annotated[int, Le(0)], Le(1)]) == 0

    def test_le_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Le(value=1)]\n"
                    "  Input: 2\n"
                    "  ValueError: value should be <= 1"
                )
            ),
        ):
            validate_value(2, Annotated[int, Le(1)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Le(value=1), Le(value=2)]\n"
                    "  Input: 2\n"
                    "  ValueError: value should be <= 1"
                )
            ),
        ):
            validate_value(2, Annotated[Annotated[int, Le(1)], Le(2)])

    def test_lt(self):
        assert validate_value(0, Annotated[int, Lt(1)]) == 0
        assert validate_value(0, Annotated[Annotated[int, Lt(1)], Lt(2)]) == 0

    def test_lt_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Lt(value=0)]\n"
                    "  Input: 0\n"
                    "  ValueError: value should be < 0"
                )
            ),
        ):
            validate_value(0, Annotated[int, Lt(0)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[int, Lt(value=0), Lt(value=1)]\n"
                    "  Input: 0\n"
                    "  ValueError: value should be < 0"
                )
            ),
        ):
            validate_value(0, Annotated[Annotated[int, Lt(0)], Lt(1)])

    def test_validate_min_len(self):
        assert validate_value("a", Annotated[str, MinLen(1)]) == "a"
        assert validate_value("ab", Annotated[Annotated[str, MinLen(2)], MinLen(1)]) == "ab"

    def test_validate_min_len_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Annotated[str, MinLen(value=1)]\n"
                    "  Input: ''\n"
                    "  ValueError: value length should be >= 1"
                )
            ),
        ):
            validate_value("", Annotated[str, MinLen(1)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Annotated[str, MinLen(value=2), MinLen(value=1)]\n"
                    "  Input: 'a'\n"
                    "  ValueError: value length should be >= 2"
                )
            ),
        ):
            validate_value("a", Annotated[Annotated[str, MinLen(2)], MinLen(1)])

    def test_validate_max_len(self):
        assert validate_value("a", Annotated[str, MaxLen(1)]) == "a"
        assert validate_value("a", Annotated[Annotated[str, MaxLen(1)], MaxLen(2)]) == "a"

    def test_validate_max_len_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Annotated[str, MaxLen(value=1)]\n"
                    "  Input: 'ab'\n"
                    "  ValueError: value length should be <= 1"
                )
            ),
        ):
            validate_value("ab", Annotated[str, MaxLen(1)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Annotated[str, MaxLen(value=1), MaxLen(value=2)]\n"
                    "  Input: 'ab'\n"
                    "  ValueError: value length should be <= 1"
                )
            ),
        ):
            validate_value("ab", Annotated[Annotated[str, MaxLen(1)], MaxLen(2)])

    def test_validate_min_items(self):
        assert validate_value([0], Annotated[list, MinItems(1)]) == [0]
        assert validate_value([0, 1], Annotated[Annotated[list, MinItems(2)], MinItems(1)]) == [0, 1]

    def test_validate_min_items_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> Annotated[list, MinItems(value=1)]\n"
                    "  Input: []\n"
                    "  ValueError: items count should be >= 1"
                )
            ),
        ):
            validate_value([], Annotated[list, MinItems(1)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> Annotated[list, MinItems(value=2), MinItems(value=1)]\n"
                    "  Input: [0]\n"
                    "  ValueError: items count should be >= 2"
                )
            ),
        ):
            validate_value([0], Annotated[Annotated[list, MinItems(2)], MinItems(1)])

    def test_validate_max_items(self):
        assert validate_value([0], Annotated[list, MaxItems(1)]) == [0]
        assert validate_value([0], Annotated[Annotated[list, MaxItems(1)], MaxItems(2)]) == [0]

    def test_validate_max_items_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> Annotated[list, MaxItems(value=1)]\n"
                    "  Input: [0, 1]\n"
                    "  ValueError: items count should be <= 1"
                )
            ),
        ):
            validate_value([0, 1], Annotated[list, MaxItems(1)])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> Annotated[list, MaxItems(value=1), MaxItems(value=2)]\n"
                    "  Input: [0, 1]\n"
                    "  ValueError: items count should be <= 1"
                )
            ),
        ):
            validate_value([0, 1], Annotated[Annotated[list, MaxItems(1)], MaxItems(2)])

    def test_validate_annotated_complex(self):
        assert validate_value([1, 2], list[Annotated[int, Ge(1)]]) == [1, 2]
        assert validate_value((1, 2), list[Annotated[int, Ge(1)]]) == [1, 2]

    def test_validate_annotated_complex_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'list'> --> list[Annotated[int, Ge(value=1)]]\n"
                    "  Input: [1, 2, 0]\n"
                    "  Path: [2]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'int'> --> Annotated[int, Ge(value=1)]\n"
                    "    Input: 0\n"
                    "    ValueError: value should be >= 1"
                )
            ),
        ):
            validate_value([1, 2, 0], list[Annotated[int, Ge(1)]])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'tuple'> --> list[Annotated[int, Ge(value=1)]]\n"
                    "  Input: (1, 2, 0)\n"
                    "  Path: [2]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'int'> --> Annotated[int, Ge(value=1)]\n"
                    "    Input: 0\n"
                    "    ValueError: value should be >= 1"
                )
            ),
        ):
            validate_value((1, 2, 0), list[Annotated[int, Ge(1)]])

    def test_lower(self):
        assert validate_value("A", LowerStr) == "a"
        assert validate_value("1", LowerStr) == "1"

    def test_upper(self):
        assert validate_value("a", UpperStr) == "A"
        assert validate_value("1", UpperStr) == "1"

    def test_strict_int(self):
        assert validate_value(1, Strict[int]) == 1

    def test_strict_int_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Annotated[int, Strict(type=[<class 'int'>])]\n"
                    "  Input: '1'\n"
                    "  ValueError: invalid value for <class 'int'>"
                )
            ),
        ):
            validate_value("1", Strict[int])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'bool'> --> Annotated[int, Strict(type=[<class 'int'>])]\n"
                    "  Input: True\n"
                    "  ValueError: invalid value for <class 'int'>"
                )
            ),
        ):
            validate_value(True, Strict[int])

    def test_strict_float(self):
        assert validate_value(1.1, Strict[float]) == 1.1

    def test_strict_float_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "  Input: 1\n"
                    "  ValueError: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value(1, Strict[float])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'bool'> --> Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "  Input: True\n"
                    "  ValueError: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value(True, Strict[float])

    def test_strict_number(self):
        assert validate_value(1, Strict[Number]) == 1
        assert validate_value(1.1, Strict[Number]) == 1.1

    def test_strict_number_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'str'> --> Union[Annotated[int, Strict(type=[<class 'int'>])], Annotated[float, Strict(type=[<class 'float'>])]]\n"
                    "  Input: '1'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> Annotated[int, Strict(type=[<class 'int'>])]\n"
                    "    Input: '1'\n"
                    "    ValueError: invalid value for <class 'int'>\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "    Input: '1'\n"
                    "    ValueError: invalid value for <class 'float'>"
                )
                if sys.version_info.minor < 14
                else (
                    "\n"
                    "  Type: <class 'str'> --> Annotated[int, Strict(type=[<class 'int'>])] | Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "  Input: '1'\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> Annotated[int, Strict(type=[<class 'int'>])]\n"
                    "    Input: '1'\n"
                    "    ValueError: invalid value for <class 'int'>\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "    Input: '1'\n"
                    "    ValueError: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value("1", Strict[Number])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'bool'> --> Union[Annotated[int, Strict(type=[<class 'int'>])], Annotated[float, Strict(type=[<class 'float'>])]]\n"
                    "  Input: True\n"
                    "  ValidationError:\n"
                    "    Type: <class 'bool'> --> Annotated[int, Strict(type=[<class 'int'>])]\n"
                    "    Input: True\n"
                    "    ValueError: invalid value for <class 'int'>\n"
                    "  ValidationError:\n"
                    "    Type: <class 'bool'> --> Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "    Input: True\n"
                    "    ValueError: invalid value for <class 'float'>"
                )
                if sys.version_info.minor < 14
                else (
                    "\n"
                    "  Type: <class 'bool'> --> Annotated[int, Strict(type=[<class 'int'>])] | Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "  Input: True\n"
                    "  ValidationError:\n"
                    "    Type: <class 'bool'> --> Annotated[int, Strict(type=[<class 'int'>])]\n"
                    "    Input: True\n"
                    "    ValueError: invalid value for <class 'int'>\n"
                    "  ValidationError:\n"
                    "    Type: <class 'bool'> --> Annotated[float, Strict(type=[<class 'float'>])]\n"
                    "    Input: True\n"
                    "    ValueError: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value(True, Strict[Number])

    def test_strict_str(self):
        assert validate_value("a", Strict[str]) == "a"

    def test_strict_str_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[str, Strict(type=[<class 'str'>])]\n"
                    "  Input: 1\n"
                    "  ValueError: invalid value for <class 'str'>"
                )
            ),
        ):
            validate_value(1, Strict[str])
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'bool'> --> Annotated[str, Strict(type=[<class 'str'>])]\n"
                    "  Input: True\n"
                    "  ValueError: invalid value for <class 'str'>"
                )
            ),
        ):
            validate_value(True, Strict[str])

    def test_strict_bool(self):
        assert validate_value(True, Strict[bool]) is True
        assert validate_value(False, Strict[bool]) is False

    def test_strict_bool_negative(self):
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'int'> --> Annotated[bool, Strict(type=[<class 'bool'>])]\n"
                    "  Input: 1\n"
                    "  ValueError: invalid value for <class 'bool'>"
                )
            ),
        ):
            validate_value(1, Strict[bool])
