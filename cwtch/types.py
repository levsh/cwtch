import re
from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated, TypeVar
from urllib.parse import urlparse

from cwtch.metadata import Ge, MinItems, MinLen, Strict, ToLower, ToUpper

T = TypeVar("T")


class UnsetType:
    def __copy__(self, *args, **kwds):
        return self

    def __deepcopy__(self, *args, **kwds):
        return self

    def __str__(self):
        return "UNSET"

    def __repr__(self):
        return "UNSET"


UNSET = UnsetType()


Unset = T | UnsetType

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


@lru_cache
def _validate_hostname(hostname: str):
    if 1 > len(hostname) > 255:
        raise ValueError("hostname invalid")
    splitted = hostname.split(".")
    if splitted[-1] and splitted[-1][0].isdigit():
        ip_address(hostname)
    else:
        for label in splitted:
            if not re.match(r"(?!-)[a-zA-Z\d-]{1,63}(?<!-)$", label):
                raise ValueError("hostname invalid")


class _UrlMixIn:
    @property
    def scheme(self):
        return self._url.scheme

    @property
    def username(self):
        return self._url.username

    @property
    def password(self):
        return self._url.password

    @property
    def hostname(self):
        return self._url.hostname

    @property
    def port(self):
        return self._url.port

    @property
    def path(self):
        return self._url.path

    @property
    def query(self):
        return self._url.query

    @property
    def fragment(self):
        return self._url.fragment


class Url(str, _UrlMixIn):
    __slots__ = ("_url",)

    def __init__(self, value):
        try:
            self._url = urlparse(value)
        except Exception as e:
            raise ValueError(e)
        if self.hostname:
            _validate_hostname(self.hostname)

    def __repr__(self):
        return f"{self.__class__.__name__}({self})"

    @classmethod
    def __cwtch_json_schema__(cls) -> dict:
        return {"type": "string", "format": "uri"}


class SecretStr(str):
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
        return False

    def __ne__(self, other):
        return True

    @classmethod
    def __cwtch_json_schema__(cls) -> dict:
        return {"type": "string"}

    def get_secret_value(self):
        return self._value


class SecretUrl(str, _UrlMixIn):
    __slots__ = ("_value", "_url")

    def __new__(cls, value):
        try:
            url = urlparse(value)
        except Exception as e:
            raise ValueError(e)
        if url.hostname:
            _validate_hostname(url.hostname)

        obj = super().__new__(
            cls,
            url._replace(netloc=f"***:***@{url.hostname}" + (f":{url.port}" if url.port is not None else "")).geturl()
            if url.scheme
            else url.geturl(),
        )
        # obj = super().__new__(cls, f"{url.with_user('***').with_password('***')}" if url.scheme else f"{url}")
        obj._value = value
        obj._url = url
        return obj

    def __repr__(self):
        url = self._url
        value = (
            url._replace(netloc=f"***:***@{url.hostname}" + (f":{url.port}" if url.port is not None else "")).geturl()
            if url.scheme
            else url.geturl()
        )
        return f"{self.__class__.__name__}({value})"
        # return (
        #     f"{self.__class__.__name__}({self._url.with_user('***').with_password('***')})"
        #     if self._url.scheme
        #     else f"{self._url}"
        # )

    def __hash__(self):
        return hash(self._value)

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    @property
    def username(self):
        return "***" if self._url.username else None

    @property
    def password(self):
        return "***" if self._url.password else None

    @classmethod
    def __cwtch_json_schema__(cls) -> dict:
        return {"type": "string", "format": "uri"}

    def get_secret_value(self):
        return self._value
