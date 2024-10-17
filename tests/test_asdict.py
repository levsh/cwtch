import cwtch


def test_include():
    @cwtch.dataclass
    class M:
        i: int
        s: str

    assert cwtch.asdict(M(i=1, s="s"), include=["s"]) == {"s": "s"}


def test_exclude():
    @cwtch.dataclass
    class M:
        i: int
        s: str

    assert cwtch.asdict(M(i=1, s="s"), exclude=["s"]) == {"i": 1}


def test_exclude_unset():
    @cwtch.dataclass
    class M:
        i: int
        s: cwtch.types.Unset[str] = cwtch.types.UNSET

    assert cwtch.asdict(M(i=1)) == {"i": 1, "s": cwtch.types.UNSET}
    assert cwtch.asdict(M(i=1), exclude_unset=True) == {"i": 1}


def test_exclude_none():
    @cwtch.dataclass
    class M:
        i: int
        s: str | None = None

    assert cwtch.asdict(M(i=1)) == {"i": 1, "s": None}
    assert cwtch.asdict(M(i=1, s=None)) == {"i": 1, "s": None}
    assert cwtch.asdict(M(i=1), exclude_none=True) == {"i": 1}
    assert cwtch.asdict(M(i=1, s=None), exclude_none=True) == {"i": 1}


def test_show_secrets():
    @cwtch.dataclass
    class M:
        s: cwtch.types.SecretStr

    assert cwtch.asdict(M(s="abc"))["s"] != "abc"
    assert cwtch.asdict(M(s="abc"), context={"show_secrets": True})["s"] == "abc"


def test_custom_asdict():
    @cwtch.dataclass
    class M:
        s: str

        def __cwtch_asdict__(self, handler, kwds):
            return handler(self, kwds)

    assert cwtch.asdict(M(s="abc")) == {"s": "abc"}


def test_comples():

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
