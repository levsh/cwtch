import dataclasses
import functools
import json
import os
import typing
from dataclasses import MISSING, Field, _is_classvar
from dataclasses import fields as dataclasses_fields
from dataclasses import is_dataclass, make_dataclass
from inspect import _empty, signature
from types import UnionType
from typing import Callable, Generic, Type, TypeVar, Union, cast

from cwtch.core import _asdict, _cache, _class_getitem, _validate_value_using_validator, get_validator, validate_value
from cwtch.errors import ValidationError
from cwtch.types import UNSET, Unset

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
    return cast(dict, os.environ)


# -------------------------------------------------------------------------------------------------------------------- #


def instantiate_generic_dataclass(tp):
    if (
        (origin := getattr(tp, "__origin__", None))
        and is_dataclass(origin)
        and getattr(origin, "__parameters__", None)
        and (args := getattr(tp, "__args__", None))
    ):
        return _make_generic_dataclass(origin, args)
    raise TypeError("must be called with a subscripted dataclass type")


# -------------------------------------------------------------------------------------------------------------------- #


@functools.cache
def _make_generic_dataclass(origin, args):
    x = ", ".join(map(lambda x: x.strip("'"), (arg.__name__ for arg in args)))
    return dataclass(
        make_dataclass(
            f"{origin.__name__}[{x}]",
            [],
            bases=(origin[*args],),
            namespace=origin.__dict__,
        ),
        force_substitute=True,
        **origin.__cwtch_params__,
    )


def _get_parameters(args):
    return (
        _make_generic_dataclass(origin, arg.__args__)
        if (
            (origin := getattr(arg, "__origin__", None))
            and is_dataclass(origin)
            and getattr(origin, "__parameters__", None)
            and getattr(arg, "__args__", None)
        )
        else arg
        for arg in args
    )


