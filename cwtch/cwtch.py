# ruff: noqa: F401
import functools
import json
import os
import sys
import typing

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import _FIELD, _DataclassParams  # type: ignore
from inspect import _empty, signature
from itertools import chain
from types import UnionType, new_class
from typing import Any, Callable, ClassVar, Generic, Literal, Type, TypeVar, Union, cast, dataclass_transform

import rich.repr

from cwtch import config
from cwtch.config import ADD_DISABLE_VALIDATION_TO_INIT, ATTACH, EQ, EXTRA, KW_ONLY, RECURSIVE, REPR, SLOTS, VALIDATE
from cwtch.core import _DEFAULT, _MISSING, UNSET, ToView, Unset, UnsetType, _get_cache, _Missing
from cwtch.core import asdict as _asdict
from cwtch.core import asjson as _asjson
from cwtch.core import get_validator, update_metadata, validate_generic_alias, validate_value
from cwtch.errors import Error, ValidationError


__all__ = (
    "is_cwtch_model",
    "is_cwtch_view",
    "field",
    "computed_field",
    "dataclass",
    "view",
    "clone",
    "from_attributes",
    "asdict",
    "asjson",
    "resolve_types",
    "validate_call",
    "validate_args",
)


T = TypeVar("T")

Extra = Literal["forbid", "ignore", "allow"]


def _is_classvar(tp: Type) -> bool:
    """Check if a type annotation is a ClassVar.

    Args:
        tp: The type annotation to check.

    Returns:
        True if the type is a ClassVar, False otherwise.
    """
    return getattr(tp, "__origin__", tp) is ClassVar


_MUTABLE_TYPES = (list, dict, set, frozenset, bytearray, memoryview)


def _is_mutable_default(value: Any) -> bool:
    """Check if default value is mutable.

    Args:
        value: The default value to check.

    Returns:
        True if value is mutable, False otherwise.
    """
    if value is None:
        return False
    return isinstance(value, _MUTABLE_TYPES)


def is_cwtch_model(cls: Type) -> bool:
    """Check if class or instance is a cwtch model.

    Args:
        cls: The class or instance to check.

    Returns:
        True if the class is a cwtch model (not a view), False otherwise.
    """
    return bool(getattr(cls, "__cwtch_model__", None) and not getattr(cls, "__cwtch_view__", None))


def is_cwtch_view(cls: Type) -> bool:
    """Check if class or instance is a cwtch view.

    Args:
        cls: The class or instance to check.

    Returns:
        True if the class is a cwtch view, False otherwise.
    """
    return bool(getattr(cls, "__cwtch_model__", None) and getattr(cls, "__cwtch_view__", None))


@rich.repr.auto
class Field:
    """Represents a dataclass field configuration.

    Attributes:
        name: The name of the field.
        type: The type annotation of the field.
        default: The default value of the field.
        default_factory: A callable that returns a default value.
        init: Whether the field is included in __init__.
        init_alias: Alternative name for the field in __init__.
        asdict_alias: Alternative name for the field in asdict().
        repr: Whether the field is included in repr().
        compare: Whether the field is used in comparisons.
        property: Whether the field is a property.
        validate: Whether the field value is validated.
        metadata: Additional metadata for the field.
        kw_only: Whether the field is keyword-only.
        computed_field: Whether this is a computed field.
        _field_type: Internal field type marker.
    """

    __slots__ = (
        "name",
        "type",
        "default",
        "default_factory",
        "init",
        "init_alias",
        "asdict_alias",
        "repr",
        "compare",
        "property",
        "validate",
        "metadata",
        "kw_only",
        "computed_field",
        "_field_type",
    )

    def __init__(
        self,
        *,
        default=_MISSING,
        default_factory: _Missing[Callable] = _MISSING,
        init: bool = True,
        init_alias: Unset[str] = UNSET,
        asdict_alias: Unset[str] = UNSET,
        repr: Unset[Literal[False]] = UNSET,
        compare: Unset[bool] = UNSET,
        property: Unset[Literal[True]] = UNSET,
        validate: Unset[bool] = UNSET,
        metadata: Unset[dict] = UNSET,
        kw_only: Unset[bool] = UNSET,
        computed_field: Unset[bool] = UNSET,
    ):
        if default is not _MISSING and default_factory is not _MISSING:
            raise ValueError("cannot specify both default and default_factory")
        self.name: str = cast(str, None)
        self.type: Any = cast(Any, None)
        self.default: Any = default
        self.default_factory = default_factory
        self.init = init
        self.init_alias = init_alias
        self.asdict_alias = asdict_alias
        self.repr = repr
        self.compare = compare
        self.property = property
        self.validate = validate
        self.metadata = {} if metadata is UNSET else metadata
        self.kw_only = kw_only
        self.computed_field = False if computed_field is UNSET else computed_field
        self._field_type = None  # Python dataclasses.dataclass compatibility

    def __rich_repr__(self):
        yield "name", self.name
        yield "type", self.type
        yield "default", self.default  # , True
        yield "default_factory", self.default_factory  # , False
        yield "init", self.init
        yield "init_alias", self.init_alias
        yield "asdict_alias", self.asdict_alias
        yield "repr", self.repr
        yield "compare", self.compare
        yield "property", self.property
        yield "validate", self.validate
        yield "metadata", self.metadata
        yield "kw_only", self.kw_only
        yield "computed_field", self.computed_field

    def __eq__(self, other) -> bool:
        if not isinstance(other, Field):
            return False
        return (
            self.name,
            self.type,
            self.default,
            self.default_factory,
            self.init,
            self.init_alias,
            self.asdict_alias,
            self.repr,
            self.compare,
            self.property,
            self.validate,
            self.metadata,
            self.kw_only,
            self.computed_field,
            self._field_type,
        ) == (
            other.name,
            other.type,
            other.default,
            other.default_factory,
            other.init,
            other.init_alias,
            other.asdict_alias,
            other.repr,
            other.compare,
            other.property,
            other.validate,
            other.metadata,
            other.kw_only,
            other.computed_field,
            other._field_type,
        )


def field(
    default: Any = _MISSING,
    *,
    default_factory: _Missing[Callable] = _MISSING,
    init: bool = True,
    init_alias: Unset[str] = UNSET,
    asdict_alias: Unset[str] = UNSET,
    repr: Unset[Literal[False]] = UNSET,
    compare: Unset[bool] = UNSET,
    property: Unset[Literal[True]] = UNSET,
    validate: Unset[bool] = UNSET,
    metadata: Unset[dict] = UNSET,
    kw_only: Unset[bool] = UNSET,
) -> Any:
    """Return an object to identify dataclass fields.

    Args:
        default: The default value of the field.
        default_factory: A 0-argument function called to initialize a field's value.
        init: If init is true, the field will be a parameter to the class's `__init__()` function.
        init_alias: Field alias for __init__.
        asdict_alias: Field alias for asdict.
        repr: If repr is true, the field will be included in the object's repr().
        compare: If compare is true, the field will be used in comparison functions.
        property: If true field will become a property.
        validate: Validate or not.
        metadata: If specified, must be a mapping which is stored but not otherwise examined by dataclass.
        kw_only: If kw_only true, the field will become a keyword-only parameter to `__init__()`.

    Returns:
        A Field object representing the dataclass field configuration.

    Raises:
        ValueError: If both default and default_factory are specified.
    """
    return Field(
        default=default,
        default_factory=default_factory,
        init=init,
        init_alias=init_alias,
        asdict_alias=asdict_alias,
        repr=repr,
        compare=compare,
        property=property,
        validate=validate,
        metadata=metadata,
        kw_only=kw_only,
    )


@dataclass_transform(field_specifiers=(field,))
def dataclass(
    cls: Type | None = None,
    *,
    slots: Unset[bool] = UNSET,
    kw_only: Unset[bool] = UNSET,
    env_prefix: Unset[str | Sequence[str]] = UNSET,
    env_source: Unset[Callable] = UNSET,
    validate: Unset[bool] = UNSET,
    add_disable_validation_to_init: Unset[bool] = UNSET,
    extra: Unset[Extra] = UNSET,
    repr: Unset[bool] = UNSET,
    eq: Unset[bool] = UNSET,
    recursive: Unset[bool | Sequence[str]] = UNSET,
) -> Callable[[Type[T]], Type[T]]:
    """Decorator to create a cwtch model class.

    Args:
        cls: The class to decorate.
        slots: If true, `__slots__` attribute will be generated
            and new class will be returned instead of the original one.
            If `__slots__` is already defined in the class, then TypeError is raised.
        kw_only: If kw_only is true, then by default all fields are keyword-only.
        env_prefix: Prefix (or list of prefixes) for environment variables.
        env_source: Environment variables source factory. By default os.environ.
        validate: If false, validation will be disabled for the entire class.
        add_disable_validation_to_init: Add disable_validation keyword argument to `__init__()` method
            to disable validation.
        extra: Ignore or forbid extra arguments passed to init.
        repr: If true, a `__rich_repr__()` method will be generated and rich.repr.auto decorator applied to the class.
        eq: If true, an `__eq__()` method will be generated.
            This method compares the class as if it were a tuple of its fields, in order.
            Both instances in the comparison must be of the identical type.
        recursive: Fields to recursively convert to views in nested models.
            When a model field has a type that is another cwtch model, setting
            recursive to True will automatically use the corresponding view
            of that nested model instead of the model itself.
            - True: Convert all nested cwtch models to their views (uses view
              with same name as current view, or falls back to first available view)
            - False/None: Don't convert nested models to views
            - Sequence[str]: Only convert to views with these specific names
            Example: If Model B has field `a: list[A] | None` and A has view `A.V`,
            then B.V with recursive=True will have field `a: list[A.V] | None`

    Returns:
        The decorated class transformed into a cwtch model.
    """

    if slots is UNSET:
        slots = SLOTS
    if kw_only is UNSET:
        kw_only = KW_ONLY
    if validate is UNSET:
        validate = VALIDATE
    if add_disable_validation_to_init is UNSET:
        add_disable_validation_to_init = ADD_DISABLE_VALIDATION_TO_INIT
    if extra is UNSET:
        extra = EXTRA
    if repr is UNSET:
        repr = REPR
    if eq is UNSET:
        eq = EQ
    if recursive is UNSET:
        recursive = RECURSIVE

    def wrapper(
        cls,
        slots=slots,
        kw_only=kw_only,
        env_prefix=env_prefix,
        env_source=env_source,
        validate=validate,
        add_disable_validation_to_init=add_disable_validation_to_init,
        extra=extra,
        repr=repr,
        eq=eq,
        recursive=recursive,
    ):
        return _build(
            cls,
            cast(bool, slots),
            cast(bool, kw_only),
            cast(
                Unset[Sequence[str]],
                env_prefix if env_prefix is UNSET or isinstance(env_prefix, (list, tuple, set)) else [env_prefix],
            ),
            env_source,
            cast(bool, validate),
            cast(bool, add_disable_validation_to_init),
            cast(Extra, extra),
            cast(bool, repr),
            cast(bool, eq),
            cast(bool, recursive),
        )

    if cls is None:
        return wrapper

    return wrapper(cls)


