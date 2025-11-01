import re

from typing import Annotated, ClassVar, Generic, TypeVar

import pytest

from cwtch import ValidationError, clone, dataclass, field, validate_value, view


class TestGeneric:
    def test_model(self):
        T = TypeVar("T")

        @dataclass
        class M(Generic[T]):
            l: list[T]

        assert M[int]
        assert M[int]
        assert id(M[int]) == id(M[int])

        assert M[str]
        assert M[str]
        assert id(M[str]) == id(M[str])

        assert id(M[int]) != id(M[str])

        assert M.__annotations__["l"] == list[T]
        assert M[int].__annotations__["l"] == list[int]

        assert validate_value({"l": ["1"]}, M[int]).l == [1]
        assert M[int](l=["1"]).l == [1]

        assert str(M[int]) == "<class 'cwtch.cwtch.M[int]'>"

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: <class 'dict'> --> <class 'cwtch.cwtch.M[int]'>\n"
                    "  Input: {'l': ['a']}\n"
                    "  Path: ['l', 0]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'list'> --> list[int]\n"
                    "    Input: ['a']\n"
                    "    Path: [0]\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'int'>\n"
                    "      Input: 'a'\n"
                    "      ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value({"l": ["a"]}, M[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "\n"
                    "  Type: --> <class 'cwtch.cwtch.M[int]'>\n"
                    "  Path: ['l', 0]\n"
                    "  ValidationError:\n"
                    "    Type: <class 'list'> --> list[int]\n"
                    "    Input: ['a']\n"
                    "    Path: [0]\n"
                    "    ValidationError:\n"
                    "      Type: <class 'str'> --> <class 'int'>\n"
                    "      Input: 'a'\n"
                    "      ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            M[int](l=["a"])

    def test_view_1(self):
        T = TypeVar("T")
        F = TypeVar("F")

        @dataclass
        class M(Generic[T]):
            t: T

            V1: ClassVar
            V2: ClassVar
            V3: ClassVar
            V4: ClassVar
            V5: ClassVar

        @view(M)
        class V1(Generic[F]):
            f: F

        @view(M, exclude=["t"])
        class V2:
            f: float

        @view(M, exclude=["t"])
        class V3(Generic[F]):
            f: F

        @view(M)
        class V4:
            t: T = 0

        @view(M)
        class V5(V4):
            pass

        assert M[int]
        assert M[int]

        assert M.__dataclass_fields__["t"].type == T
        assert M(t="1").t == "1"

        assert M[int].__dataclass_fields__["t"].type == int
        assert M[int](t="1").t == 1

        assert M.V1.__dataclass_fields__["t"].type == T
        assert M.V1.__dataclass_fields__["f"].type == F

        assert M[int].V1.__dataclass_fields__["t"].type == int
        assert M[int].V1.__dataclass_fields__["f"].type == F
        assert M[int].V1(t="1", f="2.2").t == 1
        assert M[int].V1(t="1", f="2.2").f == "2.2"

        assert M[int].V1[float].__dataclass_fields__["t"].type == int
        assert M[int].V1[float].__dataclass_fields__["f"].type == float
        assert M[int].V1[float](t="1", f="2.2").t == 1
        assert M[int].V1[float](t="1", f="2.2").f == 2.2

        assert "t" not in M.V2.__dataclass_fields__
        assert M.V2.__dataclass_fields__["f"].type == float
        assert M.V2(f="2.2").f == 2.2

        assert "t" not in M[int].V2.__dataclass_fields__
        assert M[int].V2.__dataclass_fields__["f"].type == float
        assert M[int].V2(f="2.2").f == 2.2

        assert "t" not in M.V3.__dataclass_fields__
        assert M.V3.__dataclass_fields__["f"].type == F
        assert M.V3(f="2.2").f == "2.2"
        assert M[int].V3.__dataclass_fields__["f"].type == F
        assert M[int].V3(f="2.2").f == "2.2"
        assert M[int].V3[float].__dataclass_fields__["f"].type == float
        assert M[int].V3[float](f="2.2").f == 2.2

        assert M.V4.__dataclass_fields__["t"].type == T
        assert M.V4.__dataclass_fields__["t"].default == 0
        assert M.V4(t="1").t == "1"
        assert M[int].V4.__dataclass_fields__["t"].type == int
        assert M[int].V4.__dataclass_fields__["t"].default == 0
        assert M[int].V4(t="1").t == 1

        assert M.V5.__dataclass_fields__["t"].type == T
        assert M.V5.__dataclass_fields__["t"].default == 0
        assert M.V5(t="1").t == "1"
        assert M[int].V5.__dataclass_fields__["t"].type == int
        assert M[int].V5.__dataclass_fields__["t"].default == 0
        assert M[int].V5(t="1").t == 1

    def test_view_2(self):
        T = TypeVar("T")

        @dataclass
        class M(Generic[T]):
            x: T
            y: T

        @view(M, "V")
        class MV:
            y: Annotated[bool | T, True]

        assert M[int].__dataclass_fields__["x"].type == int
        assert M[int].__dataclass_fields__["y"].type == int
        assert M[int].V.__dataclass_fields__["x"].type == int
        assert M[int].V.__dataclass_fields__["y"].type == Annotated[bool | int, True]

        assert M[str].__dataclass_fields__["x"].type == str
        assert M[str].__dataclass_fields__["y"].type == str
        assert M[str].V.__dataclass_fields__["x"].type == str
        assert M[str].V.__dataclass_fields__["y"].type == Annotated[bool | str, True]

    def test_view_3(self):
        T = TypeVar("T")

        @dataclass
        class GenericM(Generic[T]):
            t: T

        @GenericM.view("V")
        class MV:
            pass

        M = GenericM[int]

        @clone(GenericM[str])
        class M2:
            pass

        @M2.view("V", base=GenericM[str].V)
        class M2V:
            pass

        assert GenericM.__dataclass_fields__["t"].type == T
        assert GenericM.V.__dataclass_fields__["t"].type == T
        assert GenericM[int].__dataclass_fields__["t"].type == int
        assert GenericM[int].__dataclass_fields__["t"].type == int
        assert GenericM[int].V.__dataclass_fields__["t"].type == int
        assert GenericM[int].V.__dataclass_fields__["t"].type == int
        assert M2.__dataclass_fields__["t"].type == str
        assert M2.V.__dataclass_fields__["t"].type == str

    def test_view_generic(self):
        T = TypeVar("T")
        F = TypeVar("F")

        @dataclass
        class M(Generic[T]):
            x: T

        @view(M, "V")
        class MV(Generic[F]):
            y: F

        assert M[int].__dataclass_fields__["x"].type == int
        assert M[int].V.__dataclass_fields__["x"].type == int
        assert M[int].V.__dataclass_fields__["y"].type == F
        M[int].V[str]
        M[int].V[str]
        assert M[int].V[str].__dataclass_fields__["y"].type == str

    def test_inheritance(self):
        T = TypeVar("T")

        @dataclass
        class A(Generic[T]):
            x: T

        @view(A, "V")
        class AV:
            x: int

        @dataclass
        class B(A[str]):
            pass

        @view(B, "V")
        class BV:
            x: bool

        assert A.__dataclass_fields__["x"].type == T
        assert A.V.__dataclass_fields__["x"].type == int
        assert B.__dataclass_fields__["x"].type == str
        assert B.V.__dataclass_fields__["x"].type == bool

    def test_default_factory(self):
        T = TypeVar("T")

        @dataclass
        class M(Generic[T]):
            f: T = field(default_factory=T)

        @view(M, "V")
        class MV:
            pass

        assert M[int]().f == 0
        assert M[int].V().f == 0
