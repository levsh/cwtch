from typing import ClassVar

import cwtch

from cwtch.types import UNSET, SecretStr, Unset


class TestAsDict:
    def test_include(self):
        @cwtch.dataclass
        class M:
            i: int
            s: str

        assert cwtch.asdict(M(i=1, s="s"), include=["s"]) == {"s": "s"}

    def test_exclude(self):
        @cwtch.dataclass
        class M:
            i: int
            s: str

        assert cwtch.asdict(M(i=1, s="s"), exclude=["s"]) == {"i": 1}

    def test_exclude_unset(self):
        @cwtch.dataclass
        class M:
            i: int
            s: Unset[str] = UNSET

        assert cwtch.asdict(M(i=1)) == {"i": 1, "s": UNSET}
        assert cwtch.asdict(M(i=1), exclude_unset=True) == {"i": 1}

    def test_exclude_none(self):
        @cwtch.dataclass
        class M:
            i: int
            s: str | None = None

        assert cwtch.asdict(M(i=1)) == {"i": 1, "s": None}
        assert cwtch.asdict(M(i=1, s=None)) == {"i": 1, "s": None}
        assert cwtch.asdict(M(i=1), exclude_none=True) == {"i": 1}
        assert cwtch.asdict(M(i=1, s=None), exclude_none=True) == {"i": 1}

    def test_show_secrets(self):
        @cwtch.dataclass
        class M:
            s: SecretStr

        assert cwtch.asdict(M(s="abc"))["s"] != "abc"
        assert cwtch.asdict(M(s="abc"), context={"show_secrets": True})["s"] == "abc"

    def test_exclude_extra_allow(self):
        @cwtch.dataclass(extra="allow")
        class M:
            i: int

        assert cwtch.asdict(M(i=1, s="s")) == {"i": 1, "s": "s"}

    def test_custom_asdict(self):
        @cwtch.dataclass
        class M:
            s: str

            def __cwtch_asdict__(self, handler, kwds):
                return handler(self, kwds)

        assert cwtch.asdict(M(s="abc")) == {"s": "abc"}

    def test_complex(self):
        @cwtch.dataclass
        class MM:
            i: int

        @cwtch.dataclass
        class M:
            i: int
            s: str
            lm: list[MM]
            tm: tuple[MM]
            dm: dict[str, MM]

        assert cwtch.asdict(
            M(
                i=1,
                s="s",
                lm=[MM(i=0)],
                tm=(MM(i=1),),
                dm={"k": MM(i=3)},
            )
        ) == {
            "i": 1,
            "s": "s",
            "lm": [{"i": 0}],
            "tm": ({"i": 1},),
            "dm": {"k": {"i": 3}},
        }

    def test_asdict_alias(self):
        @cwtch.dataclass
        class M:
            in_: str = cwtch.field(init_alias="in", asdict_alias="in")

        m = M(**{"in": "a"})
        assert m.in_ == "a"
        assert cwtch.asdict(m) == {"in": "a"}

    def test_classvar(self):
        @cwtch.dataclass
        class M:
            i: int = 0
            var: ClassVar[int] = 1

        assert cwtch.asdict(M()) == {"i": 0}

    def test_computed_field(self):
        @cwtch.dataclass
        class M:
            i: int

            @cwtch.computed_field
            def j(self) -> int:
                return self.i * 2

        assert cwtch.asdict(M(i=1)) == {"i": 1, "j": 2}
        assert cwtch.asdict(M(i=1), exclude_computed_fields=True) == {"i": 1}
