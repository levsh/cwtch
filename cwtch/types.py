import re

from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated, TypeVar
from urllib.parse import urlparse

from cwtch import metadata
from cwtch.core import UNSET, AsDictKwds, Unset, UnsetType  # noqa
from cwtch.metadata import Ge, MinItems, MinLen, Strict, ToLower, ToUpper, UrlConstraints


__all__ = (
    "Number",
    "Positive",
    "NonNegative",
    "NonEmpty",
    "NonZeroLen",
    "LowerStr",
    "UpperStr",
    "StrictInt",
    "StrictFloat",
    "StrictNumber",
    "StrictStr",
    "StrictBool",
    "SecretBytes",
    "SecretStr",
    "Url",
    "SecretUrl",
)


T = TypeVar("T")


Number = int | float

Positive = Annotated[T, Ge(1)]
NonNegative = Annotated[T, Ge(0)]

NonEmpty = Annotated[T, MinItems(1)]
NonZeroLen = Annotated[T, MinLen(1)]

LowerStr = Annotated[str, ToLower()]
UpperStr = Annotated[str, ToUpper()]

StrictInt = Annotated[int, Strict(int)]
StrictFloat = Annotated[float, Strict(float)]
StrictNumber = StrictInt | StrictFloat
StrictStr = Annotated[str, Strict(str)]
StrictBool = Annotated[bool, Strict(bool)]


class SecretBytes(bytes):
    """Type to represent secret bytes."""

    def __new__(cls, value):
        obj = super().__new__(cls, b"***")
        obj._value = value
        return obj

    def __repr__(self):
        return f"{self.__class__.__name__}(***)"

    def __hash__(self):
        return hash(self._value)

    def __eq__(self, other):
        if not isinstance(other, SecretBytes):
            return False
        return self._value == other._value

    def __ne__(self, other):
        if not isinstance(other, SecretBytes):
            return True
        return self._value != other._value

    def __len__(self):
        return len(self._value)

    # @classmethod
    # def __cwtch_json_schema__(cls, **kwds) -> dict:
    #     return {"type": "string"}

    def __cwtch_asdict__(self, handler, kwds: AsDictKwds):
        if (kwds.context or {}).get("show_secrets"):
            return self.get_secret_value()
        return self

    def get_secret_value(self) -> bytes:
        return self._value


class SecretStr(str):
    """Type to represent secret string."""

    __slots__ = ("_value",)

    def __new__(cls, value):
        obj = super().__new__(cls, "***")
        obj._value = value
        return obj

    def __repr__(self):
        return f"{self.__class__.__name__}(***)"

    def __hash__(self):
        return hash(self._value)

    def __eq__(self, other):
        if not isinstance(other, SecretStr):
            return False
        return self._value == other._value

    def __ne__(self, other):
        if not isinstance(other, SecretStr):
            return True
        return self._value != other._value

    def __len__(self):
        return len(self._value)

    @classmethod
    def __cwtch_json_schema__(cls, **kwds) -> dict:
        return {"type": "string"}

    def __cwtch_asdict__(self, handler, kwds: AsDictKwds):
        if (kwds.context or {}).get("show_secrets"):
            return self.get_secret_value()
        return self

    def __cwtch_asjson__(self, context: dict | None = None):
        if (context or {}).get("show_secrets"):
            return self.get_secret_value()
        return f"{self}"

    def get_secret_value(self) -> str:
        return self._value


@lru_cache
def _validate_hostname(hostname: str):
    if 1 > len(hostname) > 255:
        raise ValueError("invalid hostname length")
    splitted = hostname.split(".")
    if (last := splitted[-1]) and last[0].isdigit():
        ip_address(hostname)
    else:
        for label in splitted:
            if not re.match(r"(?!-)[a-zA-Z\d-]{1,63}(?<!-)$", label):
                raise ValueError("invalid hostname")


