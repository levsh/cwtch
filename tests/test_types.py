import json

from cwtch import asdict, dataclass
from cwtch.types import SecretStr, SecretUrl, Url


def test_Url():
    url = Url("http://user:pass@localhost:80/abc?x=y#z")
    assert isinstance(url, str)
    assert url == "http://user:pass@localhost:80/abc?x=y#z"
    assert str(url) == "http://user:pass@localhost:80/abc?x=y#z"
    assert f"{url}" == "http://user:pass@localhost:80/abc?x=y#z"
    assert repr(url) == "Url(http://user:pass@localhost:80/abc?x=y#z)"
    assert url.scheme == "http"
    assert url.username == "user"
    assert url.password == "pass"
    assert url.hostname == "localhost"
    assert url.port == 80
    assert url.path == "/abc"
    assert url.query == "x=y"
    assert url.fragment == "z"


def test_SecretStr():
    s = SecretStr("secret")
    assert isinstance(s, str)
    assert s != "secret"
    assert s != SecretStr("secret")
    assert str(s) == "***"
    assert f"{s}" == "***"
    assert repr(s) == "SecretStr(***)"
    assert s.get_secret_value() == "secret"
    assert hash(s) == hash(s.get_secret_value())


def test_SecretUrl():
    url = SecretUrl("http://user:pass@localhost:80/abc?x=y#z")
    assert isinstance(url, str)
    assert url != "http://user:pass@localhost:80/abc?x=y#z"
    assert str(url) == "http://***:***@localhost:80/abc?x=y#z"
    assert f"{url}" == "http://***:***@localhost:80/abc?x=y#z"
    assert repr(url) == "SecretUrl(http://***:***@localhost:80/abc?x=y#z)"
    assert url.scheme == "http"
    assert url.username == "***"
    assert url.password == "***"
    assert url.hostname == "localhost"
    assert url.port == 80
    assert url.path == "/abc"
    assert url.query == "x=y"
    assert url.fragment == "z"
    assert url.get_secret_value() == "http://user:pass@localhost:80/abc?x=y#z"
    assert hash(url) == hash(url.get_secret_value())


def test_model():
    @dataclass
    class M:
        url: Url
        secret: SecretStr
        secret_url: SecretUrl

    m = M(url="http://localhost", secret="secret", secret_url="http://user:pass@localhost")

    assert str(m) == (
        "test_model.<locals>.M"
        "(url=Url(http://localhost), secret=SecretStr(***), secret_url=SecretUrl(http://***:***@localhost))"
    )
    assert repr(m) == (
        "test_model.<locals>.M"
        "(url=Url(http://localhost), secret=SecretStr(***), secret_url=SecretUrl(http://***:***@localhost))"
    )
    assert (
        str(asdict(m))
        == "{'url': Url(http://localhost), 'secret': SecretStr(***), 'secret_url': SecretUrl(http://***:***@localhost)}"
    )
    assert (
        repr(asdict(m))
        == "{'url': Url(http://localhost), 'secret': SecretStr(***), 'secret_url': SecretUrl(http://***:***@localhost)}"
    )
    assert (
        json.dumps(asdict(m))
        == '{"url": "http://localhost", "secret": "***", "secret_url": "http://***:***@localhost"}'
    )