@dataclass_transform(field_specifiers=(field,))
def clone(
    base_cls: Type,
    *,
    include: Unset[Sequence[str]] = UNSET,
    exclude: Unset[Sequence[str]] = UNSET,
    slots: Unset[bool] = UNSET,
    kw_only: Unset[bool] = UNSET,
    env_prefix: Unset[str | Sequence[str]] = UNSET,
    env_source: Unset[Callable] = UNSET,
    validate: Unset[bool] = UNSET,
    add_disable_validation_to_init: Unset[bool] = UNSET,
    extra: Unset[Extra] = UNSET,
    repr: Unset[bool] = UNSET,
    eq: Unset[bool] = UNSET,
) -> Callable[[Type[T]], Type[T]]:
    """Create a modified copy of a cwtch model.

    Clone creates a new model class based on an existing model or view,
    allowing customization of fields and options.

    Args:
        base_cls: The base cwtch model or view to clone.
        include: Fields to include in the clone.
        exclude: Fields to exclude from the clone.
        slots: Whether to use __slots__.
        kw_only: Whether fields should be keyword-only.
        env_prefix: Prefix for environment variables.
        env_source: Source for environment variables.
        validate: Whether to validate fields.
        add_disable_validation_to_init: Whether to add disable_validation param.
        extra: How to handle extra arguments.
        repr: Whether to generate __repr__.
        eq: Whether to generate __eq__.

    Returns:
        A decorator that creates the cloned class.
    """

    if not (is_cwtch_model(base_cls) or is_cwtch_view(base_cls)):
        raise TypeError(f"{base_cls} is not a valid cwtch model or view")

    if is_cwtch_view(base_cls):
        name = base_cls.__cwtch_view_name__
    else:
        name = UNSET

    def wrapper(
        view_cls,
        *,
        base_cls=base_cls,
        name=name,
        attach=False,
        include=include,
        exclude=exclude,
        slots=slots,
        kw_only=kw_only,
        env_prefix=env_prefix,
        env_source=env_source,
        validate=validate,
        add_disable_validation_to_init=add_disable_validation_to_init,
        extra=extra,
        repr=repr,
        eq=eq,
        recursive=False,
    ):
        if exclude and set(exclude) & view_cls.__annotations__.keys():  # type: ignore
            raise ValueError(f"unable to exclude fields {list(set(exclude) & view_cls.__annotations__.keys())}")  # type: ignore

        clone = _build_view(
            base_cls,
            view_cls,
            name,
            attach,
            include,
            exclude,
            slots,
            kw_only,
            cast(
                Unset[Sequence[str]],
                env_prefix if env_prefix is UNSET or isinstance(env_prefix, (list, tuple, str)) else [env_prefix],
            ),
            env_source,
            validate,
            add_disable_validation_to_init,
            extra,
            repr,
            eq,
            recursive,
        )

        def view(
            base_cls,
            name: Unset[str] = UNSET,
            *,
            base: Unset[Type] = UNSET,
            include: Unset[Sequence[str]] = UNSET,
            exclude: Unset[Sequence[str]] = UNSET,
            slots: Unset[bool] = UNSET,
            kw_only: Unset[bool] = UNSET,
            env_prefix: Unset[str | Sequence[str]] = UNSET,
            env_source: Unset[Callable] = UNSET,
            validate: Unset[bool] = UNSET,
            add_disable_validation_to_init: Unset[bool] = UNSET,
            extra: Unset[Extra] = UNSET,
            repr: Unset[bool] = UNSET,
            eq: Unset[bool] = UNSET,
            recursive: Unset[bool | Sequence[str]] = UNSET,
        ):
            return globals()["view"](
                base_cls,
                name=name,
                base=base,
                attach=base_cls,
                include=include,
                exclude=exclude,
                slots=slots,
                kw_only=kw_only,
                env_prefix=env_prefix,
                env_source=env_source,
                validate=validate,
                add_disable_validation_to_init=add_disable_validation_to_init,
                extra=extra,
                repr=repr,
                eq=eq,
                recursive=recursive,
            )

        clone.view = classmethod(view)

        return clone

    return wrapper


@dataclass_transform(field_specifiers=(field,))
def view(
    base_cls: Type,
    name: Unset[str] = UNSET,
    *,
    base: Unset[Type] = UNSET,
    attach: Unset[bool | Type] = UNSET,
    include: Unset[Sequence[str]] = UNSET,
    exclude: Unset[Sequence[str]] = UNSET,
    slots: Unset[bool] = UNSET,
    kw_only: Unset[bool] = UNSET,
    env_prefix: Unset[str | Sequence[str]] = UNSET,
    env_source: Unset[Callable] = UNSET,
    validate: Unset[bool] = UNSET,
    add_disable_validation_to_init: Unset[bool] = UNSET,
    extra: Unset[Extra] = UNSET,
    repr: Unset[bool] = UNSET,
    eq: Unset[bool] = UNSET,
    recursive: Unset[bool | Sequence[str]] = UNSET,
) -> Callable[[Type[T]], Type[T]]:
    """Decorator to create a cwtch view class.

    Args:
        base_cls: The base cwtch model or view class.
        name: View name.
        base: Class to use as source.
        attach: If true, view will be attached to base cls.
        include: List of fields to include in view.
        exclude: List of fields to exclude from view.
        slots: If true, `__slots__` attribute will be generated
            and new class will be returned instead of the original one.
            If `__slots__` is already defined in the class, then TypeError is raised.
            If UNSET value from base view model will be used.
        kw_only: If kw_only is true, then by default all fields are keyword-only.
        env_prefix: Prefix (or list of prefixes) for environment variables.
            If UNSET value from base view model will be used.
        env_source: Environment variables source factory.
            If UNSET value from base view model will be used.
        validate: Validate or not fields.
            If UNSET value from base view model will be used.
        add_disable_validation_to_init: Add disable_validation keyword argument to `__init__()` method
            to disable validation.
            If UNSET value from base view model will be used.
        extra: Ignore or forbid extra arguments passed to init.
            If UNSET value from base view model will be used.
        repr: If true, a `__rich_repr__()` method will be generated and rich.repr.auto decorator applied to the class.
            If UNSET value from base view model will be used.
        eq: If true, an `__eq__()` method will be generated.
            This method compares the class as if it were a tuple of its fields, in order.
            Both instances in the comparison must be of the identical type.
            If UNSET value from base view model will be used.
        recursive: Fields to recursively convert to views in nested models.
            When a view field has a type that is another cwtch model, setting
            recursive to True will automatically use the corresponding view
            of that nested model instead of the model itself.
            - True: Convert all nested cwtch models to their views (uses view
              with same name as current view, or falls back to first available view)
            - False/None: Don't convert nested models to views
            - Sequence[str]: Only convert to views with these specific names
            Example: If Model B has field `a: list[A] | None` and A has view `A.V`,
            then B.V with recursive=True will have field `a: list[A.V] | None`
            If UNSET value from base view model will be used.

    Returns:
        A decorator that creates the view class.

    Raises:
        TypeError: If base_cls is not a valid cwtch model or view.
    """

    if not (is_cwtch_model(base_cls) or is_cwtch_view(base_cls)):
        raise TypeError(f"{base_cls} is not a valid cwtch model or view")

    def wrapper(
        view_cls,
        *,
        base_cls=base or base_cls,
        name=name,
        attach=attach,
        include=include,
        exclude=exclude,
        slots=slots,
        kw_only=kw_only,
        env_prefix=env_prefix,
        env_source=env_source,
        validate=validate,
        add_disable_validation_to_init=add_disable_validation_to_init,
        extra=extra,
        repr=repr,
        eq=eq,
        recursive=recursive,
    ):
        if exclude and set(exclude) & view_cls.__annotations__.keys():  # type: ignore
            raise ValueError(f"unable to exclude fields {list(set(exclude) & view_cls.__annotations__.keys())}")  # type: ignore

        return _build_view(
            base_cls,
            view_cls,
            name,
            attach,
            include,
            exclude,
            slots,
            kw_only,
            cast(
                Unset[Sequence[str]],
                env_prefix if env_prefix is UNSET or isinstance(env_prefix, (list, tuple, str)) else [env_prefix],
            ),
            env_source,
            validate,
            add_disable_validation_to_init,
            extra,
            repr,
            eq,
            recursive,
        )

    return wrapper


