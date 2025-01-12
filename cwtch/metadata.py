import re
import types
import typing

from typing import Any, Literal, Type, TypeVar

import orjson


try:
    import emval
except ImportError:
    emval = None

from cwtch import dataclass, field
from cwtch.core import TypeMetadata, nop


__all__ = (
    "Validator",
    "Ge",
    "Gt",
    "Le",
    "Lt",
    "MinLen",
    "MaxLen",
    "Len",
    "MinItems",
    "MaxItems",
    "Match",
    "UrlConstraints",
    "JsonLoads",
    "ToLower",
    "ToUpper",
    "Strict",
)


T = TypeVar("T")


@typing.final
@dataclass(slots=True)
class Validator(TypeMetadata):
    """Validator object.

    Attributes:
        json_schema: Additional custom JSON schema.
        before: Validator to validate input data before base validation.
        after: Validator to validate value after base validation.
    """

    json_schema: dict = field(default_factory=dict, repr=False)  # type: ignore
    before: typing.Callable = field(default=nop, kw_only=True)
    after: typing.Callable = field(default=nop, kw_only=True)

    def __init_subclass__(cls, **kwds):
        raise TypeError("Validator class cannot be inherited")


@dataclass(slots=True)
class Ge(TypeMetadata):
    """
    Validator to check that the input data is greater than or equal to the specified value.

    Example:

        Annotated[int, Ge(1)]
    """

    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value}

    def after(self, value, /):
        if value < self.value:
            raise ValueError(f"value should be >= {self.value}")
        return value


@dataclass(slots=True)
class Gt(TypeMetadata):
    """
    Validator to check if input is greater than specified value.

    Example:

        Annotated[int, Gt(1)]
    """

    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value, "exclusiveMinimum": True}

    def after(self, value, /):
        if value <= self.value:
            raise ValueError(f"value should be > {self.value}")
        return value


@dataclass(slots=True)
class Le(TypeMetadata):
    """
    Validator to check that the input data is less than or equal to the specified value.

    Example:

        Annotated[int, Le(1)]
    """

    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value}

    def after(self, value, /):
        if value > self.value:
            raise ValueError(f"value should be <= {self.value}")
        return value


@dataclass(slots=True)
class Lt(TypeMetadata):
    """
    Validator to check if input is less than specified value.

    Example:

        Annotated[int, Lt(1)]
    """

    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value, "exclusiveMaximum": True}

    def after(self, value, /):
        if value >= self.value:
            raise ValueError(f"value should be < {self.value}")
        return value


@dataclass(slots=True)
class MinLen(TypeMetadata):
    """
    Validator to check that the length of the input data is greater than or equal to the specified value.

    Example:

        Annotated[str, MinLen(1)]
    """

    value: int

    def json_schema(self) -> dict:
        return {"minLength": self.value}

    def after(self, value, /):
        if len(value) < self.value:
            raise ValueError(f"value length should be >= {self.value}")
        return value


@dataclass(slots=True)
class MaxLen(TypeMetadata):
    """
    Validator to check that the length of the input data is less than or equal to the specified value.

    Example:

        Annotated[str, MaxLen(1)]
    """

    value: int

    def json_schema(self) -> dict:
        return {"maxLength": self.value}

    def after(self, value, /):
        if len(value) > self.value:
            raise ValueError(f"value length should be <= {self.value}")
        return value


@dataclass(slots=True)
class Len(TypeMetadata):
    """
    Validator to check that the input length is within the specified range.

    Example:

        Annotated[str, Len(1, 10)]
    """

    min_value: int
    max_value: int

    def json_schema(self) -> dict:
        return {"minLength": self.min_value, "maxLength": self.max_value}

    def after(self, value, /):
        if len(value) < self.min_value:
            raise ValueError(f"value length should be >= {self.min_value}")
        if len(value) > self.max_value:
            raise ValueError(f"value length should be  {self.max_value}")
        return value


@dataclass(slots=True)
class MinItems(TypeMetadata):
    """
    Validator to check that the number of elements in the input is greater than or equal to the specified value.

    Example:

        Annotated[list, MinItems(1)]
    """

    value: int

    def json_schema(self) -> dict:
        return {"minItems": self.value}

    def after(self, value, /):
        if len(value) < self.value:
            raise ValueError(f"items count should be >= {self.value}")
        return value


