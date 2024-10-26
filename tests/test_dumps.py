from cwtch import dataclass, dumps
from cwtch.types import SecretStr, SecretUrl, Url


class TestDumps:
    def test_simple(self):
        @dataclass
        class M:
            i: int
            s: str
            b: bool

        assert dumps(M(i=0, s="a", b=True)) == b'{"i":0,"s":"a","b":true}'

    def test_types(self):
        @dataclass
        class M:
            url: Url
            secret_url: SecretUrl
            secret_str: SecretStr

        assert (
            dumps(
                M(
                    url="http://example.com",
                    secret_url="http://user:pass@secret.com",
                    secret_str="secret",
                )
            )
            == b'{"url":"http://example.com","secret_url":"http://***:***@secret.com","secret_str":"***"}'
        )

        assert (
            dumps(
                M(
                    url="http://example.com",
                    secret_url="http://user:pass@secret.com",
                    secret_str="secret",
                ),
                context={"show_secrets": True},
            )
            == b'{"url":"http://example.com","secret_url":"http://user:pass@secret.com","secret_str":"secret"}'
        )
