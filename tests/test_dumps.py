import datetime

from typing import ClassVar
from uuid import UUID

from cwtch import asdict, dataclass, dumps_json, field
from cwtch.types import SecretStr, SecretUrl, Url


class TestDumps:
    def test_simple(self):
        @dataclass
        class M:
            i: int
            s: str
            b: bool

        assert dumps_json(M(i=0, s="a", b=True)) == b'{"i":0,"s":"a","b":true}'

    def test_types(self):
        @dataclass
        class M:
            url: Url
            secret_url: SecretUrl
            secret_str: SecretStr

        assert (
            dumps_json(
                M(
                    url="http://example.com",
                    secret_url="http://user:pass@secret.com",
                    secret_str="secret",
                )
            )
            == b'{"url":"http://example.com","secret_url":"http://***:***@secret.com","secret_str":"***"}'
        )

        assert (
            dumps_json(
                M(
                    url="http://example.com",
                    secret_url="http://user:pass@secret.com",
                    secret_str="secret",
                ),
                context={"show_secrets": True},
            )
            == b'{"url":"http://example.com","secret_url":"http://user:pass@secret.com","secret_str":"secret"}'
        )

    def test_custom_types(self):
        class CustomUUID(UUID): ...

        class CustomDate(datetime.date): ...

        class CustomDateTime(datetime.datetime): ...

        class CustomTime(datetime.time): ...

        @dataclass
        class M:
            id: CustomUUID
            date: CustomDate
            datetime: CustomDateTime
            time: CustomTime

        m = M(
            "7f799175-bdcf-4d61-95b8-238746c0017f",
            CustomDate(1970, 1, 1),
            CustomDateTime(1970, 1, 1, 0, 0, 0),
            CustomTime(0, 0),
        )

        assert (
            dumps_json(m)
            == b'{"id":"7f799175-bdcf-4d61-95b8-238746c0017f","date":"1970-01-01","datetime":"1970-01-01T00:00:00","time":"00:00:00"}'
        )

    def test_asdict_alias(self):
        @dataclass
        class M:
            in_: str = field(init_alias="in", asdict_alias="in")

        assert dumps_json(M(**{"in": "a"})) == b'{"in_":"a"}'
        assert dumps_json(asdict(M(**{"in": "a"}))) == b'{"in":"a"}'

    def test_cwtch_asjson(self):
        class CustomUUID(UUID):
            def __cwtch_asjson__(self, context=None):
                return "uuid"

        class CustomDate(datetime.date):
            def __cwtch_asjson__(self, context=None):
                return "date"

        class CustomDateTime(datetime.datetime):
            def __cwtch_asjson__(self, context=None):
                return "datetime"

        class CustomTime(datetime.time):
            def __cwtch_asjson__(self, context=None):
                return "time"

        @dataclass
        class M:
            id: CustomUUID
            date: CustomDate
            datetime: CustomDateTime
            time: CustomTime

        m = M(
            "7f799175-bdcf-4d61-95b8-238746c0017f",
            CustomDate(1970, 1, 1),
            CustomDateTime(1970, 1, 1, 0, 0, 0),
            CustomTime(0, 0),
        )

        assert dumps_json(m) == b'{"id":"uuid","date":"date","datetime":"datetime","time":"time"}'

    def test_classvar(self):
        @dataclass
        class M:
            i: int = 0
            var: ClassVar[int] = 1

        assert dumps_json(M()) == b'{"i":0}'