@dataclass(slots=True)
class MaxItems(TypeMetadata):
    """
    Validator to check that the number of elements in the input is less than or equal to the specified value.

    Example:

        Annotated[list, MaxItems(1)]
    """

    value: int

    def json_schema(self) -> dict:
        return {"maxItems": self.value}

    def after(self, value, /):
        if len(value) > self.value:
            raise ValueError(f"items count should be <= {self.value}")
        return value


@dataclass(slots=True)
class Match(TypeMetadata):
    """
    Validator to check that an input value matches a regular expression.

    Example:

        Annotated[str, Match(r".*")]
    """

    pattern: re.Pattern

    def json_schema(self) -> dict:
        return {"pattern": self.pattern.pattern}

    def after(self, value: str, /):
        if not self.pattern.match(value):
            raise ValueError(f"value doesn't match pattern {self.pattern}")
        return value


@dataclass(slots=True)
class UrlConstraints(TypeMetadata):
    """
    URL constraints.

    Attributes:
        schemes: List of valid schemes.
        ports: list of valid ports.


    Example:

        Annotated[Url, UrlConstraints(schemes=["http", "https"])]
    """

    schemes: list[str] | None = field(default=None, kw_only=True)
    ports: list[int] | None = field(default=None, kw_only=True)

    def after(self, value, /):
        if self.schemes is not None and value.scheme not in self.schemes:
            raise ValueError(f"URL scheme should be one of {self.schemes}")
        if self.ports is not None and value.port is not None and value.port not in self.ports:
            raise ValueError(f"port number should be one of {self.ports}")
        return value

    def __hash__(self):
        return hash(f"{sorted(self.schemes or [])}{sorted(self.ports or [])}")


@dataclass(slots=True, repr=False)
class JsonLoads(TypeMetadata):
    """
    Validator to try load value from json.

    Example:

        Annotated[list[int], JsonLoads()]
    """

    def before(self, value, /):
        try:
            return orjson.loads(value)
        except orjson.JSONDecodeError:
            return value


@dataclass(slots=True)
class ToLower(TypeMetadata):
    """
    Convert input to lower case.

    Attributes:
        mode: Validation mode, before or after base validation. Default: after.

    Example:

        Annotated[str, ToLower()]
    """

    mode: Literal["before", "after"] = "after"

    def before(self, value, /):
        if self.mode == "before":
            return value.lower()
        return value

    def after(self, value, /):
        if self.mode == "after":
            return value.lower()
        return value


@dataclass(slots=True)
class ToUpper(TypeMetadata):
    """
    Convert input to upper case.

    Attributes:
        mode: Validation mode, before or after base validation. Default: after.

    Example:

        Annotated[str, ToUpper()]
    """

    mode: Literal["before", "after"] = "after"

    def before(self, value, /):
        if self.mode == "before":
            return value.upper()
        return value

    def after(self, value, /):
        if self.mode == "after":
            return value.upper()
        return value


@dataclass(slots=True)
class Strict(TypeMetadata):
    """
    Validator to strict input type.

    Example:

        Annotated[int, Strict(int)]
    """

    type: Type

    def __post_init__(self):
        def fn(tp):
            tps = []
            if __args__ := getattr(tp, "__args__", None):
                if tp.__class__ not in [types.UnionType, typing._UnionGenericAlias]:  # type: ignore
                    raise ValueError(f"{self.type} is unsupported by {self.__class__}")
                for arg in __args__:
                    tps.extend(fn(arg))
            else:
                tps.append(tp)
            return tps

        object.__setattr__(self, "type", fn(self.type))

    def __hash__(self):
        return hash(f"{self.type}")

    def before(self, value, /):
        for tp in typing.cast(list, self.type):
            if isinstance(value, tp) and type(value) == tp:  # noqa: E721
                return value
        raise ValueError(f"invalid value for {' | '.join(map(str, typing.cast(list, self.type)))}")


if emval:

    @dataclass(slots=True)
    class EmailValidator(TypeMetadata):
        """Email address validator."""

        validator: emval.EmailValidator = field(
            default_factory=lambda: emval.EmailValidator(
                allow_smtputf8=True,
                allow_empty_local=True,
                allow_quoted_local=True,
                allow_domain_literal=True,
                deliverable_address=False,
            )
        )

        def json_schema(self) -> dict:
            return {"format": "email"}

        def after(self, value, /):
            return self.validator.validate_email(value)
