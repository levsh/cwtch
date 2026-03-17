import re

import pytest

from cwtch import asdict, dataclass, field, view
from cwtch.core import _MISSING
from cwtch.errors import ValidationError
from cwtch.types import UNSET, Unset


class TestView:
    def test_dict(self):
        @dataclass
        class M:
            i: int
            j: int = 1
            k: int = field(default=2)
            l: int = field(default_factory=lambda: 3)

        @view(M)
        class V: ...

        with pytest.raises(AttributeError):
            V.i
        assert V.j == 1
        assert V.k == 2
        with pytest.raises(AttributeError):
            V.l

    def test_view(self):
        @dataclass
        class M:
            i: int
            s: str
            b: bool
            l: list[int] | None = None

        @view(M)
        class V1:
            pass

        @view(M, include={"i"})
        class V2:
            i: int = 0

        @view(M, exclude={"s", "b", "l"})
        class V3:
            i: int = 0

        @view(M, include={"i", "f"})
        class V4:
            f: float = 0.1

        assert M.__annotations__ == {"i": int, "s": str, "b": bool, "l": list[int] | None}
        assert list(M.__dataclass_fields__.keys()) == ["i", "s", "b", "l"]

        assert M.V1
        assert M.V1.__cwtch_view_name__ == "V1"
        assert M.V1.__cwtch_view_base__ == M
        assert id(M.V1.__annotations__) != id(M.__annotations__)
        assert M.V1.__annotations__ == {}
        assert id(M.V1.__dataclass_fields__) != id(M.__dataclass_fields__)
        assert M.V1.__dataclass_fields__ == M.__dataclass_fields__

        assert M.V2
        assert M.V2.__cwtch_view_name__ == "V2"
        assert M.V2.__cwtch_view_base__ == M
        assert id(M.V2.__annotations__) != id(M.__annotations__)
        assert M.V2.__annotations__ == {"i": int}
        assert id(M.V2.__dataclass_fields__) != id(M.__dataclass_fields__)
        assert list(M.V2.__dataclass_fields__.keys()) == ["i"]
        assert M.V2.__dataclass_fields__["i"].name == "i"
        assert M.V2.__dataclass_fields__["i"].type == int
        assert M.V2.__dataclass_fields__["i"].default == 0
        assert M.V2.__dataclass_fields__["i"].default_factory == _MISSING
        assert M.V2.__dataclass_fields__["i"].init == True
        assert M.V2.__dataclass_fields__["i"].repr == UNSET
        assert M.V2.__dataclass_fields__["i"].metadata == {}

        assert M.V3
        assert M.V3.__cwtch_view_name__ == "V3"
        assert M.V3.__cwtch_view_base__ == M
        assert id(M.V3.__annotations__) != id(M.__annotations__)
        assert M.V3.__annotations__ == {"i": int}
        assert id(M.V3.__dataclass_fields__) != id(M.__dataclass_fields__)
        assert list(M.V3.__dataclass_fields__.keys()) == ["i"]
        assert M.V3.__dataclass_fields__["i"].name == "i"
        assert M.V3.__dataclass_fields__["i"].type == int
        assert M.V3.__dataclass_fields__["i"].default == 0
        assert M.V3.__dataclass_fields__["i"].default_factory == _MISSING
        assert M.V3.__dataclass_fields__["i"].init == True
        assert M.V3.__dataclass_fields__["i"].repr == UNSET
        assert M.V3.__dataclass_fields__["i"].metadata == {}

        assert M.V4
        assert M.V4.__cwtch_view_name__ == "V4"
        assert M.V4.__cwtch_view_base__ == M
        assert id(M.V4.__annotations__) != id(M.__annotations__)
        assert M.V4.__annotations__ == {"f": float}
        assert id(M.V4.__dataclass_fields__) != id(M.__dataclass_fields__)
        assert list(M.V4.__dataclass_fields__.keys()) == ["i", "f"]
        assert M.V4.__dataclass_fields__["i"].name == "i"
        assert M.V4.__dataclass_fields__["i"].type == int
        assert M.V4.__dataclass_fields__["i"].default == _MISSING
        assert M.V4.__dataclass_fields__["i"].default_factory == _MISSING
        assert M.V4.__dataclass_fields__["i"].init == True
        assert M.V4.__dataclass_fields__["i"].repr == UNSET
        assert M.V4.__dataclass_fields__["i"].metadata == {}

        m = M(i="1", s="1", b="n", l=["1", "2"])
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
        @dataclass(extra="ignore")
        class M:
            i: int

        @view(M)
        class V1:
            pass

        @view(M, extra="forbid")
        class V2:
            pass

        v1 = M.V1(i="1", b="n")
        assert v1.i == 1

        with pytest.raises(ValidationError, match=re.escape("unexpected field")):
            v2 = M.V2(i="1", b="n")

    def test_validate(self):
        @dataclass
        class M:
            i: int
            b: bool

        @view(M)
        class V1:
            b: bool = field(validate=False)

        @view(M, validate=False)
        class V2:
            b: bool = field(validate=True)

        assert M.V1(i="1", b=True).i == 1
        assert M.V1(i="1", b="t").b == "t"
        assert M.V2(i="1", b=True).i == "1"
        assert M.V2(i="1", b="t").b is True

    def test_recursive(self):
        @dataclass
        class A:
            i: int | None = None
            s: str | None = None

        @view(A, "V", include=["i"])
        class AV:
            pass

        @dataclass
        class B:
            a: list[A] | None

        @view(B, "V", recursive=True)
        class BV:
            pass

        assert B.__dataclass_fields__["a"].type == list[A] | None
        assert B.V.__dataclass_fields__["a"].type == list[A.V] | None

    def test_inheritance(self):
        @dataclass
        class A:
            i: int

        @view(A, "V1")
        class AV1:
            pass

        @view(A, "V2")
        class AV2:
            pass

        @dataclass
        class B(A):
            s: str

        @view(B, "V2")
        class BV2(A.V2):
            pass

        assert issubclass(B, A)
        assert B.V1
        assert B.V2
        assert issubclass(B.V1, A.V1)
        assert issubclass(B.V2, A.V2)

    def test_slots(self):
        @dataclass(slots=True)
        class M:
            i: int

        @view(M)
        class V1:
            pass

        @view(M)
        class V2:
            i: Unset[int] = UNSET

    def test_view_from_view(self):
        @dataclass
        class M:
            i: int
            s: str

        @view(M, exclude=["s"])
        class V1:
            i: int = 1

        @view(V1)
        class V2:
            pass

        assert "i" in V2.__dataclass_fields__
        assert V2.__dataclass_fields__["i"].default == 1
        assert "s" not in V2.__dataclass_fields__

    def test_rebuild(self):
        @dataclass
        class M:
            a: int
            b: int = 1
            c: Unset[int] = UNSET

        assert M.__dataclass_fields__["a"].default is _MISSING
        assert M.__dataclass_fields__["b"].default == 1
        assert M.__dataclass_fields__["c"].default is UNSET

        @view(M, exclude=["a"])
        class V:
            b: Unset[int] = UNSET

        assert V.__dataclass_fields__["b"].default == UNSET
        assert V.__dataclass_fields__["c"].default is UNSET

        M.cwtch_rebuild()
        M.cwtch_rebuild()
        assert M.__dataclass_fields__["a"].default is _MISSING
        assert M.__dataclass_fields__["b"].default == 1
        assert M.__dataclass_fields__["c"].default is UNSET

        assert V.__dataclass_fields__["b"].default == UNSET
        assert V.__dataclass_fields__["c"].default is UNSET

        M.cwtch_rebuild()
        M.cwtch_rebuild()
        assert V.__dataclass_fields__["b"].default == UNSET
        assert V.__dataclass_fields__["c"].default is UNSET
