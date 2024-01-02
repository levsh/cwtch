from copy import deepcopy
from inspect import _empty, signature
from os import environ
from typing import Any, Callable, Generic, Type, cast

from attr._make import _AndValidator, _CountingAttr
from attrs import NOTHING
from attrs import asdict as attrs_asdict
from attrs import fields_dict as attrs_fields_dict
from attrs import make_class as attrs_make_class

from cwtch.core import (
    Base,
    BaseIgnoreExtra,
    EnvBase,
    EnvBaseIgnoreExtra,
    ViewBase,
    ViewBaseIgnoreExtra,
    _asdict,
    _cache,
    field,
    validate_value,
)
from cwtch.errors import ValidationError

# -------------------------------------------------------------------------------------------------------------------- #


def validate_args(fn: Callable, args: tuple, kwds: dict) -> tuple[tuple, dict]:
    """
    Helper to convert and validate function arguments.

    Args:
      args: function positional arguments.
      kwds: function keyword arguments.
    """

    sig = signature(fn)

    annotations = {k: v.annotation for k, v in sig.parameters.items()}

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


def validate_call(fn):
    """Decorator for validation function args and kwds."""

    def wrapper(*args, **kwds):
        validate_args(fn, args, kwds)
        return fn(*args, **kwds)

    return wrapper


# -------------------------------------------------------------------------------------------------------------------- #


class ViewDesc:
    def __init__(self, view: Type):
        self.view = view

    def __get__(self, obj, owner=None):
        if obj:
            return lambda: self.view(
                **{k: v for k, v in attrs_asdict(obj).items() if k in attrs_fields_dict(self.view)}
            )
        return self.view


# -------------------------------------------------------------------------------------------------------------------- #


_base_cls_map: dict[tuple[bool, bool], Type] = {
    (False, False): Base,
    (False, True): BaseIgnoreExtra,
    (True, False): EnvBase,
    (True, True): EnvBaseIgnoreExtra,
}

_view_base_cls_map: dict[tuple[bool, bool], Type] = {
    (False, False): ViewBase,
    (False, True): ViewBaseIgnoreExtra,
}


def default_env_source() -> dict:
    return cast(dict, environ)


