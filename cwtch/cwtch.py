import dataclasses
import json
import typing
from copy import deepcopy
from dataclasses import _MISSING_TYPE, MISSING, Field
from inspect import _empty, currentframe, signature
from os import environ
from types import MappingProxyType, UnionType
from typing import Callable, Type, Union, cast

from cwtch.core import _asdict, _cache, _class_getitem, get_validator, validate_value, validate_value_using_validator
from cwtch.errors import ValidationError

# -------------------------------------------------------------------------------------------------------------------- #


def validate_args(fn: Callable, args: tuple, kwds: dict) -> tuple[tuple, dict]:
    """
    Helper to convert and validate function arguments.

    Args:
      args: function positional arguments.
      kwds: function keyword arguments.
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


def validate_call(fn):
    """Decorator to convert and validate function arguments."""

    def wrapper(*args, **kwds):
        validate_args(fn, args, kwds)
        return fn(*args, **kwds)

    return wrapper


# -------------------------------------------------------------------------------------------------------------------- #


class ViewDesc:
    def __init__(self, view: Type):
        self.view = view

    def __get__(self, obj, owner=None):
        view = self.view
        if obj:
            return lambda: view(**{k: v for k, v in _asdict(obj, True).items() if k in view.__dataclass_fields__})
        return view


# -------------------------------------------------------------------------------------------------------------------- #


def default_env_source() -> dict:
    return cast(dict, environ)


def _build(
    cls,
    env_prefixes: list[str] | None,
    env_source: Callable | None,
    validate: bool,
    ignore_extra: bool,
    handle_circular_refs: bool,
    **kwds,
):
    if kwds.get("kw_only") is False:
        raise Exception("only keyword arguments are supported")

    kwds["kw_only"] = True

    def create_fn(cls, name, args, body, *, globals=None, locals=None):
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
        text = f"def __create_fn__({local_vars}):\n{text}\n    return {name}"
        ns = {}

        exec(text, globals, ns)

        return ns["__create_fn__"](**locals)

    def create_init(cls, fields, validate, ignore_extra):
        __dataclass_init__ = cls.__dict__.get("__dataclass_init__", cls.__init__)

        sorted_fields = sorted(
            fields.keys(),
            key=lambda name: not (fields[name].default is MISSING and fields[name].default_factory is MISSING),
        )

        super_fields = {}
        if cls.__base__ != object:
            for item in cls.__mro__[1::-1][:-1]:
                for f_name, f_type in getattr(item, "__annotations__", {}).items():
                    if f_name not in cls.__annotations__:
                        super_fields[f_name] = f_type

        globals = {}
        locals = {
            "dataclasses_fields": dataclasses.fields,
            "_cache_get": _cache.get,
            "MISSING": MISSING,
            "ValidationError": ValidationError,
            "validate": validate_value_using_validator,
            "env_prefixes": env_prefixes,
            "env_source": env_source,
            "json_loads": json.loads,
            "JSONDecodeError": json.JSONDecodeError,
            "__dataclass_init__": __dataclass_init__,
        }

        args = ["__cwtch_self__"]
        if handle_circular_refs:
            args.append("_cwtch_cache_key=None")

        if super_fields or fields:
            args += ["*"]

        body = []

        body += [
            "if hasattr(__cwtch_self__, '__cwtch_in_post_init__'):",
        ]
        if __dataclass_init__:
            x = ", ".join(f"{f_name}={f_name}" for f_name in fields)
            body += [f"    __dataclass_init__(__cwtch_self__, {x})"]
        body += [f"    return"]

        if env_prefixes:
            body += [
                "env_source_data = env_source()",
                "env_data = {}",
                "for f in dataclasses_fields(__cwtch_self__):",
                "   if env_var := f.metadata['cwtch'].get('env_var'):",
                "       for env_prefix in env_prefixes:",
                "           if isinstance(env_var, str):",
                "               key = env_var",
                "           else:",
                "               key = f'{env_prefix}{f.name}'.upper()",
                "           if key in env_source_data:",
                "               try:",
                "                   env_data[f.name] = json_loads(env_source_data[key])",
                "               except JSONDecodeError:",
                "                   env_data[f.name] = env_source_data[key]",
                "               break",
            ]

        if fields:
            indent = ""
            if handle_circular_refs:
                body += [
                    "if _cwtch_cache_key is not None:",
                    "   _cache_get()[_cwtch_cache_key] = __cwtch_self__",
                    "try:",
                ]
                indent = " " * 4

            for f_name in sorted_fields:
                field = fields[f_name]
                locals[f"field_{f_name}"] = field
                locals[f"type_{f_name}"] = field.type
                metadata = field.metadata.get("cwtch", {})
                if field.default is not MISSING:
                    locals[f"default_{f_name}"] = field.default
                    args.append(f"{f_name}: type_{f_name} = default_{f_name}")
                    if metadata.get("validate", validate):
                        locals[f"validator_{f_name}"] = get_validator(field.type)
                        body += [f"{indent}try:"]
                        if env_prefixes:
                            body += [
                                (
                                    f"    {indent}{f_name} = "
                                    f"validate(env_data.get('{f_name}', {f_name}), type_{f_name}, validator_{f_name})"
                                )
                            ]
                        else:
                            body += [
                                f"    {indent}{f_name} = validate({f_name}, type_{f_name}, validator_{f_name})",
                            ]
                        body += [
                            f"{indent}except (TypeError, ValueError, ValidationError) as e:",
                            f"    {indent}raise ValidationError({f_name}, __class__, [e], path=[field_{f_name}.name])",
                        ]
                    elif env_prefixes:
                        body += [f"{indent}{f_name} = env_data.get('{f_name}', {f_name})"]
                    else:
                        body += [f"{indent}pass"]
                elif field.default_factory is not MISSING:
                    locals[f"default_factory_{f_name}"] = field.default_factory
                    args.append(f"{f_name}: type_{f_name} = MISSING")
                    if metadata.get("validate", validate):
                        locals[f"validator_{f_name}"] = get_validator(field.type)
                        body += [f"{indent}try:"]
                        if env_prefixes:
                            body += [
                                f"    {indent}if {f_name} is MISSING:",
                                f"        {indent}if '{f_name}' in env_data:",
                                f"            {indent}{f_name} = env_data['{f_name}']",
                                f"        {indent}else:",
                                f"            {indent}{f_name} = default_factory_{f_name}()",
                            ]
                        else:
                            body += [
                                f"    {indent}if {f_name} is MISSING:",
                                f"        {indent}{f_name} = default_factory_{f_name}()",
                            ]
                        body += [
                            f"    {indent}{f_name} = validate({f_name}, type_{f_name}, validator_{f_name})",
                            f"{indent}except (TypeError, ValueError, ValidationError) as e:",
                            f"    {indent}raise ValidationError({f_name}, __class__, [e], path=[field_{f_name}.name])",
                        ]
                    elif env_prefixes:
                        body += [f"{indent}{f_name} = env_data.get('{f_name}', {f_name})"]
                    else:
                        body += [f"{indent}pass"]
                else:
                    args.append(f"{f_name}: type_{f_name}")
                    if metadata.get("validate", validate):
                        locals[f"validator_{f_name}"] = get_validator(field.type)
                        body += [f"{indent}try:"]
                        if env_prefixes:
                            body += [
                                (
                                    f"    {indent}{f_name} = "
                                    f"validate(env_data.get('{f_name}', {f_name}), type_{f_name}, validator_{f_name})"
                                )
                            ]
                        else:
                            body += [
                                f"    {indent}{f_name} = validate({f_name}, type_{f_name}, validator_{f_name})",
                            ]
                        body += [
                            f"{indent}except (TypeError, ValueError, ValidationError) as e:",
                            f"    {indent}raise ValidationError({f_name}, __class__, [e], path=[field_{f_name}.name])",
                        ]
                    elif env_prefixes:
                        body += [f"{indent}{f_name} = env_data.get('{f_name}', {f_name})"]
                    else:
                        body += [f"{indent}pass"]

            if handle_circular_refs:
                body += [
                    "finally:",
                    "    _cache_get().pop(_cwtch_cache_key, None)",
                ]

            if __dataclass_init__:
                x = ", ".join(f"{f_name}={f_name}" for f_name in fields)
                body += [f"__dataclass_init__(__cwtch_self__, {x})"]

        else:
            body = ["pass"]

        if ignore_extra is True:
            args += ["**__cwtch_kwds__"]

        setattr(cls, "__dataclass_init__", __dataclass_init__)

        __init__ = create_fn(cls, "__init__", args, body, globals=globals, locals=locals)

        __init__.__module__ = __dataclass_init__.__module__
        __init__.__qualname__ = __dataclass_init__.__qualname__

        return __init__

    cls = dataclasses.dataclass(**kwds)(cls)

    fields = {f.name: f for f in dataclasses.fields(cls) if f.init is True}

    setattr(cls, "__init__", create_init(cls, fields, validate, ignore_extra))

    __class__ = cls

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)  # type: ignore
        return _class_getitem(cls, parameters, result)

    setattr(cls, "__class_getitem__", classmethod(__class_getitem__))

    if hasattr(cls, "__post_init__"):
        __dataclass_post_init__ = cls.__post_init__

        def __post_init__(self):
            self.__cwtch_in_post_init__ = True
            try:
                __dataclass_post_init__(self)
            except ValueError as e:
                raise ValidationError(self, __class__, [e], path=["__post_init__"])
            finally:
                if hasattr(cls, "__cwtch_in_post_init__"):
                    delattr(self, "__cwtch_in_post_init__")

        __post_init__.__module__ = __dataclass_post_init__.__module__
        __post_init__.__qualname__ = __dataclass_post_init__.__qualname__

        setattr(cls, "__post_init__", __post_init__)

    def update_forward_refs(localns, globalns):
        resolve_types(cls, globalns=globalns, localns=localns)
        _build(cls, env_prefixes, env_source, validate, ignore_extra, handle_circular_refs, **kwds)

    setattr(cls, "update_forward_refs", staticmethod(update_forward_refs))

    def cwtch_rebuild():
        _build(cls, env_prefixes, env_source, validate, ignore_extra, handle_circular_refs, **kwds)

    setattr(cls, "cwtch_rebuild", staticmethod(cwtch_rebuild))

    setattr(cls, "__cwtch_model__", True)
    setattr(cls, "__cwtch_handle_circular_refs__", handle_circular_refs)

    # views

    fields = dataclasses.fields(cls)

    def update_type(tp):
        if getattr(tp, "__origin__", None) is not None:
            return tp.__class__(
                update_type(getattr(tp, "__origin__", tp)),
                tp.__metadata__ if hasattr(tp, "__metadata__") else tuple(update_type(arg) for arg in tp.__args__),
            )
        if isinstance(tp, UnionType):
            return Union[*(update_type(arg) for arg in tp.__args__)]
        if getattr(tp, "__cwtch_model__", None):
            if hasattr(tp, view_name):
                return getattr(tp, view_name)
        return tp

    namespace = {}

    for item in cls.__mro__[1::-1]:
        for k, v in item.__dict__.items():
            if k.startswith("__") and k.endswith("__"):
                continue
            if v == cls or hasattr(v, "__cwtch_view_params__"):
                continue
            namespace[k] = v

    for view_cls in (v for v in cls.__dict__.values() if hasattr(v, "__cwtch_view_params__")):
        view_name = view_cls.__name__
        view_params = view_cls.__cwtch_view_params__
        include = view_params["include"] or set(field.name for field in fields)
        exclude = view_params["exclude"] or set()
        view_validate = view_params["validate"]
        if view_validate is None:
            view_validate = validate
        view_ignore_extra = view_params["ignore_extra"]
        if view_ignore_extra is None:
            view_ignore_extra = ignore_extra
        recursive = view_params["recursive"]

        for f in fields:
            if f.metadata is not None:
                f.metadata = dict(f.metadata)  # type: ignore
        try:
            view_fields = {
                k: v
                for k, v in {
                    **{f.name: f for f in deepcopy(fields)},
                    **{k: v for k, v in view_cls.__dict__.items() if isinstance(v, Field)},
                }.items()
                if (k in include and k not in exclude)
            }
            for f in view_fields.values():
                if isinstance(f.default, _MISSING_TYPE):
                    f.default = MISSING
                if isinstance(f.default_factory, _MISSING_TYPE):
                    f.default_factory = MISSING
        finally:
            for f in fields:
                if f.metadata is not None:
                    f.metadata = MappingProxyType(f.metadata)

        for f_name, f_type in view_cls.__annotations__.items():
            if hasattr(view_cls, f_name):
                f = getattr(view_cls, f_name)
                if not isinstance(f, Field):
                    f = dataclasses.field(default=f)
                f.name = f_name
                f.type = f_type
                view_fields[f_name] = f
            else:
                f = dataclasses.field(default=MISSING)
                f.name = f_name
                f.type = f_type
                view_fields[f_name] = f

        view_annotations = {
            k: v for k, v in {**cls.__annotations__, **view_cls.__annotations__}.items() if k in view_fields
        }

        view_namespace = {
            k: v
            for k, v in namespace.items()
            if k not in exclude and k not in view_fields and k not in {"cwtch_rebuild", "update_forward_refs"}
        }

        if recursive is not False:
            for k, v in view_fields.items():
                view_annotations[k] = v.type = update_type(v.type)
                if v.default_factory:
                    v.default_factory = update_type(v.default_factory)

        view_kwds = {"init": True, "kw_only": True}

        view_cls = dataclasses.make_dataclass(
            f"{cls.__name__}{view_name}",
            [(f.name, f.type, f) for f in view_fields.values()],
            namespace=view_namespace,
            **view_kwds,  # type: ignore
        )

        setattr(view_cls, "__init__", create_init(view_cls, view_fields, view_validate, view_ignore_extra))

        view_cls.__annotations__ = view_annotations
        view_cls.__module__ = cls.__module__
        view_cls.__cwtch_view__ = True  # type: ignore
        view_cls.__cwtch_view_base__ = cls  # type: ignore
        view_cls.__cwtch_view_name__ = view_name  # type: ignore

        setattr(cls, view_name, ViewDesc(view_cls))

    return cls


def dataclass(
    cls=None,
    *,
    env_prefix: str | list[str] | None = None,
    env_source: Callable[[], dict] | None = None,
    validate: bool = True,
    ignore_extra: bool = True,
    handle_circular_refs: bool = False,
    **kwds,
) -> Type | Callable[[Type], Type]:
    """
    Args:
      env_prefix: prefix(or list of prefixes) for environment variables.
      env_source: environment variables source factory.
      ignore_extra: ignore extra arguments passed to init(default False).
    """

    def wrapper(cls):
        env_prefixes = None
        if env_prefix and not isinstance(env_prefix, list):
            env_prefixes = [env_prefix]
        else:
            env_prefixes = env_prefix
        cls = _build(
            cls,
            env_prefixes,
            env_source or default_env_source,
            validate,
            ignore_extra,
            handle_circular_refs,
            **kwds,
        )

        return cls

    if cls is None:
        return wrapper

    return wrapper(cls)


# -------------------------------------------------------------------------------------------------------------------- #


def view(
    cls=None,
    *,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    validate: bool | None = None,
    ignore_extra: bool | None = None,
    recursive: bool | None = None,
):
    """
    Decorator for creating view of root Cwtch model.

    Args:
      include: set of field names to include from root model.
      exclude: set of field names to exclude from root model.
      validate: if False skip validation(default True).
      ignore_extra: ignore extra arguments passed to init(default False).
      recursive: ...
    """

    if (include or set()) & (exclude or set()):
        raise ValueError("same field in include and exclude are not allowed")

    root_cls_locals = currentframe().f_back.f_locals
    # root_cls_annotations = root_cls_locals["__annotations__"]

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
        f.name: getattr(obj, f"{f.name}{suffix}" if suffix else f.name)
        for f in dataclasses.fields(cls)
        if (not exclude or f.name not in exclude) and hasattr(obj, f"{f.name}{suffix}" if suffix else f.name)
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
    show_secrets: bool | None = None,
) -> dict:
    return _asdict(
        inst,
        True,
        include_=include,
        exclude_=exclude,
        exclude_unset=exclude_unset,
        show_secrets=show_secrets,
    )


# -------------------------------------------------------------------------------------------------------------------- #


def resolve_types(cls, rebuild: bool = True, globalns=None, localns=None, include_extras: bool = True):
    kwds = {"globalns": globalns, "localns": localns, "include_extras": include_extras}

    hints = typing.get_type_hints(cls, **kwds)
    for field in dataclasses.fields(cls):
        if field.name in hints:
            field.type = hints[field.name]
        if field.name in cls.__annotations__:
            cls.__annotations__[field.name] = hints[field.name]

    if rebuild:
        cls.cwtch_rebuild()

    return cls