class _UrlMixIn:
    @property
    def scheme(self) -> str | None:
        return self._parsed.scheme  # type: ignore

    @property
    def username(self) -> str | None:
        return self._parsed.username  # type: ignore

    @property
    def password(self) -> str | None:
        return self._parsed.password  # type: ignore

    @property
    def hostname(self) -> str:
        return self._parsed.hostname  # type: ignore

    @property
    def port(self) -> int | None:
        return self._parsed.port  # type: ignore

    @property
    def path(self) -> str | None:
        return self._parsed.path  # type: ignore

    @property
    def query(self) -> str | None:
        return self._parsed.query  # type: ignore

    @property
    def fragment(self) -> str | None:
        return self._parsed.fragment  # type: ignore


class Url(str, _UrlMixIn):
    """Type to represent URL."""

    __slots__ = ("_parsed",)

    def __new__(cls, value):
        try:
            parsed = urlparse(value)
        except Exception as e:
            raise ValueError(e)
        if parsed.hostname:
            _validate_hostname(parsed.hostname)

        obj = super().__new__(cls, parsed.geturl())
        obj._parsed = parsed
        return obj

    def __repr__(self):
        return f"{self.__class__.__name__}({self})"

    @classmethod
    def __cwtch_json_schema__(cls, **kwds) -> dict:
        return {"type": "string", "format": "uri"}

    def __cwtch_asjson__(self, context: dict | None = None):
        return f"{self}"


class SecretUrl(str, _UrlMixIn):
    """Type to represent secret URL."""

    __slots__ = ("_parsed", "_value")

    def __new__(cls, value):
        try:
            parsed = urlparse(value)
        except Exception as e:
            raise ValueError(e)
        if parsed.hostname:
            _validate_hostname(parsed.hostname)

        obj = super().__new__(
            cls,
            (
                parsed._replace(
                    netloc=f"***:***@{parsed.hostname}" + (f":{parsed.port}" if parsed.port is not None else "")
                ).geturl()
                if parsed.scheme
                else parsed.geturl()
            ),
        )
        obj._parsed = parsed
        obj._value = parsed.geturl()
        return obj

    def __repr__(self):
        parsed = self._parsed
        value = (
            parsed._replace(
                netloc=f"***:***@{parsed.hostname}" + (f":{parsed.port}" if parsed.port is not None else "")
            ).geturl()
            if parsed.scheme
            else parsed.geturl()
        )
        return f"{self.__class__.__name__}({value})"

    def __hash__(self):
        return hash(self._value)

    def __eq__(self, other):
        if not isinstance(other, SecretUrl):
            return False
        return self._value == other._value

    def __ne__(self, other):
        if not isinstance(other, SecretUrl):
            return True
        return self._value != other._value

    def __len__(self):
        return len(self._value)

    @property
    def username(self):
        return "***" if self._parsed.username else None

    @property
    def password(self):
        return "***" if self._parsed.password else None

    @classmethod
    def __cwtch_json_schema__(cls, **kwds) -> dict:
        return {"type": "string", "format": "uri"}

    def __cwtch_asdict__(self, handler, kwds: AsDictKwds):
        if (kwds.context or {}).get("show_secrets"):
            return self.get_secret_value()
        return self

    def __cwtch_asjson__(self, context: dict | None = None):
        if (context or {}).get("show_secrets"):
            return self.get_secret_value()
        return f"{self}"

    def get_secret_value(self) -> str:
        return self._value


HttpUrl = Annotated[Url, UrlConstraints(shemes=["http", "https"])]
SecretHttpUrl = Annotated[SecretUrl, UrlConstraints(shemes=["http", "https"])]
WebsocketpUrl = Annotated[Url, UrlConstraints(shemes=["ws", "wss"])]
FileUrl = Annotated[Url, UrlConstraints(shemes=["file"])]
FtpUrl = Annotated[Url, UrlConstraints(shemes=["ftp"])]

if getattr(metadata, "EmailValidator", None):
    Email = Annotated[str, metadata.EmailValidator()]