class _ViewDesc:
    """Descriptor for accessing view objects.

    This descriptor is used to lazily create view objects when accessed
    as class attributes on a cwtch model.

    Args:
        view_cls: The view class to instantiate.
    """

    def __init__(self, view_cls: Type):
        self.view_cls = view_cls

    def __get__(self, obj, owner=None):
        if obj:
            return ToView(self.view_cls, obj)
        return self.view_cls


def _default_env_source() -> dict:
    """Get the default environment variables source.

    Returns:
        A dictionary of environment variables (os.environ).
    """
    return cast(dict, os.environ)


def _is_generic(cls) -> bool:
    """Check if a class is a parameterized generic type.

    Args:
        cls: The class to check.

    Returns:
        True if the class is a parameterized generic, False otherwise.
    """
    return bool(
        (origin := getattr(cls, "__origin__", None))
        and getattr(origin, "__parameters__", None)
        and getattr(cls, "__args__", None)
    )


def _get_parameters_map(cls: Type, exclude_params: set | None = None) -> dict:
    """Extract type parameter mapping from a generic class.

    Args:
        cls: A generic class with type parameters.
        exclude_params: Optional set of parameter names to exclude.

    Returns:
        A dictionary mapping type parameters to their concrete types.
    """
    parameters_map = {}

    if _is_generic(cls):
        parameters_map = dict(
            zip(
                cls.__origin__.__parameters__,
                (_instantiate_generic(arg) if _is_generic(arg) else arg for arg in cls.__args__),
            )
        )

    if exclude_params:
        for param in exclude_params:
            parameters_map.pop(param, None)

    return parameters_map


def _get_fields_substitution(cls, parameters_map=None, exclude_params=None) -> tuple[dict[str, dict], dict]:
    """Calculate field substitutions for generic type parameters.

    Args:
        cls: A generic cwtch model class.
        parameters_map: Existing parameter mapping to extend.
        exclude_params: Parameters to exclude from substitution.

    Returns:
        A tuple of (fields_substitution_dict, parameters_map).
    """
    fields_subst = {"type": {}, "default": {}, "default_factory": {}}
    parameters_map = parameters_map or {}

    origin = getattr(cls, "__origin__", None)
    items = getattr(origin, "__orig_bases__", ())[::-1] + (cls,)

    for item in items:
        if not getattr(
            getattr(item, "__origin__", item),
            "__cwtch_model__",
            None,
        ) and not getattr(
            getattr(item, "__origin__", item),
            "__cwtch_view__",
            None,
        ):
            continue

        origin = getattr(item, "__origin__", None)

        item_parameters_map = _get_parameters_map(item, exclude_params=exclude_params)

        if not item_parameters_map:
            continue

        parameters_map.update(item_parameters_map)

        for f_name, f in origin.__dataclass_fields__.items():  # type: ignore
            for k in ("type", "default", "default_factory"):
                k_v = getattr(f, k)
                if hasattr(k_v, "__typing_subst__") and k_v in item_parameters_map:
                    fields_subst[k][f_name] = k_v.__typing_subst__(item_parameters_map[k_v])
                elif getattr(k_v, "__parameters__", None):
                    fields_subst[k][f_name] = k_v[*[item_parameters_map[tp] for tp in k_v.__parameters__]]

    return fields_subst, parameters_map


def _get_fields_substitution_for_view(fields, parameters_map) -> dict[str, dict]:
    """Calculate field substitutions for a view based on type parameters.

    Args:
        fields: Dictionary of field names to Field objects.
        parameters_map: Mapping of type parameters to concrete types.

    Returns:
        Dictionary with 'type', 'default', 'default_factory' substitutions.
    """
    fields_subst = {"type": {}, "default": {}, "default_factory": {}}

    for f_name, f in fields.items():
        for k in ("type", "default", "default_factory"):
            k_v = getattr(f, k)
            if hasattr(k_v, "__typing_subst__") and k_v in parameters_map:
                fields_subst[k][f_name] = k_v.__typing_subst__(parameters_map[k_v])
            elif getattr(k_v, "__parameters__", None):
                fields_subst[k][f_name] = k_v[
                    *[parameters_map[tp] if tp in parameters_map else tp for tp in k_v.__parameters__]
                ]

    return fields_subst


def _get_substituted_fields(cls, fields_subst: dict[str, dict]) -> dict[str, Field]:
    """Apply field substitutions from generic type parameters.

    Args:
        cls: The dataclass with fields.
        fields_subst: Dictionary of field substitutions to apply.

    Returns:
        Updated dictionary of field names to Field objects.
    """
    fields = {k: v for k, v in cls.__dataclass_fields__.items()}

    for f_name, f in fields.items():
        new_f = None

        for k in ("type", "default", "default_factory"):
            subst = fields_subst[k]

            if f_name not in subst:
                continue

            if getattr(f, k) != subst[f_name]:
                new_f = new_f or _copy_field(f)
                setattr(new_f, k, subst[f_name])

        if new_f:
            fields[f_name] = new_f

    return fields


def _get_substituted_annotations(cls, fields_subst: dict[str, dict]) -> dict:
    """Apply type substitutions to class annotations.

    Args:
        cls: The class with annotations.
        fields_subst: Dictionary of type substitutions to apply.

    Returns:
        Updated annotations dictionary.
    """
    annotations = {k: v for k, v in cls.__annotations__.items()}
    subst = fields_subst["type"]

    for k in cls.__annotations__:
        if k not in subst:
            continue
        annotations[k] = subst[k]

    return annotations


@functools.cache
def _instantiate_generic(tp):
    """Instantiate a parameterized generic cwtch model.

    Args:
        tp: A parameterized generic type (e.g., MyModel[int]).

    Returns:
        A new class with concrete type parameters.

    Raises:
        TypeError: If tp is not a parameterized generic type.
    """
    if not _is_generic(tp):
        raise TypeError("must be called with a subscripted dataclass type")

    __origin__ = tp.__origin__

    x = ", ".join(map(lambda x: x.strip("'"), (getattr(arg, "__origin__", arg).__name__ for arg in tp.__args__)))

    cls = type(
        f"{__origin__.__name__}[{x}]",  # type: ignore
        (__origin__,),  # type: ignore
        {
            "__annotations__": {k: v for k, v in __origin__.__annotations__.items()},
        },
    )

    for k, v in list(cls.__dict__.items()):
        if isinstance(v, _ViewDesc):
            delattr(cls, k)

    fields_subst, parameters_map = _get_fields_substitution(tp)

    if fields_subst:
        cls.__dataclass_fields__ = _get_substituted_fields(cls, fields_subst)
        cls.__annotations__ = _get_substituted_annotations(cls, fields_subst)

    for k, v in cls.__dataclass_fields__.items():
        if v.default is not _MISSING:
            setattr(cls, k, v)

    if is_cwtch_view(cls):
        cls = cls.cwtch_rebuild(attach=False)
    else:
        cls = cls.cwtch_rebuild()

    # build views
    for f_k in __origin__.__dict__:
        f_v = getattr(cls, f_k)

        if not is_cwtch_view(f_v):
            continue

        bases: tuple[Type[Any], ...] = (f_v,)

        if Generic in f_v.__bases__:
            bases += (Generic[*f_v.__parameters__],)  # type: ignore

        view_cls = new_class(
            f"{f_v.__name__}[{x}]",
            bases,
            exec_body=lambda ns: ns.update(
                {
                    f_name: _copy_field(f)
                    for f_name, f in f_v.__dataclass_fields__.items()
                    if f_name in f_v.__annotations__
                }
            ),
        )

        view_cls.__annotations__ = {k: v for k, v in f_v.__annotations__.items()}

        view_fields_subst = _get_fields_substitution_for_view(view_cls.__dataclass_fields__, parameters_map)

        if view_fields_subst:
            view_cls.__dataclass_fields__ = _get_substituted_fields(f_v, view_fields_subst)
            view_cls.__annotations__ = _get_substituted_annotations(f_v, view_fields_subst)

        for k in view_cls.__annotations__:
            setattr(view_cls, k, view_cls.__dataclass_fields__[k])

        view_params = view_cls.__cwtch_view_params__

        setattr(
            cls,
            f_k,
            _build_view(
                cls,
                view_cls,
                view_params.get("name", UNSET),
                cls,
                view_params.get("include", UNSET),
                view_params.get("exclude", UNSET),
                view_params.get("slots", UNSET),
                view_params.get("kw_only", UNSET),
                view_params.get("env_prefix", UNSET),
                view_params.get("env_source", UNSET),
                view_params.get("validate", UNSET),
                view_params.get("add_disable_validation_to_init", UNSET),
                view_params.get("extra", UNSET),
                view_params.get("repr", UNSET),
                view_params.get("eq", UNSET),
                view_params.get("recursive", UNSET),
            ),
        )

    return cls


def _make_class_getitem(__class__):
    """Create a custom __class_getitem__ method for generic cwtch models.

    This enables using subscript syntax (e.g., MyModel[int]) to create
    parameterized instances of generic cwtch models.

    Args:
        __class__: The class to create __class_getitem__ for.

    Returns:
        A __class_getitem__ method that handles generic instantiation.
    """

    def __class_getitem__(cls, *args, **kwds):
        origin = super().__class_getitem__(*args, **kwds)  # type: ignore

        if not hasattr(origin, "__cwtch_instantiated__"):
            instantiated = _instantiate_generic(origin)
            setattr(origin, "__cwtch_instantiated__", instantiated)

        return origin.__cwtch_instantiated__

    setattr(__class_getitem__, "__cwtch_method__", True)

    return __class_getitem__


