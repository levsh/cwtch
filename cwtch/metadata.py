import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from json import loads as json_loads

from msgspec import Meta


class MetaConverter:
    def convert(self, value):
        return value


class MetaValidator:
    def validate_before(self, value, /):
        pass

    def validate_after(self, value, /):
        pass


@dataclass(frozen=True, slots=True)
class MatchValidator(MetaValidator):
    pattern: re.Pattern

    def validate_after(self, value: str):
        if not self.pattern.match(value):
            raise ValueError(f"value doesn't match pattern {self.pattern}")


@dataclass(frozen=True, slots=True)
class UrlValidator(MetaValidator):
    schemes: list[str] | None = dataclass_field(default=None)
    ports: list[int] | None = dataclass_field(default=None)

    def validate_after(self, value, /):
        if self.schemes is not None and value.scheme not in self.schemes:
            raise ValueError(f"URL scheme should be one of {self.schemes}")
        if self.ports is not None and value.port is not None and value.port not in self.ports:
            raise ValueError(f"port number should be one of {self.ports}")

    def __hash__(self):
        return hash(f"{sorted(self.schemes or [])}{sorted(self.ports or [])}")


@dataclass(frozen=True, slots=True)
class JsonConverter(MetaConverter):
    def convert(self, value, /):
        return json_loads(value)
