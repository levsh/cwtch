import os
import re

from typing import Annotated, ForwardRef, Generic, Literal, Optional, TypeVar
from unittest import mock

import pytest

from cwtch import asdict, dataclass, field, make_json_schema, validate_args, validate_value, view
from cwtch.errors import ValidationError
from cwtch.metadata import Ge, Gt, JsonLoads, Le, Lt, MaxItems, MaxLen, MinItems, MinLen
from cwtch.types import _MISSING, UNSET, LowerStr, StrictBool, StrictFloat, StrictInt, StrictNumber, StrictStr, UpperStr


T = TypeVar("T")
F = TypeVar("F")


class TestMetadata:
    def test_ge(self):
        assert validate_value(1, Annotated[int, Ge(1)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Ge(value=1)] ] value_type[ <class 'int'> ] value[ 0 ]\n"
                    "  Error: value should be >= 1"
                )
            ),
        ):
            validate_value(0, Annotated[int, Ge(1)])

        assert validate_value(1, Annotated[Annotated[int, Ge(0)], Ge(1)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Ge(value=2), Ge(value=1)] ] value_type[ <class 'int'> ] value[ 1 ]\n"
                    "  Error: value should be >= 2"
                )
            ),
        ):
            validate_value(1, Annotated[Annotated[int, Ge(2)], Ge(1)])

    def test_gt(self):
        assert validate_value(1, Annotated[int, Gt(0)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Gt(value=0)] ] value_type[ <class 'int'> ] value[ 0 ]\n"
                    "  Error: value should be > 0"
                )
            ),
        ):
            validate_value(0, Annotated[int, Gt(0)])

        assert validate_value(2, Annotated[Annotated[int, Gt(0)], Gt(1)]) == 2
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Gt(value=2), Gt(value=1)] ] value_type[ <class 'int'> ] value[ 2 ]\n"
                    "  Error: value should be > 2"
                )
            ),
        ):
            validate_value(2, Annotated[Annotated[int, Gt(2)], Gt(1)])

    def test_le(self):
        assert validate_value(1, Annotated[int, Le(1)]) == 1
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Le(value=1)] ] value_type[ <class 'int'> ] value[ 2 ]\n"
                    "  Error: value should be <= 1"
                )
            ),
        ):
            validate_value(2, Annotated[int, Le(1)])

        assert validate_value(0, Annotated[Annotated[int, Le(0)], Le(1)]) == 0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Le(value=1), Le(value=2)] ] value_type[ <class 'int'> ] value[ 2 ]\n"
                    "  Error: value should be <= 1"
                )
            ),
        ):
            validate_value(2, Annotated[Annotated[int, Le(1)], Le(2)])

    def test_lt(self):
        assert validate_value(0, Annotated[int, Lt(1)]) == 0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Lt(value=0)] ] value_type[ <class 'int'> ] value[ 0 ]\n"
                    "  Error: value should be < 0"
                )
            ),
        ):
            validate_value(0, Annotated[int, Lt(0)])

        assert validate_value(0, Annotated[Annotated[int, Lt(1)], Lt(2)]) == 0
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Lt(value=0), Lt(value=1)] ] value_type[ <class 'int'> ] value[ 0 ]\n"
                    "  Error: value should be < 0"
                )
            ),
        ):
            validate_value(0, Annotated[Annotated[int, Lt(0)], Lt(1)])

    def test_validate_min_len(self):
        assert validate_value("a", Annotated[str, MinLen(1)]) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[str, MinLen(value=1)] ] value_type[ <class 'str'> ] value[ '' ]\n"
                    "  Error: value length should be >= 1"
                )
            ),
        ):
            validate_value("", Annotated[str, MinLen(1)])

        assert validate_value("ab", Annotated[Annotated[str, MinLen(2)], MinLen(1)]) == "ab"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[str, MinLen(value=2), MinLen(value=1)] ] value_type[ <class 'str'> ] value[ 'a' ]\n"
                    "  Error: value length should be >= 2"
                )
            ),
        ):
            validate_value("a", Annotated[Annotated[str, MinLen(2)], MinLen(1)])

    def test_validate_max_len(self):
        assert validate_value("a", Annotated[str, MaxLen(1)]) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[str, MaxLen(value=1)] ] value_type[ <class 'str'> ] value[ 'ab' ]\n"
                    "  Error: value length should be <= 1"
                )
            ),
        ):
            validate_value("ab", Annotated[str, MaxLen(1)])

        assert validate_value("a", Annotated[Annotated[str, MaxLen(1)], MaxLen(2)]) == "a"
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[str, MaxLen(value=1), MaxLen(value=2)] ] value_type[ <class 'str'> ] value[ 'ab' ]\n"
                    "  Error: value length should be <= 1"
                )
            ),
        ):
            validate_value("ab", Annotated[Annotated[str, MaxLen(1)], MaxLen(2)])

    def test_validate_min_items(self):
        assert validate_value([0], Annotated[list, MinItems(1)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[list, MinItems(value=1)] ] value_type[ <class 'list'> ] value[ [] ]\n"
                    "  Error: items count should be >= 1"
                )
            ),
        ):
            validate_value([], Annotated[list, MinItems(1)])

        assert validate_value([0, 1], Annotated[Annotated[list, MinItems(2)], MinItems(1)]) == [0, 1]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[list, MinItems(value=2), MinItems(value=1)] ] value_type[ <class 'list'> ] value[ [0] ]\n"
                    "  Error: items count should be >= 2"
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
                    "type[ Annotated[list, MaxItems(value=1)] ] value_type[ <class 'list'> ] value[ [0, 1] ]\n"
                    "  Error: items count should be <= 1"
                )
            ),
        ):
            validate_value([0, 1], Annotated[list, MaxItems(1)])

        assert validate_value([0], Annotated[Annotated[list, MaxItems(1)], MaxItems(2)]) == [0]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[list, MaxItems(value=1), MaxItems(value=2)] ] value_type[ <class 'list'> ] value[ [0, 1] ]\n"
                    "  Error: items count should be <= 1"
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
                    "type[ list[Annotated[int, Ge(value=1)]] ] path[ 2 ] value_type[ <class 'list'> ] path_value[ 0 ]\n"
                    "  Error: value should be >= 1"
                )
            ),
        ):
            validate_value([1, 2, 0], list[Annotated[int, Ge(1)]])

        assert validate_value((1, 2), list[Annotated[int, Ge(1)]]) == [1, 2]
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ list[Annotated[int, Ge(value=1)]] ] path[ 2 ] value_type[ <class 'tuple'> ] path_value[ 0 ]\n"
                    "  Error: value should be >= 1"
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
                    "type[ Annotated[int, Strict(type=[<class 'int'>])] ] value_type[ <class 'str'> ] value[ '1' ]\n"
                    "  Error: invalid value for <class 'int'>"
                )
            ),
        ):
            validate_value("1", StrictInt)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[int, Strict(type=[<class 'int'>])] ] value_type[ <class 'bool'> ] value[ True ]\n"
                    "  Error: invalid value for <class 'int'>"
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
                    "type[ Annotated[float, Strict(type=[<class 'float'>])] ] value_type[ <class 'int'> ] value[ 1 ]\n"
                    "  Error: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value(1, StrictFloat)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[float, Strict(type=[<class 'float'>])] ] value_type[ <class 'bool'> ] value[ True ]\n"
                    "  Error: invalid value for <class 'float'>"
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
                    "type[ Union[Annotated[int, Strict(type=[<class 'int'>])], "
                    "Annotated[float, Strict(type=[<class 'float'>])]] ] value_type[ <class 'str'> ] value[ '1' ]\n"
                    "  type[ Annotated[int, Strict(type=[<class 'int'>])] ] value_type[ <class 'str'> ]\n"
                    "    Error: invalid value for <class 'int'>\n"
                    "  type[ Annotated[float, Strict(type=[<class 'float'>])] ] value_type[ <class 'str'> ]\n"
                    "    Error: invalid value for <class 'float'>"
                )
            ),
        ):
            validate_value("1", StrictNumber)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Union[Annotated[int, Strict(type=[<class 'int'>])], "
                    "Annotated[float, Strict(type=[<class 'float'>])]] ] value_type[ <class 'bool'> ] value[ True ]\n"
                    "  type[ Annotated[int, Strict(type=[<class 'int'>])] ] value_type[ <class 'bool'> ]\n"
                    "    Error: invalid value for <class 'int'>\n"
                    "  type[ Annotated[float, Strict(type=[<class 'float'>])] ] value_type[ <class 'bool'> ]\n"
                    "    Error: invalid value for <class 'float'>"
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
                    "type[ Annotated[str, Strict(type=[<class 'str'>])] ] value_type[ <class 'int'> ] value[ 1 ]\n"
                    "  Error: invalid value for <class 'str'>"
                )
            ),
        ):
            validate_value(1, StrictStr)
        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ Annotated[str, Strict(type=[<class 'str'>])] ] value_type[ <class 'bool'> ] value[ True ]\n"
                    "  Error: invalid value for <class 'str'>"
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
                    "type[ Annotated[bool, Strict(type=[<class 'bool'>])] ] value_type[ <class 'int'> ] value[ 1 ]\n"
                    "  Error: invalid value for <class 'bool'>"
                )
            ),
        ):
            validate_value(1, StrictBool)