def _copy_field(f: Field) -> Field:
    """Create a deep copy of a Field object.

    Args:
        f: The Field object to copy.

    Returns:
        A new Field object with copied attributes.
    """
    new_f = Field(
        default=f.default,
        default_factory=f.default_factory,
        init=f.init,
        init_alias=f.init_alias,
        asdict_alias=f.asdict_alias,
        repr=f.repr,
        compare=f.compare,
        property=f.property,
        validate=f.validate,
        metadata=deepcopy(f.metadata),
        kw_only=f.kw_only,
    )
    new_f.name = f.name
    new_f.type = f.type
    new_f._field_type = f._field_type

    return new_f


def _create_fn(cls, name, args, body, *, globals=None, locals=None):
    """Dynamically create a function with specified attributes.

    Args:
        cls: The class the function will belong to.
        name: The name of the function.
        args: List of argument names.
        body: List of Python statements for the function body.
        globals: Optional global variables for the function.
        locals: Optional local variables for the function.

    Returns:
        The created function object.

    Raises:
        SyntaxError: If the generated function code is invalid.
    """
    if locals is None:
        locals = {}

    locals["__class__"] = cls

    args = ", ".join(args)
    body = "\n".join(f"        {line}" for line in body)
    text = "\n".join(
        [
            f"    def {name}({args}):",
            f"{body}",
        ]
    )
    local_vars = ", ".join(locals.keys())
    text = f"def _create_fn({local_vars}):\n\n{text}\n\n    return {name}"
    ns = {}

    exec(text, globals, ns)

    return ns["_create_fn"](**locals)


def _create_init(
    cls,
    fields,
    kw_only,
    validate,
    add_disable_validation_to_init,
    extra,
    env_prefixes,
    env_source,
):
    """Create an __init__ method for a cwtch model.

    This generates an __init__ method that handles field initialization,
    validation, environment variables, and circular reference handling.

    Args:
        cls: The class to create __init__ for.
        fields: Dictionary of field names to Field objects.
        kw_only: Whether all fields should be keyword-only.
        validate: Whether to validate field values.
        add_disable_validation_to_init: Whether to add disable_validation param.
        extra: How to handle extra arguments ('ignore' or 'forbid').
        env_prefixes: Prefix(es) for environment variables.
        env_source: Callable that returns environment variables dict.

    Returns:
        The generated __init__ function.
    """

    def empty_validator(value, T, /):
        return value

    globals = {}
    locals = {
        "config": config,
        "_MISSING": _MISSING,
        "_DEFAULT": _DEFAULT,
        "_get_cache": _get_cache,
        "_env_prefixes": env_prefixes,
        "_env_source": env_source or _default_env_source,
        "_json_loads": json.loads,
        "_builtins_id": id,
        "ValidationError": ValidationError,
        "JSONDecodeError": json.JSONDecodeError,
        "empty_validator": empty_validator,
    }

    fields = {k: v for k, v in fields.items() if v.init and not v.computed_field}

    args = ["__cwtch_self__"]

    if fields:
        args.append("/")

    body = [
        "errors = {}",
        "__cwtch_fields_set__ = ()",
        "__cwtch_extra_fields__ = ()",
    ]

    if env_prefixes is not UNSET:
        body += [
            "env_source_data = _env_source()",
            "env_data = {}",
            "for f_name, f in __cwtch_self__.__dataclass_fields__.items():",
            "   if env_var := f.metadata.get('env_var', True):",
            "       for env_prefix in _env_prefixes:",
            "           if isinstance(env_var, str):",
            "               key = env_var",
            "           else:",
            "               key = f'{env_prefix}{f_name}'.upper()",
            "           if key in env_source_data:",
            "               env_data[f_name] = env_value = env_source_data[key]",
            "               if env_value[0] in ('[', '{') and env_value[-1] in (']', '}'):",
            "                   try:",
            "                       env_data[f_name] = _json_loads(env_value)",
            "                   except JSONDecodeError:",
            "                       pass",
            "               break",
        ]

    if fields:
        indent = ""
        body += [
            "if __cwtch_cache_key is not None:",
            "    _get_cache()[__cwtch_cache_key] = __cwtch_self__",
            "try:",
        ]
        indent = " " * 4

        if extra == "forbid":
            allowed_extra_field_names = [f'"{f.init_alias}"' for f in fields.values() if f.init_alias]
            body += [
                f"{indent}if __extra_kwds:",
                f"{indent}    allowed_extra_field_names = {{{', '.join(allowed_extra_field_names)}}}",
                f"{indent}    for k in __extra_kwds:",
                f"{indent}        if k not in allowed_extra_field_names:",
                f"{indent}            err = TypeError('unexpected field')",
                f"{indent}            if config.RAISE_ON_FIRST_ERROR:",
                f"{indent}                raise ValidationError(..., __cwtch_self__.__class__, [err], path=[k])",
                f"{indent}            else:",
                f"{indent}                errors[k] = ValidationError(..., None, [err], path=[k])",
            ]

        any_fields = [
            f
            for f in sorted(
                [f for f in fields.values() if f.kw_only is False or (f.kw_only is UNSET and not kw_only)],
                key=lambda f: f.default is not _MISSING or f.default_factory is not _MISSING,
            )
        ]
        for f in any_fields:
            if f.default is not _MISSING or f.default_factory is not _MISSING:
                args.append(f"{f.name}: t_{f.name} = _DEFAULT")
            else:
                args.append(f"{f.name}: t_{f.name} = _MISSING")

        kw_only_fields = [f for f in fields.values() if f.kw_only or (f.kw_only is UNSET and kw_only)]

        if kw_only_fields:
            args.append("*")

        for f in kw_only_fields:
            if f.default is not _MISSING or f.default_factory is not _MISSING:
                args.append(f"{f.name}: t_{f.name} = _DEFAULT")
            else:
                args.append(f"{f.name}: t_{f.name} = _MISSING")

        for field in any_fields + kw_only_fields:
            f_name = field.name
            locals[f"f_{f_name}"] = field
            locals[f"t_{f_name}"] = update_metadata(field.type)
            locals[f"d_{f_name}"] = field.default
            locals[f"df_{f_name}"] = field.default_factory
            if env_prefixes is not UNSET:
                body += [
                    f"{indent}if {f_name} is _MISSING or {f_name} is _DEFAULT:",
                    f"{indent}    if '{f_name}' in env_data:",
                    f"{indent}        {f_name} = env_data['{f_name}']",
                ]
                if field.default is not _MISSING:
                    body += [
                        f"{indent}    else:",
                        f"{indent}        {f_name} = d_{f_name}",
                    ]
                elif field.default_factory is not _MISSING:
                    body += [
                        f"{indent}    else:",
                        f"{indent}        {f_name} = df_{f_name}()",
                    ]
                else:
                    body += [
                        f"{indent}    else:",
                        f"{indent}        err = TypeError('field required')",
                        f"{indent}        if config.RAISE_ON_FIRST_ERROR:",
                        f"{indent}            raise ValidationError(..., __cwtch_self__.__class__, [err], path=['{f_name}'])",
                        f"{indent}        else:",
                        f"{indent}            locals()[v_{f_name}] = empty_validator",
                        f"{indent}            errors['{f_name}'] = ValidationError(..., None, [err], path=['{f_name}'])",
                    ]
                body += [
                    f"{indent}else:",
                    f"{indent}    __cwtch_fields_set__ += ('{f_name}',)",
                ]
            else:
                if field.default is not _MISSING or field.default_factory is not _MISSING:
                    body += [
                        f"{indent}if {f_name} is _MISSING or {f_name} is _DEFAULT:",
                    ]
                else:
                    body += [
                        f"{indent}if {f_name} is _MISSING:",
                    ]

                if field.init_alias:
                    body += [
                        f"{indent}    if '{field.init_alias}' in __extra_kwds:",
                        f"{indent}        {f_name} = __extra_kwds['{field.init_alias}']",
                        f"{indent}    else:",
                    ]
                    indent += "    "
                if field.default is not _MISSING:
                    body += [
                        f"{indent}    {f_name} = d_{f_name}",
                    ]
                elif field.default_factory is not _MISSING:
                    body += [
                        f"{indent}    {f_name} = df_{f_name}()",
                    ]
                else:
                    body += [
                        f"{indent}    err = TypeError('field required')",
                        f"{indent}    if config.RAISE_ON_FIRST_ERROR:",
                        f"{indent}        raise ValidationError(..., __cwtch_self__.__class__, [err], path=['{f_name}'])",
                        f"{indent}    else:",
                        f"{indent}      locals()[v_{f_name}] = empty_validator",
                        f"{indent}      errors['{f_name}'] = ValidationError(..., None, [err], path=['{f_name}'])",
                    ]
                if field.init_alias:
                    indent = indent[:-4]
                body += [
                    f"{indent}else:",
                    f"{indent}    __cwtch_fields_set__ += ('{f_name}',)",
                ]
            if field.validate or (field.validate is UNSET and validate):
                validator = get_validator(field.type)
                if validator == validate_generic_alias:
                    validator = get_validator(field.type.__origin__)
                locals[f"v_{f_name}"] = validator
                if add_disable_validation_to_init:
                    body += [
                        f"{indent}if disable_validation is not True:",
                        f"{indent}    try:",
                        f"{indent}        _{f_name} = v_{f_name}({f_name}, t_{f_name})",
                        f"{indent}    except Exception as e:",
                        f"{indent}        _{f_name} = None",
                        f"{indent}        e.__cause__ = None",
                        f"{indent}        if isinstance(e, ValidationError):",
                        f"{indent}            path = ['{f_name}'] + (e.path or [])",
                        f"{indent}        else:",
                        f"{indent}            path = ['{f_name}']",
                        f"{indent}        err  = ValidationError(..., __cwtch_self__.__class__, [e], path=path)",
                        f"{indent}        err.__cause__ = None",
                        f"{indent}        if config.RAISE_ON_FIRST_ERROR:",
                        f"{indent}            err  = ValidationError(..., __cwtch_self__.__class__, [e], path=path)",
                        f"{indent}            raise err",
                        f"{indent}        else:",
                        f"{indent}            err  = ValidationError(..., None, [e], path=path)",
                        f"{indent}            errors['{f_name}'] = err",
                    ]
                    body += [
                        f"{indent}else:",
                        f"{indent}    _{f_name} = {f_name}",
                    ]
                else:
                    body += [
                        f"{indent}try:",
                        f"{indent}    _{f_name} = v_{f_name}({f_name}, t_{f_name})",
                        f"{indent}except Exception as e:",
                        f"{indent}    _{f_name} = None",
                        f"{indent}    e.__cause__ = None",
                        f"{indent}    if isinstance(e, ValidationError):",
                        f"{indent}        if e.value == ...:",
                        f"{indent}            e.value = {f_name}",
                        f"{indent}        path = ['{f_name}'] + (e.path or [])",
                        f"{indent}    else:",
                        f"{indent}        e = ValidationError({f_name}, t_{f_name}, [e])",
                        f"{indent}        e.__cause__ = None",
                        f"{indent}        path = ['{f_name}']",
                        f"{indent}    if config.RAISE_ON_FIRST_ERROR:",
                        f"{indent}        err = ValidationError(..., __cwtch_self__.__class__, [e], path=path)",
                        f"{indent}        err.__cause__ = None",
                        f"{indent}        raise err",
                        f"{indent}    else:",
                        f"{indent}        err = ValidationError(..., None, [e], path=path)",
                        f"{indent}        err.__cause__ = None",
                        f"{indent}        errors['{f_name}'] = err",
                    ]
            else:
                body += [
                    f"{indent}_{f_name} = {f_name}",
                ]

            if field.property:
                body += [
                    f"{indent}__cwtch_self__._prop_{f_name} = _{f_name}",
                    f"{indent}__class__.{f_name} = property(lambda self: self._prop_{f_name})",
                ]
            else:
                body += [
                    f"{indent}__cwtch_self__.{f_name} = _{f_name}",
                ]

        body += [
            "finally:",
            "    _get_cache().pop(__cwtch_cache_key, None)",
        ]

    body += [
        "if errors:",
        "    raise ValidationError(..., __cwtch_self__.__class__, list(errors.values()))",
    ]

    if extra == "allow":
        body += [
            "__cwtch_extra_fields__ = tuple(__extra_kwds.keys())",
            "for k, v in __extra_kwds.items():",
            "    setattr(__cwtch_self__, k, v)",
            "    __cwtch_fields_set__ += (k,)",
        ]

    body += [
        "__cwtch_self__.__cwtch_fields_set__ = __cwtch_fields_set__",
        "__cwtch_self__.__cwtch_extra_fields__ = __cwtch_extra_fields__",
    ]

    args.append("__cwtch_cache_key=None")

    if add_disable_validation_to_init:
        args += ["disable_validation=_MISSING"]

    args += ["**__extra_kwds"]

    if "__post_init__" in cls.__dict__:
        body += [
            "try:",
            "    __class__.__dict__['__post_init__'](__cwtch_self__)",
            "except ValueError as e:",
            "    if config.RAISE_ON_FIRST_ERROR:",
            "        raise ValidationError(",
            "            __cwtch_self__,",
            "            __cwtch_self__.__class__,",
            "            [e],",
            "            path=[f'{__cwtch_self__.__class__.__name__}.__post_init__']",
            "        )",
            "    else:",
            "        errors['__post_init__'] = ValidationError(",
            "            __cwtch_self__,",
            "            __cwtch_self__.__class__,",
            "            [e],",
            "            path=[f'{__cwtch_self__.__class__.__name__}.__post_init__']",
            "        )",
        ]

    if getattr(cls, "__post_validate__", None):
        body += [
            "try:",
            "    __cwtch_self__.__post_validate__()",
            "except ValueError as e:",
            "    if config.RAISE_ON_FIRST_ERROR:",
            "        raise ValidationError(",
            "            __cwtch_self__,",
            "            __cwtch_self__.__class__,",
            "            [e],",
            "            path=[f'{__cwtch_self__.__class__.__name__}.__post_validate__']",
            "        )",
            "    else:",
            "        errors['__post_validate__'] = ValidationError(",
            "            __cwtch_self__,",
            "            __cwtch_self__.__class__,",
            "            [e],",
            "            path=[f'{__cwtch_self__.__class__.__name__}.__post_validate__']",
            "        )",
        ]

    __init__ = _create_fn(cls, "__init__", args, body, globals=globals, locals=locals)

    __init__.__module__ = cls.__module__
    __init__.__qualname__ = f"{cls.__name__}.__init__"

    return __init__


