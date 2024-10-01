import dataclasses
import time

import cwtch
import pydantic


def test_perf():
    RANGE = 20

    @cwtch.dataclass
    class CSUB:
        i: int
        f: float

    @cwtch.dataclass
    class C:
        i: int
        f: float
        s: str
        b: bool
        l: list
        t: tuple
        li1: list[int]
        li2: list[int]
        lf1: list[float]
        lf2: list[float]
        ls1: list[str]
        ti: tuple[int, ...]
        d: dict
        dd: dict[str, int]
        subl: list[CSUB]
        subt: tuple[CSUB, ...]

    @dataclasses.dataclass
    class DSUB:
        i: int
        f: float

    @dataclasses.dataclass
    class D:
        i: int
        f: float
        s: str
        b: bool
        l: list
        t: tuple
        li1: list[int]
        li2: list[int]
        lf1: list[float]
        lf2: list[float]
        ls1: list[str]
        ti: tuple[int, ...]
        d: dict
        dd: dict[str, int]
        subl: list[DSUB]
        subt: tuple[DSUB, ...]

    class PSUB(pydantic.BaseModel):
        i: int
        f: float

    class P(pydantic.BaseModel):
        i: int
        f: float
        s: str
        b: bool
        l: list
        t: tuple
        li1: list[int]
        li2: list[int]
        lf1: list[float]
        lf2: list[float]
        ls1: list[str]
        ti: tuple[int, ...]
        d: dict
        dd: dict[str, int]
        subl: list[PSUB]
        subt: tuple[PSUB, ...]

    data = {
        "i": 0,
        "f": 1.1,
        "s": "s",
        "b": True,
        "l": list(range(RANGE)),
        "t": tuple(tuple(range(RANGE))),
        "li1": list(range(RANGE)),
        "li2": list(map(str, range(RANGE))),
        "lf1": list(map(float, range(RANGE))),
        "lf2": list(map(str, map(float, range(RANGE)))),
        "ls1": list(map(str, range(RANGE))),
        "ti": tuple(range(RANGE)),
        "d": {},
        "dd": dict(zip(map(str, range(RANGE)), range(RANGE))),
        "subl": [{"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}],
        "subt": ({"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}),
    }

    # cwtch

    model = C(**data)

    asdict = cwtch.asdict

    t0 = time.monotonic()

    assert (asdict(model, exclude=["f", "li1", "d"])) == {
        "i": 0,
        "s": "s",
        "b": True,
        "l": [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
        ],
        "t": (
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
        ),
        "li2": [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
        ],
        "lf1": [
            0.0,
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
            9.0,
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
            16.0,
            17.0,
            18.0,
            19.0,
        ],
        "lf2": [
            0.0,
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
            9.0,
            10.0,
            11.0,
            12.0,
            13.0,
            14.0,
            15.0,
            16.0,
            17.0,
            18.0,
            19.0,
        ],
        "ls1": [
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
        ],
        "ti": (
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
        ),
        "dd": {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "7": 7,
            "8": 8,
            "9": 9,
            "10": 10,
            "11": 11,
            "12": 12,
            "13": 13,
            "14": 14,
            "15": 15,
            "16": 16,
            "17": 17,
            "18": 18,
            "19": 19,
        },
        "subl": [{"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}],
        "subt": ({"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}, {"i": 0, "f": 3.14}),
    }

    for _ in range(5000):
        asdict(model, exclude=["f", "li1", "d"])

    t1 = time.monotonic()

    print()
    print("cwtch:       ", t1 - t0)

    # dataclasses

    model = D(**data)

    t0 = time.monotonic()

    for _ in range(5000):
        dataclasses.asdict(model)

    t1 = time.monotonic()

    print()
    print("dataclasses: ", t1 - t0)

    # pydantic

    model = P(**data)

    t0 = time.monotonic()

    for _ in range(5000):
        model.model_dump(exclude={"f", "li1", "d"})

    t1 = time.monotonic()

    print()
    print("pydantic:    ", t1 - t0)


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