class TestModel:
    def test_validate_value(self):
        @dataclass
        class M:
            i: int
            s: str

        assert validate_value({"i": 1, "s": "s"}, M) == M(i=1, s="s")

    def test_model(self):
        @dataclass
        class M:
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

        m = M(
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
        assert m.i == 1
        assert m.s == "1"
        assert m.b is True
        assert m.l == [0, "1"]
        assert m.t == ("0", 1)
        assert m.li == [0, 1]
        assert m.ti == (0, 1)
        assert m.d == {}
        assert m.dd == {"0": 0, "1": 1}
        assert m.ai == 1
        assert m.al == [0, 1]

        @dataclass
        class M:
            i: int
            s: str = "s"

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ <class 'test_cwtch.M'> ] path[ 'i' ] value_type[ <class 'str'> ]\n"
                    "  type[ <class 'int'> ] value_type[ <class 'str'> ] value[ 'a' ]\n"
                    "    Error: invalid literal for int() with base 10: 'a'"
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
            b1: "B"
            b2: B

        @dataclass
        class B:
            i: int

        A.cwtch_update_forward_refs(globals(), locals())

        a = validate_value({"b1": {"i": 1}, "b2": {"i": 2}}, A)
        assert a.b1.i == 1
        assert a.b2.i == 2

    def test_extra_ignore(self):
        @dataclass
        class M:
            i: int

        m = M(i="1", s="a")
        assert m.i == 1

    def test_extra_forbid(self):
        @dataclass(extra="forbid")
        class M:
            i: int

        with pytest.raises(
            TypeError,
            match=re.escape("M.__init__() got an unexpected keyword argument 's'"),
        ):
            M(i=0, s="s")

    def test_env(self):
        @dataclass(env_prefix="TEST_")
        class M:
            i: int = field(default=0, metadata={"env_var": True})
            s: str = field(default_factory=lambda: "a", metadata={"env_var": True})

        env = {}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 0
            assert M().s == "a"

        env = {"TEST_I": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 1
            assert M().s == "a"

        env = {"TEST_S": "b"}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 0
            assert M().s == "b"

        env = {"TEST_S": "0"}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 0
            assert M().s == "0"

    def test_env_multi_prefix(self):
        @dataclass(env_prefix=["TEST1_", "TEST2_"])
        class M:
            i: int = field(default=0, metadata={"env_var": True})
            j: int = field(default_factory=lambda: 7, metadata={"env_var": True})

        env = {}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 0
            assert M().j == 7

        env = {"TEST1_I": "1"}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 1
            assert M().j == 7

        env = {"TEST2_J": "0"}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().i == 0
            assert M().j == 0

    def test_env_json(self):
        @dataclass(env_prefix="TEST_")
        class M:
            v: dict

        env = {"TEST_V": '{"k": "v"}'}
        with mock.patch.dict(os.environ, env, clear=True):
            assert M().v == {"k": "v"}

    def test_inheritance(self):
        @dataclass
        class A:
            i: int

        @dataclass
        class B(A):
            i: float
            s: str

        assert B.__bases__ == (A,)
        assert B.__mro__ == (B, A, object)

        assert B.__cwtch_fields__["i"].type == float
        assert B.__cwtch_fields__["s"].type == str

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
                    "type[ <class 'cwtch.cwtch.C[int]'> ] path[ 'x' ] value_type[ <class 'list'> ]\n"
                    "  type[ list[int] ] path[ 0 ] value_type[ <class 'list'> ] path_value[ 'a' ]\n"
                    "    Error: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value({"x": ["a"]}, C[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ <class 'cwtch.cwtch.C[int]'> ] path[ 'x' ] value_type[ <class 'list'> ]\n"
                    "  type[ list[int] ] path[ 0 ] value_type[ <class 'list'> ] path_value[ 'a' ]\n"
                    "    Error: invalid literal for int() with base 10: 'a'"
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
            # ValidationError,
            TypeError,
            match=re.escape(
                # (
                #     "type[ <class 'test_cwtch.TestModel.test_init.<locals>.M'> ] "
                #     "path[ 'i'] value_type[ <class 'cwtch.types.UnsetType'> ]\n"
                #     "  Error: M.__init__() missing required keyword-only argument: 'i'"
                # )
                "M.__init__() missing required keyword-only argument: 'i'"
            ),
        ):
            M()

        with pytest.raises(
            TypeError,
            match=re.escape("M.__init__() takes 1 positional argument but 2 were given"),
        ):
            M(0)

    def test_post_init(self):
        @dataclass
        class A:
            x: int
            s: Optional[str] = None

        @dataclass
        class B(A):
            x: float

            def __post_init__(self):
                super(B, self).__init__(x=self.x, s="s")

        b = B(x="1.1")
        assert b.x == 1
        assert b.s == "s"

    def test_default_factory(self):
        @dataclass
        class M:
            i: int = field(default_factory=lambda: 1)

        assert M().i == 1

    def test_slots(self):
        @dataclass(slots=True)
        class D:
            i: int
            s: str
            b: bool = True

        assert D.__slots__ == ("i", "s", "b", "__cwtch_fields_set__")
        assert D(i="1", s=1).__slots__ == ("i", "s", "b", "__cwtch_fields_set__")
        assert D(i="1", s=1).i == 1
        assert D(i="1", s=1).s == "1"

    def test_property(self):
        @dataclass
        class D:
            i: int = field(property=True)

        d = D(i="1")
        assert d.i == 1
        assert "i" not in d.__dict__
        with pytest.raises(AttributeError):
            d.i = 0

    def test_property_with_slots(self):
        @dataclass(slots=True)
        class D:
            i: int = field(property=True)

        d = D(i="1")
        assert d.i == 1
        assert "i" not in d.__slots__
        with pytest.raises(AttributeError):
            d.i = 0

    def test_init_alias(self):
        @dataclass
        class D:
            ref1: str = field("a", init_alias="$ref1")
            ref2: str = field(default_factory=lambda: "d", init_alias="$ref2")

        d = D()
        assert d.ref1 == "a"
        assert d.ref2 == "d"

        d = D(ref1="abc", ref2="def")
        assert d.ref1 == "abc"
        assert d.ref2 == "def"

        d = D(**{"$ref1": "abc", "$ref2": "def"})
        assert d.ref1 == "abc"
        assert d.ref2 == "def"