def _create_repr(cls):
    """Create a __repr__ method for a cwtch model.

    Args:
        cls: The class to create __repr__ for.

    Returns:
        The generated __repr__ function.
    """
    globals = {}
    locals = {}

    args = ["__cwtch_self__"]

    body = ['return f"{__cwtch_self__.__class__.__name__}()"']

    __repr__ = _create_fn(cls, "__repr__", args, body, globals=globals, locals=locals)

    __repr__.__module__ = cls.__module__
    __repr__.__qualname__ = f"{cls.__name__}.__repr__"

    return __repr__


def _create_rich_repr(cls, fields):
    """Create a __rich_repr__ method for rich console output.

    Args:
        cls: The class to create __rich_repr__ for.
        fields: Dictionary of field names to Field objects.

    Returns:
        The generated __rich_repr__ function, or None if no fields.
    """
    globals = {}
    locals = {
        "_MISSING": _MISSING,
    }

    fields = {k: v for k, v in fields.items() if v.repr is not False}

    args = ["__cwtch_self__"]

    body = []

    if not fields:
        return

    for f_name in fields:
        body.append(f"yield '{f_name}', getattr(__cwtch_self__, '{f_name}', _MISSING)")

    __rich_repr__ = _create_fn(cls, "__rich_repr__", args, body, globals=globals, locals=locals)

    __rich_repr__.__module__ = cls.__module__
    __rich_repr__.__qualname__ = f"{cls.__name__}.__rich_repr__"

    return __rich_repr__


def _create_eq(cls, fields):
    """Create an __eq__ method for a cwtch model.

    Args:
        cls: The class to create __eq__ for.
        fields: Dictionary of field names to Field objects.

    Returns:
        The generated __eq__ function.
    """
    globals = {}
    locals = {}

    fields = {k: v for k, v in fields.items() if v.compare is not False}

    args = ["__cwtch_self__", "other"]

    comparison = " and ".join([f"__cwtch_self__.{field} == other.{field}" for field in fields]) or "True"

    body = [
        "if __cwtch_self__ is other:",
        "    return True",
        "if not hasattr(other, '__cwtch_model__') or __cwtch_self__.__class__ is not other.__class__:",
        "    return False",
        f"return {comparison}",
    ]

    __eq__ = _create_fn(cls, "__eq__", args, body, globals=globals, locals=locals)

    __eq__.__module__ = cls.__module__
    __eq__.__qualname__ = f"{cls.__name__}.__eq__"

    return __eq__


def _create_init_subclass(cls):
    """Create an __init_subclass__ method to propagate view descriptors.

    Args:
        cls: The class to create __init_subclass__ for.

    Returns:
        The generated __init_subclass__ function.
    """
    globals = {}
    locals = {"_ViewDesc": _ViewDesc}

    args = ["cls", "**kwds"]

    body = [
        "super().__init_subclass__(**kwds)",
        "for k, v in cls.__base__.__dict__.items():",
        "    if v.__class__ != _ViewDesc:",
        "        continue",
        "    setattr(cls, k, _ViewDesc(v.view_cls))",
    ]

    __init_subclass__ = _create_fn(cls, "__init_subclass__", args, body, globals=globals, locals=locals)

    __init_subclass__.__module__ = cls.__module__
    __init_subclass__.__qualname__ = f"{cls.__name__}.__init_subclass__"

    return __init_subclass__


def _sort_dataclass_fields(
    fields: dict[str, Field],
    base_fields: dict[str, Field],
    kw_only: bool,
) -> dict[str, Field]:
    """Sort dataclass fields according to Python dataclass rules.

    Fields are ordered with required fields first, then fields with defaults,
    then keyword-only fields. Base class fields come before derived fields.

    Model fields order:
      - any_fields_base
      - any_fields
      - any_fields_base_with_defaults
      - any_fields_with_defaults
      - kw_only_fields_base
      - kw_only_fields

    Args:
        fields: Dictionary of field names to Field objects.
        base_fields: Dictionary of base class fields.
        kw_only: Whether all fields should be keyword-only.

    Returns:
        Sorted dictionary of field names to Field objects.
    """

    any_fields = sorted(
        filter(
            lambda f: f.default is _MISSING and f.default_factory is _MISSING,
            [f for f in fields.values() if f.kw_only is False or (f.kw_only is UNSET and not kw_only)],
        ),
        key=lambda f: f.name in base_fields,
    )

    any_fields_with_default = sorted(
        filter(
            lambda f: f.default is not _MISSING or f.default_factory is not _MISSING,
            [f for f in fields.values() if f.kw_only is False or (f.kw_only is UNSET and not kw_only)],
        ),
        key=lambda f: f.name in base_fields,
    )

    kw_only_fields = sorted(
        [f for f in fields.values() if f.kw_only or (f.kw_only is UNSET and kw_only)],
        key=lambda f: f.name in base_fields,
    )

    return {f.name: f for f in chain(any_fields, any_fields_with_default, kw_only_fields)}