def _build(
    cls,
    env_prefixes: list[str] | None,
    env_source: Callable | None,
    validate: bool,
    ignore_extra: bool,
    handle_circular_refs: bool,
    rebuild: bool = False,
    force_substitute: bool = False,
    **kwds,
):
    if kwds.get("kw_only") is False:
        raise Exception("only keyword arguments are supported")

    kwds["kw_only"] = True

    if not rebuild:
        cls = dataclasses.dataclass(**kwds)(cls)

    def copy_field(f) -> Field:
        new_f = Field(f.default, f.default_factory, f.init, f.repr, f.hash, f.compare, f.metadata, f.kw_only)
        new_f.name = f.name
        new_f.type = f.type
        new_f._field_type = f._field_type  # type: ignore
        return new_f

    def get_parameters_map(cls) -> dict | None:
        if (
            (origin := getattr(cls, "__origin__", None))
            and (parameters := getattr(origin, "__parameters__", None))
            and (args := getattr(cls, "__args__", None))
        ):
            return dict(zip(parameters, _get_parameters(args)))

    def get_fields_substitution(cls, view_cls=None) -> dict:
        field_subst = {"type": {}, "default": {}, "default_factory": {}}
        items = getattr(cls, "__orig_bases__", ())[::-1]
        if force_substitute:
            items += (cls,)
        for item in items:
            origin = getattr(item, "__origin__", None)
            if not is_dataclass(origin):
                continue
            parameters_map = get_parameters_map(item)
            if not parameters_map:
                continue
            for f in dataclasses.fields(view_cls or origin):
                for k in ("type", "default", "default_factory"):
                    k_v = getattr(f, k)
                    if hasattr(k_v, "__typing_subst__"):
                        field_subst[k][f.name] = k_v.__typing_subst__(parameters_map[k_v])
                    elif getattr(k_v, "__parameters__", None):
                        field_subst[k][f.name] = k_v[*[parameters_map[tp] for tp in f.type.__parameters__]]
        return field_subst

    field_subst = get_fields_substitution(cls)

    for f in dataclasses_fields(cls):
        f_name = f.name
        if f_name in cls.__annotations__:
            continue
        new_f = None
        for k in ("type", "default", "default_factory"):
            subst = field_subst[k]
            if f_name not in subst:
                continue
            if getattr(f, k) != subst[f_name]:
                new_f = new_f or copy_field(f)
                setattr(new_f, k, subst[f_name])
        if new_f:
            cls.__dataclass_fields__[f_name] = new_f

    fields = {f.name: f for f in dataclasses_fields(cls) if f.init is True}

    if env_prefixes is not None:
        for f in fields.values():
            if (
                f.metadata.get("cwtch", {}).get("env_var", True)
                and f.default == MISSING
                and f.default_factory == MISSING
            ):
                raise TypeError(f"environment field[{f.name}] should has default or default_factory value")

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
            for item in cls.__mro__[::-1][1:]:
                for f_name, f_type in getattr(item, "__annotations__", {}).items():
                    if f_name not in cls.__annotations__:
                        super_fields[f_name] = f_type

        globals = {}
        locals = {
            "__MISSING": MISSING,
            "__dataclasses_fields": dataclasses.fields,
            "__cache_get": _cache.get,
            "__validate": _validate_value_using_validator,
            "__env_prefixes": env_prefixes,
            "__env_source": env_source,
            "__json_loads": json.loads,
            "__builtins_id": id,
            "__dataclass_init__": __dataclass_init__,
            "__ValidationError": ValidationError,
            "__JSONDecodeError": json.JSONDecodeError,
        }

        args = ["__cwtch_self__"]
        if handle_circular_refs:
            args.append("_cwtch_cache_key=None")

        if super_fields or fields:
            args += ["*"]

        body = [
            "if __cache_get().get(f'{__builtins_id(__cwtch_self__)}post_init'):",
        ]
        if __dataclass_init__:
            x = ", ".join(f"{f_name}={f_name}" for f_name in fields)
            body += [f"    __dataclass_init__(__cwtch_self__, {x})"]
        body += [
            f"    return",
        ]

        if env_prefixes is not None:
            body += [
                "env_source_data = __env_source()",
                "env_data = {}",
                "for f in __dataclasses_fields(__cwtch_self__):",
                "   metadata = f.metadata.get('cwtch', {})",
                "   if env_var := metadata.get('env_var', True):",
                "       for env_prefix in __env_prefixes:",
                "           if isinstance(env_var, str):",
                "               key = env_var",
                "           else:",
                "               key = f'{env_prefix}{f.name}'.upper()",
                "           if key in env_source_data:",
                "               try:",
                "                   env_data[f.name] = __json_loads(env_source_data[key])",
                "               except __JSONDecodeError:",
                "                   env_data[f.name] = env_source_data[key]",
                "               break",
            ]

        if fields:
            indent = ""
            if handle_circular_refs:
                body += [
                    "if _cwtch_cache_key is not None:",
                    "   __cache_get()[_cwtch_cache_key] = __cwtch_self__",
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
                        if env_prefixes is not None:
                            body += [
                                (
                                    f"    {indent}{f_name} = "
                                    f"__validate(env_data.get('{f_name}', {f_name}), type_{f_name}, validator_{f_name})"
                                )
                            ]
                        else:
                            body += [
                                f"    {indent}{f_name} = __validate({f_name}, type_{f_name}, validator_{f_name})",
                            ]
                        body += [
                            f"{indent}except (TypeError, ValueError, __ValidationError) as e:",
                            f"    {indent}raise __ValidationError({f_name}, __class__, [e], path=[field_{f_name}.name])",
                        ]
                    elif env_prefixes is not None:
                        body += [f"{indent}{f_name} = env_data.get('{f_name}', {f_name})"]
                    else:
                        body += [f"{indent}pass"]
                elif field.default_factory is not MISSING:
                    locals[f"default_factory_{f_name}"] = field.default_factory
                    args.append(f"{f_name}: type_{f_name} = __MISSING")
                    if metadata.get("validate", validate):
                        locals[f"validator_{f_name}"] = get_validator(field.type)
                        body += [f"{indent}try:"]
                        if env_prefixes is not None:
                            body += [
                                f"    {indent}if {f_name} is __MISSING:",
                                f"        {indent}if '{f_name}' in env_data:",
                                f"            {indent}{f_name} = env_data['{f_name}']",
                                f"        {indent}else:",
                                f"            {indent}{f_name} = default_factory_{f_name}()",
                            ]
                        else:
                            body += [
                                f"    {indent}if {f_name} is __MISSING:",
                                f"        {indent}{f_name} = default_factory_{f_name}()",
                            ]
                        body += [
                            f"    {indent}{f_name} = __validate({f_name}, type_{f_name}, validator_{f_name})",
                            f"{indent}except (TypeError, ValueError, __ValidationError) as e:",
                            f"    {indent}raise __ValidationError({f_name}, __class__, [e], path=[field_{f_name}.name])",
                        ]
                    elif env_prefixes is not None:
                        body += [f"{indent}{f_name} = env_data.get('{f_name}', {f_name})"]
                    else:
                        body += [f"{indent}pass"]
                else:
                    args.append(f"{f_name}: type_{f_name} = __MISSING")
                    if metadata.get("validate", validate):
                        locals[f"validator_{f_name}"] = get_validator(field.type)
                        body += [f"{indent}try:"]
                        body += [
                            f"{indent}    if {f_name} == __MISSING:",
                            (
                                f'{indent}        raise TypeError(f"{{__class__.__qualname__}}.__init__()'
                                f" missing required keyword-only argument: '{f_name}'\")"
                            ),
                        ]
                        if env_prefixes is not None:
                            body += [
                                (
                                    f"    {indent}{f_name} = "
                                    f"__validate(env_data.get('{f_name}', {f_name}), type_{f_name}, validator_{f_name})"
                                )
                            ]
                        else:
                            body += [
                                f"    {indent}{f_name} = __validate({f_name}, type_{f_name}, validator_{f_name})",
                            ]
                        body += [
                            f"{indent}except (TypeError, ValueError, __ValidationError) as e:",
                            f"    {indent}raise __ValidationError({f_name}, __class__, [e], path=[field_{f_name}.name])",
                        ]
                    elif env_prefixes is not None:
                        body += [f"{indent}{f_name} = env_data.get('{f_name}', {f_name})"]
                    else:
                        body += [f"{indent}pass"]

            if handle_circular_refs:
                body += [
                    "finally:",
                    "    __cache_get().pop(_cwtch_cache_key, None)",
                ]

            if __dataclass_init__:
                x = ", ".join(f"{f_name}={f_name}" for f_name in fields)
                body += ["try:"]
                if ignore_extra:
                    body += [f"    __dataclass_init__(__cwtch_self__, {x})"]
                else:
                    body += [f"    __dataclass_init__(__cwtch_self__, {x}, **__cwtch_kwds__)"]
                body += [
                    f"except TypeError as e:",
                    f"    value = {{}}",
                ]
                for f_name in fields:
                    body += [f"    value['{f_name}'] = {f_name}"]
                body += [
                    f"    raise __ValidationError(value, __class__, [e], path=[f'{{__class__.__name__}}.__init__'])"
                ]

        else:
            body = ["pass"]

        args += ["**__cwtch_kwds__"]

        setattr(cls, "__dataclass_init__", __dataclass_init__)

        __init__ = create_fn(cls, "__init__", args, body, globals=globals, locals=locals)

        __init__.__module__ = __dataclass_init__.__module__
        __init__.__qualname__ = __dataclass_init__.__qualname__

        return __init__

    setattr(cls, "__init__", create_init(cls, fields, validate, ignore_extra))

    def make_class_getitem(cls):
        __class__ = cls
        class_getitem = _class_getitem

        def __class_getitem__(cls, parameters):
            result = super().__class_getitem__(parameters)  # type: ignore
            return class_getitem(cls, parameters, result)

        return __class_getitem__

    setattr(cls, "__class_getitem__", classmethod(make_class_getitem(cls)))

    if hasattr(cls, "__post_init__"):
        __dataclass_post_init__ = cls.__post_init__

        def __post_init__(self):
            cache = _cache.get()
            key = f"{id(self)}post_init"
            cache[key] = True
            try:
                __dataclass_post_init__(self)
            except ValueError as e:
                raise ValidationError(self, self.__class__, [e], path=[f"{cls.__name__}.__post_init__"])
            finally:
                cache.pop(key, None)

        __post_init__.__module__ = __dataclass_post_init__.__module__
        __post_init__.__qualname__ = __dataclass_post_init__.__qualname__

        setattr(cls, "__post_init__", __post_init__)

    def cwtch_update_forward_refs(localns, globalns):
        resolve_types(cls, globalns=globalns, localns=localns)
        _build(cls, env_prefixes, env_source, validate, ignore_extra, handle_circular_refs, rebuild=True, **kwds)

    setattr(cls, "cwtch_update_forward_refs", staticmethod(cwtch_update_forward_refs))

    def cwtch_rebuild():
        _build(cls, env_prefixes, env_source, validate, ignore_extra, handle_circular_refs, rebuild=True, **kwds)

    setattr(cls, "cwtch_rebuild", staticmethod(cwtch_rebuild))

    setattr(cls, "__cwtch_model__", True)
    setattr(cls, "__cwtch_handle_circular_refs__", handle_circular_refs)

    # views

    def update_type(tp, view_names: list[str]):
        if getattr(tp, "__origin__", None) is not None:
            return tp.__class__(
                update_type(getattr(tp, "__origin__", tp), view_names),
                tp.__metadata__
                if hasattr(tp, "__metadata__")
                else tuple(update_type(arg, view_names) for arg in tp.__args__),
            )
        if isinstance(tp, UnionType):
            return Union[*(update_type(arg, view_names) for arg in tp.__args__)]
        if getattr(tp, "__cwtch_model__", None):
            for view_name in view_names:
                if hasattr(tp, view_name):
                    return getattr(tp, view_name)
        return tp

    cls_dataclass_fields = {k: v for k, v in cls.__dataclass_fields__.items()}
    cls_fields = dataclasses_fields(cls)

    for view_cls in list(
        {
            k: v
            for item in cls.__mro__[::-1][1:]
            for k in item.__dict__
            if hasattr((v := getattr(item, k)), "__cwtch_view_params__")
        }.values()
    ):
        view_name = getattr(view_cls, "__cwtch_view_name__", view_cls.__name__)
        view_params = view_cls.__cwtch_view_params__
        for item in view_cls.__mro__[::-1][1:]:
            if hasattr(item, "__cwtch_view_params__"):
                view_params.update({k: v for k, v in item.__cwtch_view_params__.items() if v != UNSET})
        include = view_params["include"]
        exclude = view_params["exclude"]
        view_validate = view_params["validate"]
        if view_validate is UNSET:
            view_validate = validate
        view_ignore_extra = view_params["ignore_extra"]
        if view_ignore_extra is UNSET:
            view_ignore_extra = ignore_extra
        recursive = view_params["recursive"]
        if recursive is UNSET:
            recursive = True

        view_kwds = {"init": True, "kw_only": True}

        fields = {f.name: f for f in cls_fields}
        for item in view_cls.__mro__[::-1][1:-1]:
            for k in item.__annotations__:
                fields[k] = item.__dataclass_fields__[k]
        for k in cls.__annotations__:
            fields[k] = cls_dataclass_fields[k]
        for item in view_cls.__bases__[::-1]:
            if hasattr(item, "__cwtch_view_params__") and item.__name__ in cls.__dict__:
                for k in item.__annotations__:
                    fields[k] = item.__dataclass_fields__[k]
        if view_name in cls.__dict__ and view_cls.__annotations__:
            for f in dataclasses_fields(dataclasses.dataclass(view_cls, **{**kwds, **view_kwds})):
                fields[f.name] = f
        fields = {
            k: v
            for k, v in fields.items()
            if (include is UNSET or k in include) and (exclude is UNSET or k not in exclude)
        }
        fields = {k: copy_field(v) for k, v in fields.items()}

        view_field_subst = get_fields_substitution(cls, view_cls=view_cls)

        for f_name, f in fields.items():
            for k in ("type", "default", "default_factory"):
                subst = view_field_subst[k]
                if f_name not in subst:
                    continue
                if getattr(f, k) != subst[f_name]:
                    setattr(f, k, subst[f_name])

        view_annotations = {k: v.type for k, v in fields.items()}

        if recursive is not False:
            view_names = recursive if isinstance(recursive, list) else [view_name]
            for k, v in fields.items():
                view_annotations[k] = v.type = update_type(v.type, view_names)
                if v.default_factory:
                    v.default_factory = update_type(v.default_factory, view_names)  # type: ignore

        view_parameters = set()
        for f in fields.values():
            if type(f.type) == TypeVar:
                view_parameters.add(f.type)
            elif hasattr(f.type, "__parameters__"):
                for p in f.type.__parameters__:
                    view_parameters.add(p)
        parameters = [p for p in getattr(cls, "__parameters__", []) if p in view_parameters]
        for p in getattr(view_cls, "__parameters__", []):
            if p in view_parameters and p not in parameters:
                parameters.append(p)

        for p in getattr(view_cls, "__parameters__", ()):
            if p not in parameters:
                parameters += (p,)

        if parameters:

            class ViewBase(Generic[*parameters]):
                pass

        else:

            class ViewBase:
                pass

        for k, v in fields.items():
            setattr(ViewBase, k, v)

        ViewBase.__annotations__ = view_annotations
        ViewBase = dataclasses.dataclass(ViewBase, **view_kwds)

        if parameters:

            class View(ViewBase, Generic[*parameters]):
                __dataclass_fields__ = fields

        else:

            class View(ViewBase):
                __dataclass_fields__ = fields

        setattr(
            View,
            "__init__",
            create_init(
                View,
                {f.name: f for f in dataclasses_fields(View) if f.init and not _is_classvar(f.type, typing)},
                view_validate,
                view_ignore_extra,
            ),
        )

        if parameters:
            setattr(View, "__class_getitem__", classmethod(make_class_getitem(View)))

        View.__name__ = f"{cls.__name__}.{view_name}"
        View.__qualname__ = view_cls.__qualname__
        View.__module__ = view_cls.__module__
        if view_name in cls.__dict__:
            View.__annotations__ = view_cls.__annotations__
        View.__cwtch_view__ = True  # type: ignore
        View.__cwtch_view_base__ = cls  # type: ignore
        View.__cwtch_view_name__ = view_name  # type: ignore
        View.__cwtch_view_params__ = view_params  # type: ignore
        View.__xxx__ = view_cls

        setattr(cls, view_name, ViewDesc(View))

    return cls


def dataclass(
    cls=None,
    *,
    env_prefix: str | list[str] | None = None,
    env_source: Callable[[], dict] | None = None,
    validate: bool = True,
    ignore_extra: bool = False,
    handle_circular_refs: bool = False,
    **kwds,
) -> Type | Callable[[Type], Type]:
    """
    Args:
      env_prefix: prefix(or list of prefixes) for environment variables.
      env_source: environment variables source factory.
      ignore_extra: ignore extra arguments passed to init(default False).
      handle_circular_refs: handle or not circular refs.
      kwds: other dataclasses.dataclass arguments.
    """

    def wrapper(cls):
        env_prefixes = None
        if env_prefix is not None and not isinstance(env_prefix, list):
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

        cls.__cwtch_params__ = {
            "env_prefix": env_prefix,
            "env_source": env_source,
            "validate": validate,
            "ignore_extra": ignore_extra,
            "handle_circular_refs": handle_circular_refs,
            **kwds,
        }

        return cls

    if cls is None:
        return wrapper

    return wrapper(cls)


# -------------------------------------------------------------------------------------------------------------------- #


def view(
    cls=None,
    *,
    include: Unset[set[str]] = UNSET,
    exclude: Unset[set[str]] = UNSET,
    validate: Unset[bool] = UNSET,
    ignore_extra: Unset[bool] = UNSET,
    recursive: Unset[bool | list[str]] = UNSET,
):
    """
    Decorator to create view of root model.

    Args:
      include: set of field names to include from root model.
      exclude: set of field names to exclude from root model.
      validate: if False skip validation(default True).
      ignore_extra: ignore extra arguments passed to init(default False).
      recursive: ... default(True).
    """

    if include is not UNSET and exclude is not UNSET and include & exclude:  # type: ignore
        raise ValueError("same field in include and exclude are not allowed")

    def wrapper(cls):
        if exclude is not UNSET and cls.__dict__.keys() & exclude:
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