class TestView:
    def test_view(self):
        @dataclass
        class M:
            i: int
            s: str
            b: bool
            l: Optional[list[int]] = None

        @view
        class V1(M):
            pass

        @view(include={"i"})
        class V2(M):
            i: int = 0

        @view(exclude={"s", "b", "l"})
        class V3(M):
            i: int = 0

        @view(include={"i", "f"})
        class V4(M):
            f: float = 0.1

        assert M.__annotations__ == {"i": int, "s": str, "b": bool, "l": Optional[list[int]]}
        assert list(M.__cwtch_fields__.keys()) == ["i", "s", "b", "l"]

        assert M.V1
        assert M.V1.__cwtch_view_name__ == "V1"
        assert M.V1.__cwtch_view_base__ == M
        assert id(M.V1.__annotations__) != id(M.__annotations__)
        assert M.V1.__annotations__ == {}
        assert id(M.V1.__cwtch_fields__) != id(M.__cwtch_fields__)
        assert M.V1.__cwtch_fields__ == M.__cwtch_fields__

        assert M.V2
        assert M.V2.__cwtch_view_name__ == "V2"
        assert M.V2.__cwtch_view_base__ == M
        assert id(M.V2.__annotations__) != id(M.__annotations__)
        assert M.V2.__annotations__ == {"i": int}
        assert id(M.V2.__cwtch_fields__) != id(M.__cwtch_fields__)
        assert list(M.V2.__cwtch_fields__.keys()) == ["i"]
        assert M.V2.__cwtch_fields__["i"].name == "i"
        assert M.V2.__cwtch_fields__["i"].type == int
        assert M.V2.__cwtch_fields__["i"].default == 0
        assert M.V2.__cwtch_fields__["i"].default_factory == _MISSING
        assert M.V2.__cwtch_fields__["i"].init == True
        assert M.V2.__cwtch_fields__["i"].repr == UNSET
        assert M.V2.__cwtch_fields__["i"].metadata == {}

        assert M.V3
        assert M.V3.__cwtch_view_name__ == "V3"
        assert M.V3.__cwtch_view_base__ == M
        assert id(M.V3.__annotations__) != id(M.__annotations__)
        assert M.V3.__annotations__ == {"i": int}
        assert id(M.V3.__cwtch_fields__) != id(M.__cwtch_fields__)
        assert list(M.V3.__cwtch_fields__.keys()) == ["i"]
        assert M.V3.__cwtch_fields__["i"].name == "i"
        assert M.V3.__cwtch_fields__["i"].type == int
        assert M.V3.__cwtch_fields__["i"].default == 0
        assert M.V3.__cwtch_fields__["i"].default_factory == _MISSING
        assert M.V3.__cwtch_fields__["i"].init == True
        assert M.V3.__cwtch_fields__["i"].repr == UNSET
        assert M.V3.__cwtch_fields__["i"].metadata == {}

        assert M.V4
        assert M.V4.__cwtch_view_name__ == "V4"
        assert M.V4.__cwtch_view_base__ == M
        assert id(M.V4.__annotations__) != id(M.__annotations__)
        assert M.V4.__annotations__ == {"f": float}
        assert id(M.V4.__cwtch_fields__) != id(M.__cwtch_fields__)
        assert list(M.V4.__cwtch_fields__.keys()) == ["i", "f"]
        assert M.V4.__cwtch_fields__["i"].name == "i"
        assert M.V4.__cwtch_fields__["i"].type == int
        assert M.V4.__cwtch_fields__["i"].default == _MISSING
        assert M.V4.__cwtch_fields__["i"].default_factory == _MISSING
        assert M.V4.__cwtch_fields__["i"].init == True
        assert M.V4.__cwtch_fields__["i"].repr == UNSET
        assert M.V4.__cwtch_fields__["i"].metadata == {}

        m = M(i="1", s=1, b="n", l=["1", "2"])
        assert m.i == 1
        assert m.s == "1"
        assert m.b is False
        assert m.l == [1, 2]
        assert m.V1
        assert asdict(m) == {"i": 1, "s": "1", "b": False, "l": [1, 2]}

        v1 = m.V1()
        assert v1.__cwtch_view_name__ == "V1"
        assert v1.__cwtch_view_base__ == M
        assert v1.i == 1
        assert v1.s == "1"
        assert v1.b is False
        assert v1.l == [1, 2]
        assert asdict(v1) == {"i": 1, "s": "1", "b": False, "l": [1, 2]}

        v2 = m.V2()
        assert v2.__cwtch_view_name__ == "V2"
        assert v2.__cwtch_view_base__ == M
        assert v2.i == 1
        with pytest.raises(AttributeError):
            v2.s
        with pytest.raises(AttributeError):
            v2.b
        with pytest.raises(AttributeError):
            v2.l
        assert asdict(v2) == {"i": 1}

        v3 = m.V3()
        assert v3.__cwtch_view_name__ == "V3"
        assert v3.__cwtch_view_base__ == M
        assert v3.i == 1
        with pytest.raises(AttributeError):
            v3.s
        with pytest.raises(AttributeError):
            v3.b
        with pytest.raises(AttributeError):
            v3.l
        assert asdict(v3) == {"i": 1}

        v4 = m.V4()
        assert v4.__cwtch_view_name__ == "V4"
        assert v4.__cwtch_view_base__ == M
        assert v4.i == 1
        assert v4.f == 0.1
        with pytest.raises(AttributeError):
            v4.s
        with pytest.raises(AttributeError):
            v4.b
        with pytest.raises(AttributeError):
            v4.l
        assert asdict(v4) == {"i": 1, "f": 0.1}

    def test_extra(self):
        @dataclass
        class M:
            i: int

        @view
        class V1(M):
            pass

        @view(extra="forbid")
        class V2(M):
            pass

        v1 = M.V1(i="1", b="n")
        assert v1.i == 1

        with pytest.raises(TypeError, match=re.escape("V2.__init__() got an unexpected keyword argument 'b'")):
            v2 = M.V2(i="1", b="n")

    def test_validate(self):
        @dataclass
        class M:
            i: int
            b: bool

        @view
        class V1(M):
            b: bool = field(validate=False)

        @view(validate=False)
        class V2(M):
            b: bool = field(validate=True)

        assert M.V1(i="1", b=True).i == 1
        assert M.V1(i="1", b="t").b == "t"
        assert M.V2(i="1", b=True).i == "1"
        assert M.V2(i="1", b="t").b is True

    def test_recursive(self):
        @dataclass
        class A:
            i: Optional[int] = None
            s: Optional[str] = None

        @view("V", include=["i"])
        class AV(A):
            pass

        @dataclass
        class B:
            a: Optional[list[A]]

        @view("V", recursive=True)
        class BV(B):
            pass

        assert B.__cwtch_fields__["a"].type == Optional[list[A]]
        assert B.V.__cwtch_fields__["a"].type == Optional[list[A.V]]

    def test_inheritance(self):
        @dataclass
        class A:
            i: int

        @view("V1")
        class AV1(A):
            pass

        @view("V2")
        class AV2(A):
            pass

        @dataclass
        class B(A):
            s: str

        @view("V2")
        class BV2(B, A.V2):
            pass

        assert issubclass(B, A)
        assert B.V1
        assert B.V2
        assert not issubclass(B.V1, A.V1)
        assert issubclass(B.V2, A.V2)

    def test_slots(self):
        @dataclass(slots=True)
        class M:
            i: int

        @view
        class V1(M):
            pass


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
            {"$ref": "#/$defs/GenericModel[int, str]"},
            {
                "GenericModel[int, str]": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "array", "items": {"type": "string"}}},
                    "required": ["a", "b"],
                }
            },
        )

    def test_json_value_metadata(self):
        JsonList = Annotated[list, JsonLoads()]
        JsonDict = Annotated[dict, JsonLoads()]

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