def _build(
    cls,
    slots: bool,
    kw_only: bool,
    env_prefix: Unset[str | Sequence[str]],
    env_source: Unset[Callable],
    validate: bool,
    add_disable_validation_to_init: bool,
    extra: Extra,
    repr: bool,
    eq: bool,
    recursive: bool | Sequence[str],
    rebuild: bool = False,
):
    """Build or rebuild a cwtch model class.

    This is the main function that transforms a class into a cwtch model
    by adding __init__, __eq__, __repr__, validation, and other functionality.

    Args:
        cls: The class to transform.
        slots: Whether to use __slots__.
        kw_only: Whether fields are keyword-only.
        env_prefix: Prefix for environment variables.
        env_source: Source for environment variables.
        validate: Whether to validate fields.
        add_disable_validation_to_init: Whether to add disable_validation param.
        extra: How to handle extra arguments.
        repr: Whether to generate __repr__.
        eq: Whether to generate __eq__.
        recursive: Fields to recursively convert to views in nested models.
            When a model field has a type that is another cwtch model, setting
            recursive to True will automatically use the corresponding view
            of that nested model instead of the model itself.
            - True: Convert all nested cwtch models to their views
            - False: Don't convert nested models to views
            - Sequence[str]: Only convert to views with these specific names
        rebuild: Whether this is a rebuild operation.

    Returns:
        The transformed cwtch model class.
    """
    __bases__ = cls.__bases__
    __annotations__ = cls.__annotations__
    __dict__ = {k: v for k, v in cls.__dict__.items()}

    for k, v in __dict__.items():
        if isinstance(v, Field) and k not in __annotations__:
            raise TypeError(f"{k} is a field but has no type annotation")

    defaults = {k: __dict__[k] for k, v in __annotations__.items() if k in __dict__ and not _is_classvar(v)}

    __dataclass_fields__ = getattr(cls, "__dataclass_fields__", {}).copy()

    for base in __bases__[::-1]:
        if hasattr(base, "__dataclass_fields__"):
            __dataclass_fields__.update(
                {k: v for k, v in base.__dataclass_fields__.items() if k not in __dataclass_fields__}
            )

    base_fields = __dataclass_fields__

    for f_name, f_type in __annotations__.items():
        if _is_classvar(f_type):
            continue
        if f_name in defaults:
            f = defaults[f_name]
            if not isinstance(f, Field) and _is_mutable_default(f):
                raise ValueError(
                    f"mutable default {type(f).__name__} for field '{f_name}' is not allowed: use default_factory"
                )
        else:
            f = __dataclass_fields__.get(f_name, _MISSING)
        if not isinstance(f, Field):
            f = Field(default=f)
            f._field_type = _FIELD
        f.name = f_name
        f.type = f_type
        f.computed_field = False
        __dataclass_fields__[f_name] = f

    __dataclass_fields__ = _sort_dataclass_fields(__dataclass_fields__, base_fields, kw_only)

    for f in __dataclass_fields__.values():
        if not slots and f.default is not _MISSING:
            __dict__[f.name] = f.default
        else:
            __dict__.pop(f.name, None)

    for k, v in __dict__.items():
        if isinstance(v, property):
            __cwtch_computed_field_params__ = getattr(v.fget, "__cwtch_computed_field_params__", None)
            if __cwtch_computed_field_params__:
                f = Field(
                    init=False,
                    computed_field=True,
                    **__cwtch_computed_field_params__,
                )
                f.type = v.fget.__annotations__["return"]
                __dataclass_fields__[k] = f

    if not rebuild:
        if slots:
            if "__slots__" in __dict__:
                raise TypeError(f"{cls.__name__} already specifies __slots__")
            __slots__ = tuple(
                [f"_prop_{f_name}" if f.property is True else f_name for f_name, f in __dataclass_fields__.items()]
            )
            __dict__["__slots__"] = __slots__ + ("__cwtch_fields_set__", "__cwtch_extra_fields__")
        __dict__.pop("__dict__", None)
        cls = type(cls.__name__, cls.__bases__, __dict__)

    if env_prefix is UNSET or isinstance(env_prefix, (list, tuple, str)):
        env_prefixes = env_prefix
    else:
        env_prefixes = [env_prefix]

    setattr(
        cls,
        "__init__",
        _create_init(
            cls,
            __dataclass_fields__,
            kw_only,
            validate,
            add_disable_validation_to_init,
            extra,
            env_prefixes,
            env_source,
        ),
    )

    if repr:
        __rich_repr__ = _create_rich_repr(cls, __dataclass_fields__)
        if __rich_repr__:
            setattr(cls, "__rich_repr__", __rich_repr__)
            rich.repr.auto()(cls)  # type: ignore
        else:
            __repr__ = _create_repr(cls)
            setattr(cls, "__repr__", __repr__)

    if eq:
        setattr(cls, "__eq__", _create_eq(cls, __dataclass_fields__))

    if hasattr(cls, "__parameters__"):
        if not hasattr(cls.__class_getitem__, "__cwtch_method__"):
            setattr(cls, "__class_getitem__", classmethod(_make_class_getitem(cls)))

    setattr(cls, "__init_subclass__", classmethod(_create_init_subclass(cls)))

    setattr(cls, "__dataclass_fields__", __dataclass_fields__)

    if sys.version_info.minor > 11:
        setattr(
            cls,
            "__dataclass_params__",
            _DataclassParams(True, repr, eq, False, False, False, False, False, slots, False),
        )
    else:
        setattr(
            cls,
            "__dataclass_params__",
            _DataclassParams(True, repr, eq, False, False, False),
        )

    def cwtch_rebuild(cls):
        if not is_cwtch_model(cls):
            raise Exception("not cwtch model")
        return _build(
            cls,
            slots=slots,
            kw_only=kw_only,
            env_prefix=env_prefix,
            env_source=env_source,
            validate=validate,
            add_disable_validation_to_init=add_disable_validation_to_init,
            extra=extra,
            repr=repr,
            eq=eq,
            recursive=recursive,
            rebuild=True,
        )

    setattr(cls, "cwtch_rebuild", classmethod(cwtch_rebuild))
    cls.cwtch_rebuild.__func__.__qualname__ = "cwtch_rebuild"

    def cwtch_update_forward_refs(cls, localns: dict | None = None, globalns: dict | None = None):
        if globalns is None:
            module = sys.modules.get(cls.__module__, None)
            globalns = vars(module) if module else {}

        if localns is None:
            localns = sys._getframe(1).f_locals

        resolve_types(cls, globalns=globalns, localns=localns)

    setattr(cls, "cwtch_update_forward_refs", classmethod(cwtch_update_forward_refs))
    cls.cwtch_update_forward_refs.__func__.__qualname__ = "cwtch_update_forward_refs"

    setattr(cls, "__cwtch_model__", True)

    setattr(
        cls,
        "__cwtch_params__",
        {
            "slots": slots,
            "kw_only": kw_only,
            "env_prefix": env_prefix,
            "env_source": env_source,
            "validate": validate,
            "add_disable_validation_to_init": add_disable_validation_to_init,
            "extra": extra,
            "repr": repr,
            "eq": eq,
            "recursive": recursive,
        },
    )

    setattr(cls, "__cwtch_views__", set())

    if rebuild:
        for k in cls.__dict__:
            v = getattr(cls, k)
            if hasattr(v, "cwtch_rebuild"):
                v.cwtch_rebuild()

    if not rebuild:
        # rebuild inherited views
        for base in __bases__[::-1]:
            for k in base.__dict__:
                v = getattr(base, k)
                if k in cls.__dict__ or not is_cwtch_view(v):
                    continue
                view_params = v.__cwtch_view_params__
                setattr(
                    cls,
                    k,
                    _build_view(
                        cls,
                        v,
                        view_params.get("name", UNSET),
                        cls,
                        view_params.get("include", UNSET),
                        view_params.get("exclude", UNSET),
                        view_params.get("slots", UNSET),
                        view_params.get("kw_only", UNSET),
                        view_params.get("env_prefix", UNSET),
                        view_params.get("env_source", UNSET),
                        view_params.get("validate", UNSET),
                        view_params.get("add_disable_validation_to_init", UNSET),
                        view_params.get("extra", UNSET),
                        view_params.get("repr", UNSET),
                        view_params.get("eq", UNSET),
                        view_params.get("recursive", UNSET),
                    ),
                )

    def view(
        base_cls,
        name: Unset[str] = UNSET,
        *,
        base: Unset[Type] = UNSET,
        include: Unset[Sequence[str]] = UNSET,
        exclude: Unset[Sequence[str]] = UNSET,
        slots: Unset[bool] = UNSET,
        kw_only: Unset[bool] = UNSET,
        env_prefix: Unset[str | Sequence[str]] = UNSET,
        env_source: Unset[Callable] = UNSET,
        validate: Unset[bool] = UNSET,
        add_disable_validation_to_init: Unset[bool] = UNSET,
        extra: Unset[Extra] = UNSET,
        repr: Unset[bool] = UNSET,
        eq: Unset[bool] = UNSET,
        recursive: Unset[bool | Sequence[str]] = UNSET,
    ):
        return globals()["view"](
            base_cls,
            name=name,
            base=base,
            attach=base_cls,
            include=include,
            exclude=exclude,
            slots=slots,
            kw_only=kw_only,
            env_prefix=env_prefix,
            env_source=env_source,
            validate=validate,
            add_disable_validation_to_init=add_disable_validation_to_init,
            extra=extra,
            repr=repr,
            eq=eq,
            recursive=recursive,
        )

    cls.view = classmethod(view)

    return cls


