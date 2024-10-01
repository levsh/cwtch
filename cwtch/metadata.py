import dataclasses
import json
import re
import types
import typing

from typing import Any, Type, TypeVar


T = TypeVar("T")


class TypeMetadata:
    """Base class for type metadata."""

    def json_schema(self) -> dict:
        return {}

    def before(self, value, /):
        return value

    def after(self, value, /):
        return value


@typing.final
@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class Validator(TypeMetadata):
    json_schema: dict = dataclasses.field(default_factory=lambda: dict)  # type: ignore
    before: typing.Callable = lambda v: v
    after: typing.Callable = lambda v: v

    def __init_subclass__(cls, **kwds):
        raise Exception("Validator class cannot be inherited")


@dataclasses.dataclass(frozen=True, slots=True)
class Ge(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value}

    def after(self, value):
        if value < self.value:
            raise ValueError(f"value should be >= {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class Gt(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value, "exclusiveMinimum": True}

    def after(self, value):
        if value <= self.value:
            raise ValueError(f"value should be > {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class Le(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value}

    def after(self, value):
        if value > self.value:
            raise ValueError(f"value should be <= {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class Lt(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value, "exclusiveMaximum": True}

    def after(self, value):
        if value >= self.value:
            raise ValueError(f"value should be < {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class MinLen(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"minLength": self.value}

    def after(self, value):
        if len(value) < self.value:
            raise ValueError(f"value length should be >= {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class MaxLen(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"maxLength": self.value}

    def after(self, value):
        if len(value) > self.value:
            raise ValueError(f"value length should be <= {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class MinItems(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"minItems": self.value}

    def after(self, value):
        if len(value) < self.value:
            raise ValueError(f"items count should be >= {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class MaxItems(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"maxItems": self.value}

    def after(self, value):
        if len(value) > self.value:
            raise ValueError(f"items count should be <= {self.value}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class Match(TypeMetadata):
    pattern: re.Pattern

    def json_schema(self) -> dict:
        return {"pattern": self.pattern.pattern}

    def after(self, value: str):
        if not self.pattern.match(value):
            raise ValueError(f"value doesn't match pattern {self.pattern}")
        return value


@dataclasses.dataclass(frozen=True, slots=True)
class UrlConstraints(TypeMetadata):
    schemes: list[str] | None = dataclasses.field(default=None)
    ports: list[int] | None = dataclasses.field(default=None)

    def after(self, value, /):
        if self.schemes is not None and value.scheme not in self.schemes:
            raise ValueError(f"URL scheme should be one of {self.schemes}")
        if self.ports is not None and value.port is not None and value.port not in self.ports:
            raise ValueError(f"port number should be one of {self.ports}")
        return value

    def __hash__(self):
        return hash(f"{sorted(self.schemes or [])}{sorted(self.ports or [])}")


@dataclasses.dataclass(frozen=True, slots=True)
class JsonLoads(TypeMetadata):
    def before(self, value, /):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value


@dataclasses.dataclass(frozen=True, slots=True)
class ToLower(TypeMetadata):
    def after(self, value, /):
        return value.lower()


@dataclasses.dataclass(frozen=True, slots=True)
class ToUpper(TypeMetadata):
    def after(self, value, /):
        return value.upper()


@dataclasses.dataclass(frozen=True, slots=True)
class Strict(TypeMetadata):
    type: Type

    def __post_init__(self):
        def fn(tp):
            tps = []
            if hasattr(tp, "__args__"):
                if tp.__class__ not in [types.UnionType, typing._UnionGenericAlias]:  # type: ignore
                    raise ValueError(f"{self.type} is unsupported by {self.__class__}")
                for arg in tp.__args__:
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
