import dataclasses
import re
from json import loads as json_loads
from typing import Any


class TypeMetadata:
    """Base class for type metadata."""

    def json_schema(self) -> dict:
        return {}

    def convert(self, value):
        return value

    def validate_before(self, value, /):
        pass

    def validate_after(self, value, /):
        pass


@dataclasses.dataclass(frozen=True, slots=True)
class Ge(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value}

    def validate_after(self, value):
        if value < self.value:
            raise ValueError(f"value should be >= {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class Gt(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"minimum": self.value, "exclusiveMinimum": True}

    def validate_after(self, value):
        if value <= self.value:
            raise ValueError(f"value should be > {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class Le(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value}

    def validate_after(self, value):
        if value > self.value:
            raise ValueError(f"value should be <= {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class Lt(TypeMetadata):
    value: Any

    def json_schema(self) -> dict:
        return {"maximum": self.value, "exclusiveMaximum": True}

    def validate_after(self, value):
        if value >= self.value:
            raise ValueError(f"value should be < {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class MinLen(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"minLength": self.value}

    def validate_after(self, value):
        if len(value) < self.value:
            raise ValueError(f"value length should be >= {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class MaxLen(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"maxLength": self.value}

    def validate_after(self, value):
        if len(value) > self.value:
            raise ValueError(f"value length should be <= {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class MinItems(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"minItems": self.value}

    def validate_after(self, value):
        if len(value) < self.value:
            raise ValueError(f"items count should be >= {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class MaxItems(TypeMetadata):
    value: int

    def json_schema(self) -> dict:
        return {"maxItems": self.value}

    def validate_after(self, value):
        if len(value) > self.value:
            raise ValueError(f"items count should be <= {self.value}")


@dataclasses.dataclass(frozen=True, slots=True)
class Match(TypeMetadata):
    pattern: re.Pattern

    def json_schema(self) -> dict:
        return {"pattern": self.pattern.pattern}

    def validate_after(self, value: str):
        if not self.pattern.match(value):
            raise ValueError(f"value doesn't match pattern {self.pattern}")


@dataclasses.dataclass(frozen=True, slots=True)
class UrlConstraints(TypeMetadata):
    schemes: list[str] | None = dataclasses.field(default=None)
    ports: list[int] | None = dataclasses.field(default=None)

    def validate_after(self, value, /):
        if self.schemes is not None and value.scheme not in self.schemes:
            raise ValueError(f"URL scheme should be one of {self.schemes}")
        if self.ports is not None and value.port is not None and value.port not in self.ports:
            raise ValueError(f"port number should be one of {self.ports}")

    def __hash__(self):
        return hash(f"{sorted(self.schemes or [])}{sorted(self.ports or [])}")


@dataclasses.dataclass(frozen=True, slots=True)
class JsonValue(TypeMetadata):
    def convert(self, value, /):
        return json_loads(value)