def _update_type_with_views(tp: Any, view_names: Sequence[str]) -> Any:
    """Recursively update type to use views instead of models.

    Args:
        tp: The type to update.
        view_names: List of view names to use for substitution.

    Returns:
        The updated type with views instead of models.
    """

    if isinstance(tp, UnionType):
        return Union[*(_update_type_with_views(arg, view_names) for arg in tp.__args__)]

    origin = getattr(tp, "__origin__", None)
    if origin is not None:
        return tp.__class__(
            _update_type_with_views(origin, view_names),
            (
                tp.__metadata__
                if hasattr(tp, "__metadata__")
                else tuple(_update_type_with_views(arg, view_names) for arg in tp.__args__)
            ),
        )

    if getattr(tp, "__cwtch_model__", None):
        for view_name in view_names:
            if hasattr(tp, view_name):
                return getattr(tp, view_name)
        for view_name in view_names:
            if hasattr(tp, "__cwtch_view_base__") and hasattr(tp.__cwtch_view_base__, view_name):
                return getattr(tp.__cwtch_view_base__, view_name)
    return tp


def _build_view(
    cls: Type,
    view_cls,
    name: Unset[str],
    attach: Unset[bool | Type],
    include: Unset[Sequence[str]],
    exclude: Unset[Sequence[str]],
    slots: Unset[bool],
    kw_only: Unset[bool],
    env_prefix: Unset[str | Sequence[str]],
    env_source: Unset[Callable],
    validate: Unset[bool],
    add_disable_validation_to_init: Unset[bool],
    extra: Unset[Extra],
    repr: Unset[bool],
    eq: Unset[bool],
    recursive: Unset[bool | Sequence[str]],
    rebuild: bool = False,
):
    """Build or rebuild a cwtch view class.

    Views are subsets of model fields with their own validation and configuration.

    Args:
        cls: The base model class.
        view_cls: The view class to build.
        name: The name of the view.
        attach: Whether to attach view to base class.
        include: Fields to include in the view.
        exclude: Fields to exclude from the view.
        slots: Whether to use __slots__.
        kw_only: Whether fields are keyword-only.
        env_prefix: Prefix for environment variables.
        env_source: Source for environment variables.
        validate: Whether to validate fields.
        add_disable_validation_to_init: Whether to add disable_validation param.
        extra: How to handle extra arguments.
        repr: Whether to generate __repr__.
        eq: Whether to generate __eq__.
        recursive: Fields to recursively convert to views in nested models.
            When a view field has a type that is another cwtch model, setting
            recursive to True will automatically use the corresponding view
            of that nested model instead of the model itself.
            - True: Convert all nested cwtch models to their views
            - False/None: Don't convert nested models to views
            - Sequence[str]: Only convert to views with these specific names
        rebuild: Whether this is a rebuild operation.

    Returns:
        The built view class.
    """

    __bases__ = view_cls.__bases__
    __annotations__ = view_cls.__annotations__
    __dict__ = {k: v for k, v in view_cls.__dict__.items()}

    for k, v in __dict__.items():
        if isinstance(v, Field) and k not in __annotations__:
            raise TypeError(f"{k} is a field but has no type annotation")

    if is_cwtch_view(cls):
        __cwtch_params__ = cls.__cwtch_view_params__
    else:
        __cwtch_params__ = cls.__cwtch_params__

    __cwtch_view_params__ = {
        "include": include,
        "exclude": exclude,
        "slots": __cwtch_params__["slots"],
        "kw_only": __cwtch_params__["kw_only"],
        "env_prefix": __cwtch_params__["env_prefix"],
        "env_source": __cwtch_params__["env_source"],
        "validate": __cwtch_params__["validate"],
        "add_disable_validation_to_init": __cwtch_params__["add_disable_validation_to_init"],
        "repr": __cwtch_params__["repr"],
        "eq": __cwtch_params__["eq"],
        "extra": __cwtch_params__["extra"],
        "recursive": __cwtch_params__["recursive"],
    }

    if hasattr(view_cls, "__cwtch_view_params__"):
        __cwtch_view_params__.update({k: v for k, v in view_cls.__cwtch_view_params__.items() if v != UNSET})

    if name is not UNSET:
        __cwtch_view_params__["name"] = name
    if attach is not UNSET:
        if not isinstance(attach, bool) and not (is_cwtch_model(attach) or is_cwtch_view(attach)):
            raise Error("'attach' parameter should be a bool, cwtch model or view")
        __cwtch_view_params__["attach"] = attach
    if include is not UNSET:
        __cwtch_view_params__["include"] = include
    if exclude is not UNSET:
        __cwtch_view_params__["exclude"] = exclude
    if slots is not UNSET:
        __cwtch_view_params__["slots"] = slots
    if kw_only is not UNSET:
        __cwtch_view_params__["kw_only"] = kw_only
    if env_prefix is not UNSET:
        __cwtch_view_params__["env_prefix"] = env_prefix
    if env_source is not UNSET:
        __cwtch_view_params__["env_source"] = env_source
    if validate is not UNSET:
        __cwtch_view_params__["validate"] = validate
    if add_disable_validation_to_init is not UNSET:
        __cwtch_view_params__["add_disable_validation_to_init"] = add_disable_validation_to_init
    if repr is not UNSET:
        __cwtch_view_params__["repr"] = repr
    if eq is not UNSET:
        __cwtch_view_params__["eq"] = eq
    if extra is not UNSET:
        __cwtch_view_params__["extra"] = extra
    if recursive is not UNSET:
        __cwtch_view_params__["recursive"] = recursive

    __dataclass_fields__ = {k: _copy_field(v) for k, v in cls.__dataclass_fields__.items()}

    if hasattr(view_cls, "__dataclass_fields__"):
        __dataclass_fields__.update({k: _copy_field(v) for k, v in view_cls.__dataclass_fields__.items()})
    else:
        for base in __bases__[::-1]:
            if hasattr(base, "__dataclass_fields__"):
                __dataclass_fields__.update({k: _copy_field(v) for k, v in base.__dataclass_fields__.items()})

    base_fields = __dataclass_fields__

    defaults = {k: __dict__[k] for k, v in __annotations__.items() if k in __dict__ and not _is_classvar(v)}

    for f_name, f_type in __annotations__.items():
        if _is_classvar(f_type):
            continue
        f = defaults.get(f_name, _MISSING)
        if not isinstance(f, Field):
            f = Field(default=f)
            f._field_type = _FIELD
        f.name = f_name
        f.type = f_type
        __dataclass_fields__[f_name] = f

    __dataclass_fields__ = _sort_dataclass_fields(__dataclass_fields__, base_fields, __cwtch_view_params__["kw_only"])

    view_name = __cwtch_view_params__.get("name", view_cls.__name__)

    include = __cwtch_view_params__.get("include", UNSET)
    if include and (missing_fields := set(include) - __dataclass_fields__.keys()):  # type: ignore
        raise Exception(f"fields {list(missing_fields)} not present")

    exclude = __cwtch_view_params__.get("exclude", UNSET)

    __dataclass_fields__ = {
        k: v
        for k, v in __dataclass_fields__.items()
        if (include is UNSET or k in include) and (exclude is UNSET or k not in exclude)
    }

    view_recursive = __cwtch_view_params__["recursive"]
    if view_recursive:
        view_names: Sequence[str] = cast(
            Sequence[str],
            view_recursive if isinstance(view_recursive, (list, tuple, set)) else [view_name],
        )
        for k, v in __dataclass_fields__.items():
            v.type = _update_type_with_views(v.type, view_names)
            if k in view_cls.__annotations__:
                view_cls.__annotations__[k] = v.type
            if v.default_factory is not _MISSING:
                v.default_factory = _update_type_with_views(v.default_factory, view_names)  # type: ignore

    if __cwtch_view_params__["env_prefix"] is UNSET or isinstance(
        __cwtch_view_params__["env_prefix"], (list, tuple, str)
    ):
        env_prefixes = __cwtch_view_params__["env_prefix"]
    else:
        env_prefixes = [__cwtch_view_params__["env_prefix"]]

    for f in __dataclass_fields__.values():
        if __cwtch_view_params__["slots"]:
            __dict__.pop(f.name, None)
        elif f.default is not _MISSING:
            __dict__[f.name] = f.default

    if not rebuild:
        if __cwtch_view_params__["slots"]:
            if "__slots__" in __dict__:
                raise TypeError(f"{cls.__name__} already specifies __slots__")
            __slots__ = tuple(
                [f"_prop_{f_name}" if f.property is True else f_name for f_name, f in __dataclass_fields__.items()]
            )
            __dict__["__slots__"] = __slots__ + ("__cwtch_fields_set__", "__cwtch_extra_fields__")
        __dict__.pop("__dict__", None)
        view_cls = type(view_cls.__name__, __bases__, __dict__)

    setattr(
        view_cls,
        "__init__",
        _create_init(
            view_cls,
            __dataclass_fields__,
            __cwtch_view_params__["kw_only"],
            __cwtch_view_params__["validate"],
            __cwtch_view_params__["add_disable_validation_to_init"],
            __cwtch_view_params__["extra"],
            env_prefixes,
            __cwtch_view_params__["env_source"],
        ),
    )

    if __cwtch_view_params__["repr"]:
        __rich_repr__ = _create_rich_repr(view_cls, __dataclass_fields__)
        if __rich_repr__:
            setattr(view_cls, "__rich_repr__", __rich_repr__)
            rich.repr.auto()(view_cls)  # type: ignore
        else:
            __repr__ = _create_repr(view_cls)
            setattr(view_cls, "__repr__", __repr__)

    if __cwtch_view_params__["eq"]:
        setattr(
            view_cls,
            "__eq__",
            _create_eq(view_cls, __dataclass_fields__),
        )

    if getattr(view_cls, "__parameters__", None):
        if not hasattr(view_cls.__class_getitem__, "__cwtch_method__"):
            setattr(view_cls, "__class_getitem__", classmethod(_make_class_getitem(view_cls)))

    __class__ = view_cls  # noqa: F841

    def __getattribute__(self, name: str, /) -> Any:
        result = super().__getattribute__(name)  # type: ignore
        if isinstance(result, Field) and result.name not in object.__getattribute__(self, "__dataclass_fields__"):
            try:
                x = object.__getattribute__(self, "__dict__")
            except KeyError:
                x = object.__getattribute__(self, "__slots__")
            if name not in x:
                raise AttributeError(
                    f"'{object.__getattribute__(self, '__class__').__name__}' object has no attribute '{name}'"
                )
        return result

    setattr(view_cls, "__getattribute__", __getattribute__)

    setattr(view_cls, "__cwtch_model__", True)
    setattr(view_cls, "__cwtch_view_name__", view_name)
    setattr(view_cls, "__cwtch_view__", True)
    setattr(view_cls, "__cwtch_view_base__", cls)
    setattr(view_cls, "__cwtch_view_params__", __cwtch_view_params__)
    setattr(view_cls, "__dataclass_fields__", __dataclass_fields__)

    if "__post_validate__" in cls.__dict__:
        setattr(view_cls, "__post_validate__", cls.__post_validate__)

    def cwtch_rebuild(view_cls, attach: bool | UnsetType = UNSET):
        if not getattr(view_cls, "__cwtch_view__", None):
            raise Exception("not cwtch view")
        return _build_view(
            view_cls.__cwtch_view_base__,
            view_cls,
            name=name,
            attach=attach if attach != UNSET else __cwtch_view_params__.get("attach", UNSET),
            include=include,
            exclude=exclude,
            slots=slots,
            kw_only=kw_only,
            env_prefix=env_prefix,
            env_source=env_source,
            validate=validate,
            add_disable_validation_to_init=add_disable_validation_to_init,
            extra=extra,
            repr=repr,
            eq=eq,
            recursive=recursive,
            rebuild=True,
        )

    setattr(view_cls, "cwtch_rebuild", classmethod(cwtch_rebuild))

    setattr(view_cls, "__cwtch_views__", set())

    if attach or (attach is UNSET and ATTACH):
        if isinstance(attach, (bool, UnsetType)):
            attach_to = cls
        else:
            attach_to = cast(Type, attach)
        setattr(attach_to, view_name, _ViewDesc(view_cls))
        for k in attach_to.__cwtch_views__:
            setattr(view_cls, k, _ViewDesc(getattr(attach_to, k)))
            setattr(getattr(attach_to, k), view_name, _ViewDesc(view_cls))
        attach_to.__cwtch_views__.add(view_name)

    return view_cls