def define(
    cls=None,
    *,
    env_prefix: str | list[str] | None = None,
    env_source: Callable[[], dict] | None = None,
    ignore_extra: bool | None = None,
    **kwds,
) -> Type | Callable[[Type], Type]:
    """
    Args:
      env_prefix: prefix(or list of prefixes) for environment variables.
      env_source: environment variables source factory.
      ignore_extra: ignore extra arguments passed to init.
    """

    kwds["kw_only"] = True
    kwds["init"] = False

    env_source = env_source or default_env_source

    def wrapper(cls):
        cls_annotations = cls.__annotations__
        cls_module = cls.__module__

        attrs = {k: v for k, v in cls.__dict__.items() if isinstance(v, _CountingAttr)}
        for attr_name, attr_type in cls_annotations.items():
            if attr_name in attrs:
                if (v := attrs[attr_name]).type is None:
                    v.type = attr_type
            else:
                if hasattr(cls, attr_name):
                    attrs[attr_name] = field(validate=True, type=attr_type, default=getattr(cls, attr_name))
                else:
                    attrs[attr_name] = field(validate=True, type=attr_type, default=NOTHING)

        views_attrs = {}
        views = {}

        for item in cls.__mro__[::-1]:
            for attr_name, attr_type in getattr(item, "__annotations__", {}).items():
                attr = getattr(item, attr_name, NOTHING)
                if isinstance(attr, (_CountingAttr, _CountingAttrProxy)):
                    views_attrs[attr_name] = attr
                else:
                    views_attrs[attr_name] = field(validate=True, type=attr_type, default=attr)
            for attr_name, attr in item.__dict__.items():
                if hasattr(attr, "__cwtch_view_params__"):
                    views[attr_name] = attr

        for attr_name, attr in cls.__dict__.items():
            if hasattr(attr, "__cwtch_view_params__"):
                views[attr_name] = attr
        views = list(views.values())

        def _deepcopy(attrs):
            types = {k: v.type for k, v in attrs.items()}
            for v in attrs.values():
                v.type = None
            copied_attrs = deepcopy(attrs)
            for k, v in attrs.items():
                v.type = types[k]
            for k, v in copied_attrs.items():
                v.type = types[k]
            return copied_attrs

        cls_attrs = _deepcopy(attrs)

        for attr_name, attr in cls_attrs.items():
            attr.type = cls_annotations.get(attr_name, attr.type)
            if isinstance(attr._validator, _AndValidator):
                attr._validator._validators = tuple(
                    v for v in attr._validator._validators if not hasattr(v, "__cwtch_view__")
                )

        base = _base_cls_map[(bool(env_prefix), bool(ignore_extra))]

        if issubclass(cls, base):
            bases = (cls,)
        else:
            bases = (base, cls)
        if getattr(cls, "__parameters__", None):
            bases = bases + (Generic[*cls.__parameters__],)  # # type: ignore

        cls = attrs_make_class(f"{cls.__name__}", cls_attrs, bases=bases, **kwds)

        if env_prefix and not isinstance(env_prefix, list):
            env_prefixes = [env_prefix]
        else:
            env_prefixes = env_prefix

        cls.__annotations__ = cls_annotations
        cls.__module__ = cls_module
        cls.__cwtch_model__ = True  # type: ignore
        if env_prefixes:
            cls.__cwtch_env_prefixes__ = env_prefixes  # type: ignore
            cls.__cwtch_env_source__ = staticmethod(env_source)  # type: ignore

        for view in views:
            view_name = view.__name__
            view_params = view.__cwtch_view_params__
            include = view_params["include"] or views_attrs
            exclude = view_params["exclude"] or set()
            validate = view_params["validate"]
            view_ignore_extra = view_params["ignore_extra"]
            if view_ignore_extra is None:
                view_ignore_extra = ignore_extra
            recursive = view_params["recursive"]

            view_attrs = {
                k: v
                for k, v in {
                    **_deepcopy(views_attrs),
                    **{k: v for k, v in view.__dict__.items() if isinstance(v, _CountingAttr)},
                }.items()
                if (k in include and k not in exclude)
            }

            for attr_name, attr_type in view.__annotations__.items():
                if hasattr(view, attr_name):
                    attr = getattr(view, attr_name)
                    if attr.__class__ in (_CountingAttr, _CountingAttrProxy):
                        continue
                    view_attrs[attr_name] = field(validate=True, type=attr_type, default=attr)
                else:
                    view_attrs[attr_name] = field(validate=True, type=attr_type, default=NOTHING)

            view_annotations = {k: v for k, v in {**cls_annotations, **view.__annotations__}.items() if k in view_attrs}

            for attr_name, attr in view_attrs.items():
                if validate is False:
                    attr._validator = attr.metadata.get("validator")
                attr.type = view_annotations.get(attr_name, attr.type)
                if isinstance(attr._validator, _AndValidator):
                    attr._validator._validators = tuple(
                        v
                        for v in attr._validator._validators
                        if (__cwtch_view__ := getattr(v, "__cwtch_view__", None)) is None or __cwtch_view__ == view
                    )

            if recursive:

                def update_type(tp):
                    if (origin := getattr(tp, "__origin__", None)) is not None:
                        return tp.__class__(
                            update_type(origin),
                            tp.__metadata__
                            if hasattr(tp, "__metadata__")
                            else tuple(update_type(arg) for arg in tp.__args__),
                        )
                    elif getattr(tp, "__cwtch_model__", None):
                        if hasattr(tp, view_name):
                            return getattr(tp, view_name)
                    return tp

                for k, v in view_attrs.items():
                    view_annotations[k] = v.type = update_type(v.type)

            view_base = _view_base_cls_map[(bool(env_prefix), bool(view_ignore_extra))]

            view_kwds = kwds.copy()
            view_kwds["init"] = False

            view_cls = attrs_make_class(
                f"{cls.__name__}{view_name}",
                view_attrs,
                bases=(view_base,),
                **view_kwds,
            )

            view_cls.__annotations__ = view_annotations
            view_cls.__module__ = cls_module
            view_cls.__cwtch_view__ = True  # type: ignore
            view_cls.__cwtch_view_base__ = cls  # type: ignore
            view_cls.__cwtch_view_name__ = view.__name__  # type: ignore

            setattr(cls, view.__name__, ViewDesc(view_cls))

        return cls

    if cls is None:
        return wrapper

    return wrapper(cls)


