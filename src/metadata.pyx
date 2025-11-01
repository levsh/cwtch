# cython: language_level=3
# cython: profile=False
# distutils: language=c

import re
import types
import typing

from typing import Any, Literal, NewType, Type, TypeVar

import cython
import orjson


try:
    import emval
except ImportError:
    emval = None

from cwtch import core, dataclass, field
from cwtch.core import TypeMetadata, ValidatorAfter, ValidatorBefore


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
class Validator(ValidatorBefore, ValidatorAfter):
    """Validator class.

    Attributes:
        json_schema: Additional custom JSON schema.
        before: Validator to validate input data before base validation.
        after: Validator to validate value after base validation.
    """

    json_schema: dict = field(default_factory=dict, kw_only=True, repr=False)  # type: ignore
    before: typing.Callable = field(default=core.nop, kw_only=True)
    after: typing.Callable = field(default=core.nop, kw_only=True)

    __annotations__ = {
        "json_schema": dict,
        "before": typing.Callable,
        "after": typing.Callable,
    }

    def __init_subclass__(cls, **kwds):
        raise TypeError("Validator class cannot be inherited")


@dataclass(slots=True)
class Ge(core._Ge):
    """
    Validator to check that the input data is greater than or equal to the specified value.

    Example:

        Annotated[int, Ge(1)]
    """

    value: Any

    __annotations__ = {"value": Any}

    def json_schema(self) -> dict:
        return {"minimum": self.value}


@dataclass(slots=True)
class Gt(core._Gt):
    """
    Validator to check if input is greater than specified value.

    Example:

        Annotated[int, Gt(1)]
    """

    value: Any

    __annotations__ = {"value": Any}

    def json_schema(self) -> dict:
        return {"minimum": self.value, "exclusiveMinimum": True}


@dataclass(slots=True)
class Le(core._Le):
    """
    Validator to check that the input data is less than or equal to the specified value.

    Example:

        Annotated[int, Le(1)]
    """

    value: Any

    __annotations__ = {"value": Any}

    def json_schema(self) -> dict:
        return {"maximum": self.value}


@dataclass(slots=True)
class Lt(core._Lt):
    """
    Validator to check if input is less than specified value.

    Example:

        Annotated[int, Lt(1)]
    """

    value: Any

    __annotations__ = {"value": Any}

    def json_schema(self) -> dict:
        return {"maximum": self.value, "exclusiveMaximum": True}


@dataclass(slots=True)
class MinLen(core._MinLen):
    """
    Validator to check that the length of the input data is greater than or equal to the specified value.

    Example:

        Annotated[str, MinLen(1)]
    """

    value: int

    __annotations__ = {"value": int}

    def json_schema(self) -> dict:
        return {"minLength": self.value}


@dataclass(slots=True)
class MaxLen(core._MaxLen):
    """
    Validator to check that the length of the input data is less than or equal to the specified value.

    Example:

        Annotated[str, MaxLen(1)]
    """

    value: int

    __annotations__ = {"value": int}

    def json_schema(self) -> dict:
        return {"maxLength": self.value}


@dataclass(slots=True)
class Len(core._Len):
    """
    Validator to check that the input length is within the specified range.

    Example:

        Annotated[str, Len(1, 10)]
    """

    min_value: int
    max_value: int

    __annotations__ = {"min_value": int, "max_value": int}

    def json_schema(self) -> dict:
        return {"minLength": self.min_value, "maxLength": self.max_value}


@dataclass(slots=True)
class MinItems(core._MinItems):
    """
    Validator to check that the number of elements in the input is greater than or equal to the specified value.

    Example:

        Annotated[list, MinItems(1)]
    """

    value: int

    __annotations__ = {"value": int}

    def json_schema(self) -> dict:
        return {"minItems": self.value}


@dataclass(slots=True)
class MaxItems(core._MaxItems):
    """
    Validator to check that the number of elements in the input is less than or equal to the specified value.

    Example:

        Annotated[list, MaxItems(1)]
    """

    value: int

    __annotations__ = {"value": int}

    def json_schema(self) -> dict:
        return {"maxItems": self.value}


@dataclass(slots=True)
class Match(ValidatorAfter):
    """
    Validator to check that an input value matches a regular expression.

    Example:

        Annotated[str, Match(r".*")]
    """

    pattern: re.Pattern

    __annotations__ = {"pattern": re.Pattern}

    def json_schema(self) -> dict:
        return {"pattern": self.pattern.pattern}

    def after(self, value: str, /):
        if self.pattern.match(value):
            return value
        raise ValueError(f"value doesn't match pattern {self.pattern}")


@dataclass(slots=True)
class ToLower(core._ToLowerA, core._ToLowerB):
    """
    Convert input to lower case.

    Attributes:
        mode: Validation mode, before or after base validation. Default: after.

    Example:

        Annotated[str, ToLower()]
    """

    mode: Literal["before", "after"] = "after"

    __annotations__ = {"mode": Literal["before", "after"]}


@dataclass(slots=True)
class ToUpper(core._ToUpperA, core._ToUpperB):
    """
    Convert input to upper case.

    Attributes:
        mode: Validation mode, before or after base validation. Default: after.

    Example:

        Annotated[str, ToUpper()]
    """

    mode: Literal["before", "after"] = "after"

    __annotations__ = {"mode": Literal["before", "after"]}


@dataclass(slots=True)
class UrlConstraints(ValidatorAfter):
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

    __annotations__ = {"schemes": list[str] | None, "ports": list[int] | None}

    def after(self, value, /):
        if self.schemes is not None and value.scheme not in self.schemes:
            raise ValueError(f"URL scheme should be one of {self.schemes}")
        if self.ports is not None and value.port is not None and value.port not in self.ports:
            raise ValueError(f"port number should be one of {self.ports}")
        return value

    def __hash__(self):
        return hash(f"{sorted(self.schemes or [])}{sorted(self.ports or [])}")


@dataclass(slots=True, repr=False)
class JsonLoads(ValidatorBefore):
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
class Strict(ValidatorBefore):
    """
    Validator to strict input type.

    Example:

        Annotated[int, Strict(int)]
    """

    type: Type | NewType

    __annotations__ = {"type": Type | NewType}

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
    class EmailValidator(ValidatorAfter):
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

        __annotations__ = {"validator": emval.EmailValidator}

        def json_schema(self) -> dict:
            return {"format": "email"}

        def after(self, value, /):
            return self.validator.validate_email(value)