def from_attributes(
    cls: Type,
    obj: Any,
    data: dict | None = None,
    exclude: Sequence | None = None,
    suffix: str | None = None,
    reset_circular_refs: bool | None = None,
) -> Type:
    """Build model from attributes of other object.

    Args:
        cls: The cwtch model class to create.
        obj: Object from which to build.
        data: Additional data to build.
        exclude: List of fields to exclude.
        suffix: Fields suffix.
        reset_circular_refs: Reset circular references to None.

    Returns:
        An instance of the cwtch model class.
    """

    kwds = {
        f.name: getattr(obj, f"{f_name}{suffix}" if suffix else f_name)
        for f_name, f in cls.__dataclass_fields__.items()
        if (not exclude or f_name not in exclude) and hasattr(obj, f"{f.name}{suffix}" if suffix else f_name)
    }
    if data:
        kwds.update(data)
    if exclude:
        kwds = {k: v for k, v in kwds.items() if k not in exclude}

    cache = _get_cache()

    cache["reset_circular_refs"] = reset_circular_refs

    try:
        return cls(__cwtch_cache_key=(cls, id(obj)), **kwds)
    finally:
        del cache["reset_circular_refs"]


def asdict(
    inst: Any,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    exclude_none: bool | None = None,
    exclude_unset: bool | None = None,
    exclude_computed_fields: bool | None = None,
    context: dict | None = None,
) -> dict:
    """Return cwtch model as dict.

    Args:
        inst: cwtch model instance.
        include: List of field names to include.
        exclude: List of field names to exclude.
        exclude_none: If true, fields with None value will be excluded.
        exclude_unset: If true, unset fields will be excluded.
        exclude_computed_fields: If true, computed fields will be excluded.
        context: If specified, must be a mapping.

    Returns:
        A dictionary representation of the cwtch model.
    """

    return _asdict(
        inst,
        include_=include,
        exclude_=exclude,
        exclude_none=exclude_none,
        exclude_unset=exclude_unset,
        exclude_computed_fields=exclude_computed_fields,
        context=context,
    )


def asjson(inst: Any, encoder: Callable[[Any], Any] | None = None, context: dict | None = None) -> str:
    """Dump cwtch model to json.

    Args:
        inst: cwtch model instance.
        encoder: Custom JSON encoder as callable.
        context: If specified, must be a mapping.

    Returns:
        A JSON string representation of the cwtch model.
    """

    return _asjson(inst, encoder, context)


def resolve_types(
    cls: Type,
    globalns: dict | None = None,
    localns: dict | None = None,
    *,
    include_extras: bool = True,
    rebuild: bool = True,
) -> Type:
    """Resolve forward references in a cwtch model.

    This function resolves string annotations and forward references
    in the class's type hints.

    If globalns and localns are not provided, they will be automatically
    extracted from the call frame where the class was defined.

    Args:
        cls: The cwtch model class to update.
        globalns: Global namespace for resolving types. If not provided, extracted from class module.
        localns: Local namespace for resolving types. If not provided, extracted from call frame.
        include_extras: Whether to include extra type information.
        rebuild: Whether to rebuild the class after resolving.

    Returns:
        The updated class with resolved types.
    """
    if globalns is None:
        module = sys.modules.get(cls.__module__, None)
        globalns = vars(module) if module else {}

    if localns is None:
        localns = sys._getframe(1).f_locals

    hints = typing.get_type_hints(cls, globalns=globalns, localns=localns, include_extras=include_extras)

    for f_name, f in cls.__dataclass_fields__.items():
        if f_name in hints:
            f.type = hints[f_name]
        if f_name in cls.__annotations__:
            cls.__annotations__[f_name] = hints[f_name]

    if rebuild:
        cls.cwtch_rebuild()

    return cls


def validate_args(fn: Callable, args: tuple, kwds: dict) -> tuple[tuple, dict]:
    """Helper to convert and validate function arguments.

    Args:
        fn: The function to validate arguments for.
        args: Function positional arguments.
        kwds: Function keyword arguments.

    Returns:
        A tuple of (validated_args, validated_kwds).

    Raises:
        TypeError: If arguments don't match the function's type annotations.
    """

    annotations = {k: v.annotation for k, v in signature(fn).parameters.items()}

    validated_args = []

    for v, (arg_name, T) in zip(args, annotations.items()):
        if T != _empty:
            try:
                validated_args.append(validate_value(v, T))
            except ValidationError as e:
                raise TypeError(f"{fn.__name__}() expects {T} for argument {arg_name}") from e
        else:
            validated_args.append(v)

    validated_kwds = {}

    for arg_name, v in kwds.items():
        T = annotations[arg_name]
        if T != _empty:
            try:
                validated_kwds[arg_name] = validate_value(v, T)
            except ValidationError as e:
                raise TypeError(f"{fn.__name__}() expects {T} for argument {arg_name}") from e
        else:
            validated_kwds[arg_name] = v

    return tuple(validated_args), validated_kwds


def validate_call(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to convert and validate function arguments.

    Args:
        fn: The function to decorate.

    Returns:
        A wrapped function that validates arguments before calling.
    """

    def wrapper(*args, **kwds):
        validated_args, validated_kwds = validate_args(fn, args, kwds)
        return fn(*validated_args, **validated_kwds)

    return wrapper


def computed_field(
    fn: Callable[..., Any] | None = None,
    *,
    asdict_alias: Unset[str] = UNSET,
    repr: Unset[Literal[False]] = UNSET,
    compare: Unset[bool] = UNSET,
) -> Callable[[Callable[..., Any]], property] | property:
    """Decorator to define a computed (read-only) field.

    Computed fields are properties that are derived from other fields
    and are automatically included in asdict() output.

    Args:
        fn: The function to decorate (if used without parentheses).
        asdict_alias: Alternative name for the field in asdict() output.
        repr: Whether to include in repr() output.
        compare: Whether to include in equality comparisons.

    Returns:
        A property decorator with computed field metadata.
    """

    def wrapper(fn):
        if fn.__class__ is not property:
            fn = property(fn)
        if fn.fget.__annotations__.get("return") is None:
            raise Exception
        setattr(
            fn.fget,
            "__cwtch_computed_field_params__",
            {
                "asdict_alias": asdict_alias,
                "repr": repr,
                "compare": compare,
            },
        )
        return fn

    if fn is None:
        return wrapper

    return wrapper(fn)