# -------------------------------------------------------------------------------------------------------------------- #


class _CountingAttrProxy:
    def __init__(self, view_cls: Type, counting_attr: _CountingAttr):
        self._view_cls = view_cls
        self._counting_attr = counting_attr

    def validator(self, fn: Callable):
        fn.__cwtch_view__ = self._view_cls
        return self._counting_attr.validator(fn)


def view(
    cls=None,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    validate: bool | None = None,
    ignore_extra: bool | None = None,
    recursive: bool | None = None,
    lc: dict[str, Any] | None = None,
):
    """
    Decorator for creating view of root Cwtch model.

    Args:
      include: set of field names to include from root model.
      exclude: set of field names to exclude from root model.
      validate: if False skip validation(default True).
      ignore_extra: ignore extra arguments passed to init.
      recursive: ...
      lc: Python frame locals.
    """

    if (include or set()) & (exclude or set()):
        raise ValueError("same field in include and exclude are not allowed")

    def wrapper(cls):
        if set(cls.__dict__) & (exclude or set()):
            raise ValueError("defined fields conflict with exclude parameter")

        cls.__cwtch_view_params__ = {
            "include": include,
            "exclude": exclude,
            "validate": validate,
            "ignore_extra": ignore_extra,
            "recursive": recursive,
        }

        if lc:
            include_ = include or lc.keys()
            attrs = {
                k: v
                for k, v in lc.items()
                if k not in cls.__dict__
                and isinstance(v, _CountingAttr)
                and k in include_
                and k not in (exclude or set())
            }
            for k, v in attrs.items():
                setattr(cls, k, _CountingAttrProxy(cls, v))
            cls.__annotations__ = {
                **{k: v for k, v in lc["__annotations__"].items() if k in attrs},
                **cls.__annotations__,
            }

        return cls

    if cls is None:
        return wrapper

    return wrapper(cls)


def from_attributes(
    cls,
    obj,
    data: dict | None = None,
    exclude: list | None = None,
    suffix: str | None = None,
    reset_circular_refs: bool | None = None,
):
    """
    Build model from attributes of other object.

    Args:
      obj: object from which to build.
      data: additional data to build.
      exclude: list of field to exclude.
      suffix: fields suffix.
      reset_circular_refs: reset circular references to None.
    """

    kwds = {
        k: getattr(obj, f"{k}{suffix}" if suffix else k)
        for k in {a.name for a in cls.__attrs_attrs__}
        if (not exclude or k not in exclude) and hasattr(obj, f"{k}{suffix}" if suffix else k)
    }
    if data:
        kwds.update(data)
    if exclude:
        kwds = {k: v for k, v in kwds.items() if k not in exclude}

    cache = _cache.get()
    cache["reset_circular_refs"] = reset_circular_refs
    try:
        return cls(_cwtch_cache_key=(cls, id(obj)), **kwds)
    finally:
        del cache["reset_circular_refs"]


# -------------------------------------------------------------------------------------------------------------------- #


def asdict(
    inst,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    exclude_unset: bool | None = None,
) -> dict:
    return _asdict(inst, include_=include, exclude_=exclude, exclude_unset=exclude_unset)
