import json
import re
import types
import typing

from typing import Any, Type, TypeVar


try:
    import emval
except ImportError:
    emval = None

from cwtch import dataclass, field
from cwtch.core import TypeMetadata


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


def nop(v):
    return v


@typing.final
@dataclass(slots=True)
class Validator(TypeMetadata):

    json_schema: dict = field(default_factory=dict, repr=False)  # type: ignore
    before: typing.Callable = field(default=nop, kw_only=True)
    after: typing.Callable = field(default=nop, kw_only=True)

    def __init_subclass__(cls, **kwds):
        raise Exception("Validator class cannot be inherited")


@dataclass(slots=True)
class Ge(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value}

    def after(self, value, /):
        if value < self.value:
            raise ValueError(f"value should be >= {self.value}")
        return value


@dataclass(slots=True)
class Gt(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value, "exclusiveMinimum": True}

    def after(self, value, /):
        if value <= self.value:
            raise ValueError(f"value should be > {self.value}")
        return value


@dataclass(slots=True)
class Le(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value}

    def after(self, value, /):
        if value > self.value:
            raise ValueError(f"value should be <= {self.value}")
        return value


@dataclass(slots=True)
class Lt(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value, "exclusiveMaximum": True}

    def after(self, value, /):
        if value >= self.value:
            raise ValueError(f"value should be < {self.value}")
        return value


@dataclass(slots=True)
class MinLen(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"minLength": self.value}

    def after(self, value, /):
        if len(value) < self.value:
            raise ValueError(f"value length should be >= {self.value}")
        return value


@dataclass(slots=True)
class MaxLen(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"maxLength": self.value}

    def after(self, value, /):
        if len(value) > self.value:
            raise ValueError(f"value length should be <= {self.value}")
        return value


@dataclass(slots=True)
class Len(TypeMetadata):
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
    value: int

    def json_schema(self) -> dict:
        return {"minItems": self.value}

    def after(self, value, /):
        if len(value) < self.value:
            raise ValueError(f"items count should be >= {self.value}")
        return value


@dataclass(slots=True)
class MaxItems(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"maxItems": self.value}

    def after(self, value, /):
        if len(value) > self.value:
            raise ValueError(f"items count should be <= {self.value}")
        return value


@dataclass(slots=True)
class Match(TypeMetadata):
    pattern: re.Pattern

    def json_schema(self) -> dict:
        return {"pattern": self.pattern.pattern}

    def after(self, value: str, /):
        if not self.pattern.match(value):
            raise ValueError(f"value doesn't match pattern {self.pattern}")
        return value


@dataclass(slots=True)
class UrlConstraints(TypeMetadata):
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
    def before(self, value, /):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value


@dataclass(slots=True, repr=False)
class ToLower(TypeMetadata):
    def after(self, value, /):
        return value.lower()


@dataclass(slots=True, repr=False)
class ToUpper(TypeMetadata):
    def after(self, value, /):
        return value.upper()


@dataclass(slots=True)
class Strict(TypeMetadata):
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
