import re
import types
import typing

from functools import lru_cache
from ipaddress import ip_address
from typing import TYPE_CHECKING, Annotated, Generic, Optional, TypeVar, Union
from urllib.parse import ParseResult, urlparse

from cwtch import metadata
from cwtch.core import UNSET, AsDictKwds, Unset, UnsetType  # noqa
from cwtch.metadata import Ge, MinItems, MinLen
from cwtch.metadata import Strict as StrictMetadata
from cwtch.metadata import ToLower, ToUpper, UrlConstraints


__all__ = (
    "AsDictKwds",
    "UnsetType",
    "Unset",
    "UNSET",
    "Number",
    "Positive",
    "NonNegative",
    "NonEmpty",
    "NonZeroLen",
    "LowerStr",
    "UpperStr",
    "Strict",
    "SecretBytes",
    "SecretStr",
    "Url",
    "HttpUrl",
    "SecretUrl",
    "SecretHttpUrl",
    "WebsocketpUrl",
    "FtpUrl",
    "FileUrl",
)


T = TypeVar("T")


Number = int | float
"""
Number type.
Example:

    i: Number = 1
    f: Number = 1.1
"""

Positive = Annotated[T, Ge(1)]
"""
Positive type(Generic).
Example:

    i: Positive[int] = 1
    n: Positive[Number] = 1.1
"""

NonNegative = Annotated[T, Ge(0)]
"""
Non negative type(Generic).
Example:

    i: NonNegative[int] = 0
    n: NonNegative[Number] = 0.0
"""

NonEmpty = Annotated[T, MinItems(1)]
"""
Non empty container.
Example:

    l: NonEmpty[list] = [1]
"""

NonZeroLen = Annotated[T, MinLen(1)]
"""
Non zero length object.
Example:

    l: NonZeroLen[str] = "a"
"""

LowerStr = Annotated[str, ToLower()]
"""
Lower case string.
Example:

    s: LowerStr = "a"
"""

UpperStr = Annotated[str, ToUpper()]
"""
Upper case string.
Example:

    s: LowerStr = "A"
"""


class Strict(Generic[T]):
    """
    Example:

        b: Strict[bool] = True
    """

    def __class_getitem__(cls, tp):
        if __args__ := getattr(tp, "__args__", None):
            if tp.__class__ == typing._AnnotatedAlias:
                return Annotated[tp, StrictMetadata(__args__[0])]
            if tp.__class__ in [types.UnionType, typing._UnionGenericAlias]:  # type: ignore
                return Union[*[Annotated[arg, StrictMetadata(arg)] for arg in __args__]]
            raise ValueError(f"{tp} is unsupported by {cls}")
        return Annotated[tp, StrictMetadata(tp)]


class SecretBytes(bytes):
    """Type to represent secret bytes."""

    __cwtch_type_config__ = {"strict_validation": False}

    if TYPE_CHECKING:
        _value: bytes

    def __new__(cls, value):
        try:
            if not isinstance(value, bytes):
                if isinstance(value, str) and not cls.__cwtch_type_config__["strict_validation"]:
                    value = value.encode()
                else:
                    raise ValueError(f"value is not a valid {bytes}")
        except Exception:
            raise ValueError(f"value is not a valid {bytes}")
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

    def __cwtch_asdict__(self, handler, kwds: AsDictKwds):
        if (kwds.context or {}).get("show_secrets"):
            return self.get_secret_value()
        return self

    def get_secret_value(self) -> bytes:
        return self._value


class SecretStr(str):
    """Type to represent secret string."""

    __slots__ = ("_value",)

    __cwtch_type_config__ = {"strict_validation": False}

    if TYPE_CHECKING:
        _value: str

    def __new__(cls, value):
        try:
            if not isinstance(value, str):
                if not cls.__cwtch_type_config__["strict_validation"]:
                    value = super().__new__(str, value)
                else:
                    raise ValueError(f"value is not a valid {str}")
        except Exception:
            raise ValueError(f"value is not a valid {str}")
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
    if TYPE_CHECKING:
        _parsed: ParseResult

    @property
    def scheme(self) -> Optional[str]:
        return self._parsed.scheme

    @property
    def username(self) -> Optional[str]:
        return self._parsed.username

    @property
    def password(self) -> Optional[str]:
        return self._parsed.password

    @property
    def hostname(self) -> Optional[str]:
        return self._parsed.hostname

    @property
    def port(self) -> Optional[int]:
        return self._parsed.port

    @property
    def path(self) -> Optional[str]:
        return self._parsed.path

    @property
    def query(self) -> Optional[str]:
        return self._parsed.query

    @property
    def fragment(self) -> Optional[str]:
        return self._parsed.fragment


class Url(str, _UrlMixIn):
    """Type to represent URL."""

    __slots__ = ("_parsed",)

    def __new__(cls, value):
        try:
            if not isinstance(value, str):
                raise ValueError(f"value is not a valid {str}")
        except Exception:
            raise ValueError(f"value is not a valid {str}")
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
            if not isinstance(value, str):
                raise ValueError(f"value is not a valid {str}")
        except Exception:
            raise ValueError(f"value is not a valid {str}")
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
    def username(self) -> Optional[str]:
        return "***" if self._parsed.username else None

    @property
    def password(self) -> Optional[str]:
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


HttpUrl = Annotated[Url, UrlConstraints(schemes=["http", "https"])]
"""
Type for HTTP URL.
"""

SecretHttpUrl = Annotated[SecretUrl, UrlConstraints(schemes=["http", "https"])]
"""
Type for secret HTTP URL.
"""

WebsocketpUrl = Annotated[Url, UrlConstraints(schemes=["ws", "wss"])]
"""
Type for websocket URL.
"""

FileUrl = Annotated[Url, UrlConstraints(schemes=["file"])]
"""
Type for file URL.
"""

FtpUrl = Annotated[Url, UrlConstraints(schemes=["ftp"])]
"""
Type for FTP URL.
"""

if getattr(metadata, "EmailValidator", None):
    Email = Annotated[str, metadata.EmailValidator()]

    __all__ += ("Email",)
