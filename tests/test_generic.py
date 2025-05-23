import re

from typing import Generic, TypeVar

import pytest

from cwtch import ValidationError, dataclass, field, validate_value, view


class TestGeneric:
    def test_model(self):
        T = TypeVar("T")

        @dataclass
        class M(Generic[T]):
            l: list[T]

        assert M[int]
        assert validate_value({"l": ["1"]}, M[int]).l == [1]
        assert M[int](l=["1"]).l == [1]

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ <class 'cwtch.cwtch.M[int]'> ] path[ 'l' ]\n"
                    "  type[ list[int] ] input_type[ <class 'list'> ] path[ 0 ] path_value[ 'a' ] path_value_type[ <class 'str'> ]\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            validate_value({"l": ["a"]}, M[int])

        with pytest.raises(
            ValidationError,
            match=re.escape(
                (
                    "type[ <class 'cwtch.cwtch.M[int]'> ] path[ 'l' ]\n"
                    "  type[ list[int] ] input_type[ <class 'list'> ] path[ 0 ] path_value[ 'a' ] path_value_type[ <class 'str'> ]\n"
                    "    ValueError: invalid literal for int() with base 10: 'a'"
                )
            ),
        ):
            M[int](l=["a"])

    def test_view(self):
        T = TypeVar("T")
        F = TypeVar("F")

        @dataclass
        class M(Generic[T]):
            t: T

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
            # x: str
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
