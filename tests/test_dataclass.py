import os
import re

from typing import Annotated, ClassVar, ForwardRef, TypeVar
from unittest import mock

import pytest

from cwtch import asdict, dataclass, field, validate_value
from cwtch.core import _MISSING, UNSET
from cwtch.cwtch import computed_field
from cwtch.errors import ValidationError
from cwtch.metadata import Ge, MinLen


T = TypeVar("T")
F = TypeVar("F")


class TestDataClass:
    def test_dataclass_empty(self):
        @dataclass
        class M:
            pass

        assert M.__dataclass_fields__ == {}
        assert M.__cwtch_model__ is True
        assert M.__cwtch_params__ == {
            "slots": False,
            "kw_only": False,
            "env_prefix": UNSET,
            "env_source": UNSET,
            "validate": True,
            "add_disable_validation_to_init": False,
            "extra": "forbid",
            "repr": True,
            "eq": True,
            "recursive": True,
        }
        assert M.__cwtch_views__ == set()

    def test_dataclass(self):
        @dataclass
        class M:
            i: int
            s: str = "s"
            b: bool = field(default=True)
            f: float = field(default_factory=lambda: 3.3)

        assert list(M.__dataclass_fields__.keys()) == ["i", "s", "b", "f"]

        assert M.__dataclass_fields__["i"].name == "i"
        assert M.__dataclass_fields__["i"].type == int
        assert M.__dataclass_fields__["i"].default == _MISSING
        assert M.__dataclass_fields__["i"].default_factory == _MISSING
        assert M.__dataclass_fields__["i"].init is True
        assert M.__dataclass_fields__["i"].init_alias == UNSET
        assert M.__dataclass_fields__["i"].asdict_alias == UNSET
        assert M.__dataclass_fields__["i"].repr == UNSET
        assert M.__dataclass_fields__["i"].compare == UNSET
        assert M.__dataclass_fields__["i"].property == UNSET
        assert M.__dataclass_fields__["i"].validate == UNSET
        assert M.__dataclass_fields__["i"].metadata == {}
        assert M.__dataclass_fields__["i"].kw_only == UNSET
        assert M.__dataclass_fields__["i"].computed_field is False

        assert M.__dataclass_fields__["s"].name == "s"
        assert M.__dataclass_fields__["s"].type == str
        assert M.__dataclass_fields__["s"].default == "s"
        assert M.__dataclass_fields__["s"].default_factory == _MISSING
        assert M.__dataclass_fields__["s"].init is True
        assert M.__dataclass_fields__["s"].init_alias == UNSET
        assert M.__dataclass_fields__["s"].asdict_alias == UNSET
        assert M.__dataclass_fields__["s"].repr == UNSET
        assert M.__dataclass_fields__["s"].compare == UNSET
        assert M.__dataclass_fields__["s"].property == UNSET
        assert M.__dataclass_fields__["s"].validate == UNSET
        assert M.__dataclass_fields__["s"].metadata == {}
        assert M.__dataclass_fields__["s"].kw_only == UNSET
        assert M.__dataclass_fields__["s"].computed_field is False

        assert M.__dataclass_fields__["b"].name == "b"
        assert M.__dataclass_fields__["b"].type == bool
        assert M.__dataclass_fields__["b"].default is True
        assert M.__dataclass_fields__["b"].default_factory == _MISSING
        assert M.__dataclass_fields__["b"].init is True
        assert M.__dataclass_fields__["b"].init_alias == UNSET
        assert M.__dataclass_fields__["b"].asdict_alias == UNSET
        assert M.__dataclass_fields__["b"].repr == UNSET
        assert M.__dataclass_fields__["b"].compare == UNSET
        assert M.__dataclass_fields__["b"].property == UNSET
        assert M.__dataclass_fields__["b"].validate == UNSET
        assert M.__dataclass_fields__["b"].metadata == {}
        assert M.__dataclass_fields__["b"].kw_only == UNSET
        assert M.__dataclass_fields__["b"].computed_field is False

        assert M.__dataclass_fields__["f"].name == "f"
        assert M.__dataclass_fields__["f"].type == float
        assert M.__dataclass_fields__["f"].default == _MISSING
        assert M.__dataclass_fields__["f"].default_factory
        assert M.__dataclass_fields__["f"].init is True
        assert M.__dataclass_fields__["f"].init_alias == UNSET
        assert M.__dataclass_fields__["i"].asdict_alias == UNSET
        assert M.__dataclass_fields__["f"].repr == UNSET
        assert M.__dataclass_fields__["f"].compare == UNSET
        assert M.__dataclass_fields__["f"].property == UNSET
        assert M.__dataclass_fields__["f"].validate == UNSET
        assert M.__dataclass_fields__["f"].metadata == {}
        assert M.__dataclass_fields__["f"].kw_only == UNSET
        assert M.__dataclass_fields__["f"].computed_field is False

        assert M.__cwtch_model__ is True
        assert M.__cwtch_params__ == {
            "slots": False,
            "kw_only": False,
            "env_prefix": UNSET,
            "env_source": UNSET,
            "validate": True,
            "add_disable_validation_to_init": False,
            "extra": "forbid",
            "repr": True,
            "eq": True,
            "recursive": True,
        }
        assert M.__cwtch_views__ == set()

        with pytest.raises(AttributeError):
            M.i
        assert M.s == "s"
        assert M.b is True
        with pytest.raises(AttributeError):
            M.f

    def test_dataclass_custom(self):
        env_source = lambda: {}

        @dataclass(
            slots=True,
            kw_only=True,
            env_prefix=["ENV_"],
            env_source=env_source,
            validate=False,
            add_disable_validation_to_init=True,
            extra="ignore",
            repr=False,
            eq=False,
            recursive=False,
        )
        class M:
            pass

        assert M.__cwtch_params__ == {
            "slots": True,
            "kw_only": True,
            "env_prefix": ["ENV_"],
            "env_source": env_source,
            "validate": False,
            "add_disable_validation_to_init": True,
            "extra": "ignore",
            "repr": False,
            "eq": False,
            "recursive": False,
        }

    def test_validation(self):
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
            s="1",
            b="y",
            l=(0, "1"),
            t=["0", 1],
            li=(0, "1"),
            ti=["0", 1],
            d={},
            dd={"0": 0, "1": "1"},
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

    def test_validation_negative(self):
        @dataclass
        class M:
            i: int
            s: str = "s"

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'test_dataclass.M'>\n"
                    "  Path: ['i']\n"
                    "  ValidationError:\n"
                    "    Type: <class 'str'> --> <class 'int'>\n"
                    "    Input: 'a'\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            M(i="a")

    def test_validate_value(self):
        @dataclass
        class M:
            i: int
            s: str

        assert validate_value({"i": 1, "s": "s"}, M) == M(i=1, s="s")
        with pytest.raises(ValidationError):
            validate_value({"i": "a", "s": 1}, M)

    def test_validate_value_list(self):
        @dataclass
        class M:
            i: int

        assert validate_value(({"i": 0}, {"i": 1}), list[M]) == [M(i=0), M(i=1)]

    def test_validate_value_tuple(self):
        @dataclass
        class M:
            i: int

        assert validate_value([{"i": 0}, {"i": 1}], tuple[M, M]) == (M(i=0), M(i=1))

    def test_validate_value_set(self):
        @dataclass
        class M:
            i: int

            def __hash__(self):
                return hash(self.i)

        assert validate_value([{"i": 0}, {"i": 1}], set[M]) == {M(i=0), M(i=1)}

    def test_validate_value_mapping(self):
        @dataclass
        class M:
            i: int

        assert validate_value({"m": {"i": 0}}, dict[str, M]) == {"m": M(i=0)}

    def test_forward_ref(self):
        @dataclass
        class A:
            b1: "B"
            b2: ForwardRef("B")

        @dataclass
        class B:
            i: int

        A.cwtch_update_forward_refs()

        a = validate_value({"b1": {"i": 1}, "b2": {"i": 2}}, A)
        assert a.b1.i == 1
        assert a.b2.i == 2

    def test_extra_ignore(self):
        @dataclass(extra="ignore")
        class M:
            i: int

        m = M(i="1", s="a")
        assert m.i == 1

    def test_extra_forbid(self):
        @dataclass(extra="forbid")
        class M:
            i: int

        with pytest.raises(
            ValidationError,
            match=re.escape("unexpected field"),
        ):
            M(i=0, s="s")

    def test_extra_allow(self):
        @dataclass(extra="allow")
        class M:
            i: int

        m = M(i="1", s="a")
        assert m.i == 1
        assert m.s == "a"
        assert m.__cwtch_extra_fields__ == ("s",)
        assert m.__cwtch_fields_set__ == ("i", "s")

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

    def test_env_json_value(self):
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

        assert tuple(A.__dataclass_fields__.keys()) == ("i",)
        assert tuple(B.__dataclass_fields__.keys()) == ("i", "s")
        assert B.__dataclass_fields__["i"].type == float
        assert B.__dataclass_fields__["s"].type == str

    def test_init(self):
        @dataclass
        class M:
            i: int

        M(0)
        M(i=0)

        with pytest.raises(ValidationError, match=re.escape("field required")):
            M()

    def test_post_init(self):
        @dataclass
        class A:
            x: int
            s: str | None = None

            def __post_init__(self):
                pass

        @dataclass
        class B(A):
            x: float

            def __post_init__(self):
                super(B, self).__init__(x=self.x, s="s")

        b = B(x="1.1")
        assert b.x == 1
        assert b.s == "s"

    def test_post_validate(self):
        @dataclass
        class A:
            x: int
            s: str | None = None

            def __post_validate__(self):
                if self.x == 0:
                    raise ValueError

        @dataclass
        class B(A):
            pass

        B(x=1)
        with pytest.raises(ValidationError):
            B(x=0)

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

        assert D.__slots__ == ("i", "s", "b", "__cwtch_fields_set__", "__cwtch_extra_fields__")
        assert D(i="1", s="1").__slots__ == ("i", "s", "b", "__cwtch_fields_set__", "__cwtch_extra_fields__")
        assert D(i="1", s="1").i == 1
        assert D(i="1", s="1").s == "1"

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

    def test_eq(self):
        @dataclass
        class M:
            i: int
            s: str

        assert M(i=0, s="a") == M(i=0, s="a")
        assert M(i=0, s="a") != M(i=1, s="a")
        assert M(i=0, s="a") != M(i=0, s="b")

        @dataclass
        class M:
            i: int
            s: str = field(compare=False)

        assert M(i=0, s="a") == M(i=0, s="a")
        assert M(i=0, s="a") == M(i=0, s="b")
        assert M(i=0, s="a") != M(i=1, s="a")

        @dataclass
        class A:
            i: int
            s: str

        @dataclass
        class B:
            i: int
            s: str

        assert A(i=0, s="a") != B(i=0, s="a")

    def test_kw_only(self):
        @dataclass
        class M:
            i: int = field()
            j: int = field(kw_only=False)
            s: str = field(kw_only=True)

        m = M(0, 1, s="a")
        assert m.i == 0
        assert m.j == 1
        assert m.s == "a"

        m = M(s="a", j=1, i=0)
        assert m.i == 0
        assert m.j == 1
        assert m.s == "a"

        with pytest.raises(
            TypeError,
            match=re.escape("M.__init__() takes from 1 to 3 positional arguments but 4 were given"),
        ):
            m = M(0, 1, "a")

    def test_rebuild(self):
        @dataclass
        class M:
            i: int = 1
            l: list = field(default_factory=list, property=True, kw_only=False)

        M.cwtch_rebuild()

        assert M.__dataclass_fields__["i"].default == 1
        assert M.__dataclass_fields__["l"].default_factory == list
        assert M.__dataclass_fields__["l"].property is True
        assert M.__dataclass_fields__["l"].kw_only is False

    def test_add_disable_validation_on_init(self):
        @dataclass(add_disable_validation_to_init=True)
        class M:
            i: int

        assert M(i="1").i == 1
        with pytest.raises(ValidationError):
            assert M(i="a")
        assert M(i="a", disable_validation=True).i == "a"

    def test_fields_init_order(self):
        @dataclass
        class A:
            a: int
            b: int | None = None

        @dataclass
        class B(A):
            c: int
            d: int | None = None
            e: int = field(3, kw_only=True)

        assert list(B.__dataclass_fields__.keys()) == ["a", "c", "b", "d", "e"]

        b = B(1, 2)
        assert b.a == 1
        assert b.b is None
        assert b.c == 2
        assert b.d is None
        assert b.e == 3

    def test_classvar(self):
        @dataclass
        class M:
            i: int = 0
            var: ClassVar[int] = 1

        assert "var" not in M.__dataclass_fields__
        assert M().i == 0
        assert M().var == 1

    def test_computed_field(self):
        @dataclass
        class M:
            i: int

            @computed_field
            def b(self) -> bool:
                return True

        assert "b" in M.__dataclass_fields__
        assert M.__dataclass_fields__["b"].type == bool
        assert M.__dataclass_fields__["b"].computed_field is True
        assert M(i=1).b is True
        assert str(M(i=1)) == "M(i=1, b=True)"
        assert asdict(M(i=1)) == {"i": 1, "b": True}

    def test_from_attributes(self):
        pass

    def test_mutable_default(self):
        """Test that mutable defaults raise ValueError like stdlib dataclass."""
        with pytest.raises(ValueError, match="mutable default"):

            @dataclass
            class M1:
                items: list = []

        with pytest.raises(ValueError, match="mutable default"):

            @dataclass
            class M2:
                data: dict = {}

        with pytest.raises(ValueError, match="mutable default"):

            @dataclass
            class M3:
                items: set = set()

        with pytest.raises(ValueError, match="mutable default"):

            @dataclass
            class M4:
                data: bytearray = bytearray()

        @dataclass
        class M5:
            items: list = field(default_factory=list)

        m1 = M5()
        m2 = M5()
        m1.items.append(1)
        assert m1.items != m2.items
