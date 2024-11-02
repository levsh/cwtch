# ruff: noqa: F401


import functools
import json
import os
import sys
import typing

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import _FIELD, _DataclassParams
from inspect import _empty, signature
from types import UnionType, new_class
from typing import Any, Callable, ClassVar, Generic, Literal, Type, Union, cast

import rich.repr

from cwtch.config import (
    ATTACH,
    EQ,
    EXTRA,
    HANDLE_CIRCULAR_REFS,
    RECURSIVE,
    REPR,
    SHOW_INPUT_VALUE_ON_ERROR,
    SLOTS,
    VALIDATE,
)
from cwtch.core import _MISSING, CACHE, UNSET, Missing, Unset, UnsetType
from cwtch.core import asdict as _asdict
from cwtch.core import dumps_json as _dumps_json
from cwtch.core import get_validator, validate_value, validate_value_using_validator
from cwtch.errors import ValidationError


def _is_classvar(tp) -> bool:
    return getattr(tp, "__origin__", tp) is ClassVar


def is_cwtch_model(cls) -> bool:
    return bool(getattr(cls, "__cwtch_model__", None) and not getattr(cls, "__cwtch_view__", None))


def is_cwtch_view(cls) -> bool:
    return bool(getattr(cls, "__cwtch_model__", None) and getattr(cls, "__cwtch_view__", None))


# -------------------------------------------------------------------------------------------------------------------- #


@rich.repr.auto
class Field:
    __slots__ = (
        "name",
        "type",
        "default",
        "default_factory",
        "init",
        "init_alias",
        "repr",
        "compare",
        "property",
        "validate",
        "metadata",
        "kw_only",
        "_field_type",
    )

    def __init__(
        self,
        *,
        default=_MISSING,
        default_factory: Missing[Callable] = _MISSING,
        init: bool = True,
        init_alias: Unset[str] = UNSET,
        repr: Unset[Literal[False]] = UNSET,
        compare: Unset[bool] = UNSET,
        property: Unset[Literal[True]] = UNSET,
        validate: Unset[bool] = UNSET,
        metadata: Unset[dict] = UNSET,
        kw_only: Unset[bool] = UNSET,
    ):
        self.name: str = cast(str, None)
        self.type: Any = cast(Any, None)
        self.default: Any = default
        self.default_factory = default_factory
        self.init = init
        self.init_alias = init_alias
        self.repr = repr
        self.compare = compare
        self.property = property
        self.validate = validate
        self.metadata = {} if metadata is UNSET else metadata
        self.kw_only = kw_only
        self._field_type = None

    def __rich_repr__(self):
        yield "name", self.name
        yield "type", self.type
        yield "default", self.default, True
        yield "default_factory", self.default_factory, False
        yield "init", self.init
        yield "init_alias", self.init_alias
        yield "repr", self.repr
        yield "compare", self.compare
        yield "property", self.property
        yield "validate", self.validate
        yield "metadata", self.metadata
        yield "kw_only", self.kw_only

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
            self.repr,
            self.compare,
            self.property,
            self.validate,
            self.metadata,
            self.kw_only,
            self._field_type,
        ) == (
            other.name,
            other.type,
            other.default,
            other.default_factory,
            other.init,
            other.init_alias,
            other.repr,
            other.compare,
            other.property,
            other.validate,
            other.metadata,
            other.kw_only,
            other._field_type,
        )


# -------------------------------------------------------------------------------------------------------------------- #


def field(
    default=_MISSING,
    *,
    default_factory: Missing[Callable] = _MISSING,
    init: bool = True,
    init_alias: Unset[str] = UNSET,
    repr: Unset[Literal[False]] = UNSET,
    compare: Unset[bool] = UNSET,
    property: Unset[Literal[True]] = UNSET,
    validate: Unset[bool] = UNSET,
    metadata: Unset[dict] = UNSET,
    kw_only: Unset[dict] = UNSET,
) -> Any:
    return Field(
        default=default,
        default_factory=default_factory,
        init=init,
        init_alias=init_alias,
        repr=repr,
        compare=compare,
        property=property,
        validate=validate,
        metadata=metadata,
        kw_only=kw_only,
    )


# -------------------------------------------------------------------------------------------------------------------- #


def dataclass(
    cls=None,
    *,
    slots: Unset[bool] = UNSET,
    env_prefix: Unset[str | Sequence[str]] = UNSET,
    env_source: Unset[Callable] = UNSET,
    validate: Unset[bool] = UNSET,
    show_input_value_on_error: Unset[bool] = UNSET,
    extra: Unset[Literal["ignore", "forbid"]] = UNSET,
    repr: Unset[bool] = UNSET,
    eq: Unset[bool] = UNSET,
    recursive: Unset[bool | Sequence[str]] = UNSET,
    handle_circular_refs: Unset[bool] = UNSET,
):
    """
    Args:
        slots: if true, __slots__ attribute will be generated
            and new class will be returned instead of the original one.
            If __slots__ is already defined in the class, then TypeError is raised.
        env_prefix: prefix(or list of prefixes) for environment variables.
        env_source: environment variables source factory.
        validate: validate or not fields.
        extra: ignore or forbid extra arguments passed to init.
        repr: if true, a __rich_repr__ method will be generated and rich.repr.auto decorator applied to the class.
        eq: if true, an __eq__ method will be generated.
            This method compares the class as if it were a tuple of its fields, in order.
            Both instances in the comparison must be of the identical type.
        recursive: ...
        handle_circular_refs: handle or not circular refs.
    """

    if slots is UNSET:
        slots = SLOTS
    if validate is UNSET:
        validate = VALIDATE
    if show_input_value_on_error is UNSET:
        show_input_value_on_error = SHOW_INPUT_VALUE_ON_ERROR
    if extra is UNSET:
        extra = EXTRA
    if repr is UNSET:
        repr = REPR
    if eq is UNSET:
        eq = EQ
    if recursive is UNSET:
        recursive = RECURSIVE
    if handle_circular_refs is UNSET:
        handle_circular_refs = HANDLE_CIRCULAR_REFS

    def wrapper(
        cls,
        slots=slots,
        env_prefix=env_prefix,
        env_source=env_source,
        validate=validate,
        extra=extra,
        repr=repr,
        eq=eq,
        recursive=recursive,
        handle_circular_refs=handle_circular_refs,
    ):
        # if getattr(cls, "__cwtch_asjson__", None) is not None:
        #     logger.warning("Method __cwtch_asjson__ is not applicable to dataclass")

        return _build(
            cls,
            cast(bool, slots),
            cast(
                Unset[Sequence[str]],
                env_prefix if env_prefix is UNSET or isinstance(env_prefix, (list, tuple, set)) else [env_prefix],
            ),
            env_source,
            cast(bool, validate),
            cast(Literal["ignore", "forbid"], extra),
            cast(bool, repr),
            cast(bool, eq),
            cast(bool, recursive),
            cast(bool, handle_circular_refs),
        )

    if cls is None:
        return wrapper

    return wrapper(cls)


# -------------------------------------------------------------------------------------------------------------------- #


def view(
    view_cls_or_view_name=UNSET,
    *,
    attach: Unset[bool] = UNSET,
    include: Unset[Sequence[str]] = UNSET,
    exclude: Unset[Sequence[str]] = UNSET,
    slots: Unset[bool] = UNSET,
    env_prefix: Unset[str | Sequence[str]] = UNSET,
    env_source: Unset[Callable] = UNSET,
    validate: Unset[bool] = UNSET,
    extra: Unset[Literal["ignore", "forbid"]] = UNSET,
    repr: Unset[bool] = UNSET,
    eq: Unset[bool] = UNSET,
    recursive: Unset[bool | Sequence[str]] = UNSET,
    handle_circular_refs: Unset[bool] = UNSET,
):
    """
    Args:
        include: list of fields to include in view.
        exclude: list of fields to exclude from view.
        slots: if true, __slots__ attribute will be generated
            and new class will be returned instead of the original one.
            If __slots__ is already defined in the class, then TypeError is raised.
            If UNSET value from base view model will be used.
        env_prefix: prefix(or list of prefixes) for environment variables.
            If UNSET value from base view model will be used.
        env_source: environment variables source factory.
            If UNSET value from base view model will be used.
        validate: validate or not fields.
            If UNSET value from base view model will be used.
        extra: ignore or forbid extra arguments passed to init.
            If UNSET value from base view model will be used.
        repr: if true, a __rich_repr__ method will be generated and rich.repr.auto decorator applied to the class.
            If UNSET value from base view model will be used.
        eq: if true, an __eq__ method will be generated.
            This method compares the class as if it were a tuple of its fields, in order.
            Both instances in the comparison must be of the identical type.
            If UNSET value from base view model will be used.
        recursive: ...
        handle_circular_refs: handle or not circular refs.
            If UNSET value from base view model will be used.
    """

    if isinstance(view_cls_or_view_name, str):
        view_name = view_cls_or_view_name
    else:
        view_name = UNSET

    if attach is UNSET:
        attach = ATTACH

    def wrapper(
        view_cls,
        *,
        name=view_name,
        attach=attach,
        include=include,
        exclude=exclude,
        slots=slots,
        env_prefix=env_prefix,
        env_source=env_source,
        validate=validate,
        extra=extra,
        repr=repr,
        eq=eq,
        recursive=recursive,
        handle_circular_refs=handle_circular_refs,
    ):
        if exclude and set(exclude) & view_cls.__annotations__.keys():  # type: ignore
            raise ValueError(f"unable to exclude fields {list(set(exclude) & view_cls.__annotations__.keys())}")  # type: ignore

        # if getattr(cls, "__cwtch_asjson__", None) is not None:
        #     logger.warning("Method __cwtch_asjson__ is not applicable to dataclass view")

        cls = next((x for x in view_cls.__bases__ if getattr(x, "__cwtch_model__", None)), None)

        if not cls:
            raise Exception("view class must inherit from cwtch model or view")

        if getattr(cls, "__cwtch_view__", None):
            cls = cls.__cwtch_view_base__

        return _build_view(
            cls,
            view_cls,
            name,
            attach,
            include,
            exclude,
            slots,
            cast(
                Unset[Sequence[str]],
                env_prefix if env_prefix is UNSET or isinstance(env_prefix, (list, tuple, str)) else [env_prefix],
            ),
            env_source,
            validate,
            extra,
            repr,
            eq,
            recursive,
            handle_circular_refs,
        )

    if isinstance(view_cls_or_view_name, (str, UnsetType)):
        return wrapper

    return wrapper(view_cls_or_view_name)


# -------------------------------------------------------------------------------------------------------------------- #


class _ViewDesc:
    def __init__(self, view_cls: Type):
        self.view_cls = view_cls

    def __get__(self, obj, owner=None):
        view_cls = self.view_cls
        if obj:
            # TODO
            return lambda: view_cls(**{k: v for k, v in _asdict(obj).items() if k in view_cls.__dataclass_fields__})
        return view_cls


# -------------------------------------------------------------------------------------------------------------------- #


def _default_env_source() -> dict:
    return cast(dict, os.environ)


# -------------------------------------------------------------------------------------------------------------------- #


def _is_generic(cls) -> bool:
    return bool(
        (origin := getattr(cls, "__origin__", None))
        and getattr(origin, "__parameters__", None)
        and getattr(cls, "__args__", None)
    )


# -------------------------------------------------------------------------------------------------------------------- #


@functools.cache
def _instantiate_generic(tp):
    if not _is_generic(tp):
        raise TypeError("must be called with a subscripted dataclass type")

    __origin__ = tp.__origin__

    x = ", ".join(map(lambda x: x.strip("'"), (arg.__name__ for arg in tp.__args__)))
    cls = type(
        f"{__origin__.__name__}[{x}]",  # type: ignore
        (__origin__,),  # type: ignore
        {
            "__annotations__": {k: v for k, v in __origin__.__annotations__.items()},
        },
    )

    fields_subst = _get_fields_substitution(tp)

    if fields_subst:
        cls.__dataclass_fields__ = _get_substituted_fields(cls, fields_subst)
        cls.__annotations__ = _get_substituted_annotations(cls, fields_subst)

    for k, v in cls.__dataclass_fields__.items():
        setattr(cls, k, v)

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
            f_v.__name__,
            bases,
            exec_body=lambda ns: ns.update(
                {f_name: f.default for f_name, f in f_v.__dataclass_fields__.items() if f.default is not _MISSING},
            ),
        )
        view_cls.__annotations__ = {k: v for k, v in f_v.__annotations__.items()}

        if f_v.__parameters__:
            view_fields_subst = {k: v for k, v in fields_subst.items()}
            for k, v in _get_fields_substitution(cls, exclude_params=f_v.__parameters__).items():
                view_fields_subst[k].update(v)
        else:
            view_fields_subst = fields_subst

        if view_fields_subst:
            view_cls.__dataclass_fields__ = _get_substituted_fields(f_v, view_fields_subst)
            view_cls.__annotations__ = _get_substituted_annotations(f_v, view_fields_subst)

        view_params = view_cls.__cwtch_view_params__

        setattr(
            cls,
            f_k,
            _build_view(
                cls,
                view_cls,
                view_params.get("name", UNSET),
                view_params.get("attach", UNSET),
                view_params.get("include", UNSET),
                view_params.get("exclude", UNSET),
                view_params.get("slots", UNSET),
                view_params.get("env_prefix", UNSET),
                view_params.get("env_source", UNSET),
                view_params.get("validate", UNSET),
                view_params.get("extra", UNSET),
                view_params.get("repr", UNSET),
                view_params.get("eq", UNSET),
                view_params.get("recursive", UNSET),
                view_params.get("handle_circular_refs", UNSET),
            ),
        )

    return cls


# -------------------------------------------------------------------------------------------------------------------- #


def _make_class_getitem(__class__):

    def __class_getitem__(cls, *args, **kwds):
        result = super().__class_getitem__(*args, **kwds)  # type: ignore
        if not hasattr(result, "__cwtch_instantiated__"):
            result = _instantiate_generic(result)
            setattr(result, "__cwtch_instantiated__", True)
        return result

    __class__.__class_getitem__ = __class_getitem__

    return __class_getitem__


# -------------------------------------------------------------------------------------------------------------------- #


def _get_parameters_map(cls, exclude_params=None) -> dict:
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


# -------------------------------------------------------------------------------------------------------------------- #


def _get_fields_substitution(cls, exclude_params=None) -> dict[str, dict]:
    fields_subst = {"type": {}, "default": {}, "default_factory": {}}
    origin = getattr(cls, "__origin__", None)
    items = getattr(origin, "__orig_bases__", ())[::-1] + (cls,)
    for item in items:
        if not hasattr(getattr(item, "__origin__", item), "__cwtch_model__"):
            continue
        origin = getattr(item, "__origin__", None)
        parameters_map = _get_parameters_map(item, exclude_params=exclude_params)
        if not parameters_map:
            continue
        for f_name, f in origin.__dataclass_fields__.items():  # type: ignore
            for k in ("type", "default", "default_factory"):
                k_v = getattr(f, k)
                if hasattr(k_v, "__typing_subst__") and k_v in parameters_map:
                    fields_subst[k][f_name] = k_v.__typing_subst__(parameters_map[k_v])
                elif getattr(k_v, "__parameters__", None):
                    fields_subst[k][f_name] = k_v[*[parameters_map[tp] for tp in k_v.__parameters__]]
    return fields_subst


# -------------------------------------------------------------------------------------------------------------------- #


def _get_substituted_fields(cls, fields_subst: dict[str, dict]) -> dict[str, Field]:
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


# -------------------------------------------------------------------------------------------------------------------- #


def _get_substituted_annotations(cls, fields_subst: dict[str, dict]) -> dict:
    annotations = {k: v for k, v in cls.__annotations__.items()}
    subst = fields_subst["type"]
    for k in cls.__annotations__:
        if k not in subst:
            continue
        annotations[k] = subst[k]
    return annotations


# -------------------------------------------------------------------------------------------------------------------- #


def _copy_field(f: Field) -> Field:
    new_f = Field(
        default=f.default,
        default_factory=f.default_factory,
        init=f.init,
        init_alias=f.init_alias,
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


# -------------------------------------------------------------------------------------------------------------------- #


def _create_fn(cls, name, args, body, *, globals=None, locals=None):
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


def _create_init(cls, fields, validate, extra, env_prefixes, env_source, handle_circular_refs):
    globals = {}
    locals = {
        "_MISSING": _MISSING,
        "_cache_get": CACHE.get,
        "_validate": validate_value_using_validator,
        "_env_prefixes": env_prefixes,
        "_env_source": env_source or _default_env_source,
        "_json_loads": json.loads,
        "_builtins_id": id,
        "ValidationError": ValidationError,
        "JSONDecodeError": json.JSONDecodeError,
    }

    fields = {k: v for k, v in fields.items() if v.init is True}

    args = ["__cwtch_self__"]

    if fields:
        args.append("/")

    body = ["__cwtch_fields_set__ = ()"]

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
        if handle_circular_refs:
            body += [
                "if __cwtch_cache_key is not None:",
                "    _cache_get()[__cwtch_cache_key] = __cwtch_self__",
                "try:",
            ]
            indent = " " * 4

        if extra == "forbid":
            allowed_extra_field_names = [f.init_alias for f in fields.values() if f.init_alias]
            body += [
                f"{indent}if __extra_kwds:",
                f"{indent}    allowed_extra_field_names = {{{', '.join(allowed_extra_field_names)}}}",
                f"{indent}    for k in __extra_kwds:",
                f"{indent}        if k not in allowed_extra_field_names:",
                f"{indent}            raise TypeError(",
                f'{indent}                f"{{__class__.__name__}}.__init__() "',
                f"{indent}                f\"got an unexpected keyword argument '{{k}}'\"",
                f"{indent}            )",
            ]

        any_fields = [f_name for f_name, f in fields.items() if f.kw_only is not True]
        for f_name in any_fields:
            args.append(f"{f_name}: t_{f_name} = _MISSING")

        kw_only_fields = [f_name for f_name, f in fields.items() if f.kw_only is True]
        if kw_only_fields:
            args.append("*")
        for f_name in kw_only_fields:
            args.append(f"{f_name}: t_{f_name} = _MISSING")

        for f_name in any_fields + kw_only_fields:
            field = fields[f_name]
            locals[f"f_{f_name}"] = field
            locals[f"t_{f_name}"] = field.type
            locals[f"d_{f_name}"] = field.default
            locals[f"df_{f_name}"] = field.default_factory
            if env_prefixes is not UNSET:
                body += [
                    f"{indent}if {f_name} is _MISSING:",
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
                        (
                            f'{indent}        raise TypeError(f"{{__class__.__name__}}.__init__()'
                            f" missing required positional argument: '{f_name}'\")"
                            if fields[f_name].kw_only is not True
                            else f'{indent}        raise TypeError(f"{{__class__.__name__}}.__init__()'
                            f" missing required keyword-only argument: '{f_name}'\")"
                        ),
                    ]
                body += [
                    f"{indent}else:",
                    f"{indent}    __cwtch_fields_set__ += ('{f_name}',)",
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
                        (
                            f'{indent}    raise TypeError(f"{{__class__.__name__}}.__init__()'
                            f" missing required positional argument: '{f_name}'\")"
                            if fields[f_name].kw_only is not True
                            else f'{indent}        raise TypeError(f"{{__class__.__name__}}.__init__()'
                            f" missing required keyword-only argument: '{f_name}'\")"
                        )
                    ]
                if field.init_alias:
                    indent = indent[:-4]
                body += [
                    f"{indent}else:",
                    f"{indent}    __cwtch_fields_set__ += ('{f_name}',)",
                ]
            if field.validate is True or (field.validate is UNSET and validate is True):
                locals[f"v_{f_name}"] = get_validator(field.type)
                body += [
                    f"{indent}try:",
                    f"{indent}    _{f_name} = _validate({f_name}, t_{f_name}, v_{f_name})",
                    f"{indent}except (TypeError, ValueError, ValidationError) as e:",
                    f"{indent}    raise ValidationError(..., __class__, [e], path=[f_{f_name}.name])",
                ]
            else:
                body += [
                    f"{indent}_{f_name} = {f_name}",
                ]
            if field.property is True:
                body += [
                    f"__cwtch_self__._prop_{f_name} = _{f_name}",
                    f"__class__.{f_name} = property(lambda self: self._prop_{f_name})",
                ]
            else:
                body += [
                    f"{indent}__cwtch_self__.{f_name} = _{f_name}",
                ]

        body += [
            f"{indent}__cwtch_self__.__cwtch_fields_set__ = __cwtch_fields_set__",
        ]

        if handle_circular_refs is True:
            body += [
                "finally:",
                "    _cache_get().pop(__cwtch_cache_key, None)",
            ]

    else:
        body = ["pass"]

    if handle_circular_refs:
        args.append("__cwtch_cache_key=None")

    args += ["**__extra_kwds"]

    body += [
        "if '__post_init__' in __class__.__dict__:",
        "    try:",
        "        __class__.__dict__['__post_init__'](__cwtch_self__)",
        "    except ValueError as e:",
        "        raise ValidationError(",
        "            __cwtch_self__,",
        "            __class__,",
        "            [e],",
        "            path=[f'{__class__.__name__}.__post_init__']",
        "        )",
    ]

    __init__ = _create_fn(cls, "__init__", args, body, globals=globals, locals=locals)

    __init__.__module__ = cls.__module__
    __init__.__qualname__ = f"{cls.__name__}.__init__"

    return __init__


def _create_rich_repr(cls, fields):
    globals = {}
    locals = {}

    fields = {k: v for k, v in fields.items() if v.repr is not False}

    args = ["__cwtch_self__"]

    body = []

    if not fields:
        raise Exception("unable to create __rich_repr__ method, all fields disable `repr`")

    for f_name in fields:
        body.append(f"yield '{f_name}', __cwtch_self__.{f_name}")

    __rich_repr__ = _create_fn(cls, "__rich_repr__", args, body, globals=globals, locals=locals)

    __rich_repr__.__module__ = cls.__module__
    __rich_repr__.__qualname__ = f"{cls.__name__}.__rich_repr__"

    return __rich_repr__


def _create_eq(cls, fields):
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


def _build(
    cls,
    slots: bool,
    env_prefix: Unset[str | Sequence[str]],
    env_source: Unset[Callable],
    validate: bool,
    extra: Literal["ignore", "forbid"],
    repr: bool,
    eq: bool,
    recursive: bool | Sequence[str],
    handle_circular_refs: bool,
    rebuild: bool = False,
):
    __bases__ = cls.__bases__
    __annotations__ = cls.__annotations__
    __dict__ = {k: v for k, v in cls.__dict__.items()}

    defaults = {k: __dict__.pop(k) for k, v in __annotations__.items() if k in __dict__ and not _is_classvar(v)}

    __dataclass_fields__ = getattr(cls, "__dataclass_fields__", {})

    for base in __bases__[::-1]:
        if hasattr(base, "__dataclass_fields__"):
            __dataclass_fields__.update(
                {k: v for k, v in base.__dataclass_fields__.items() if k not in __dataclass_fields__}
            )

    for f_name, f_type in __annotations__.items():
        if _is_classvar(f_type):
            continue
        if f_name in defaults:
            f = defaults[f_name]
        else:
            f = __dataclass_fields__.get(f_name, _MISSING)
        if not isinstance(f, Field):
            f = Field(default=f)
            f._field_type = _FIELD
        f.name = f_name
        f.type = f_type
        __dataclass_fields__[f_name] = f

    if not rebuild:
        if slots:
            if "__slots__" in __dict__:
                raise TypeError(f"{cls.__name__} already specifies __slots__")
            __dict__["__slots__"] = tuple(
                [f_name if f.property is not True else f"_prop_{f_name}" for f_name, f in __dataclass_fields__.items()]
            ) + ("__cwtch_fields_set__",)
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
            validate,
            extra,
            env_prefixes,
            env_source,
            handle_circular_refs,
        ),
    )

    if repr:
        setattr(cls, "__rich_repr__", _create_rich_repr(cls, __dataclass_fields__))
        rich.repr.auto()(cls)  # type: ignore

    if eq:
        setattr(cls, "__eq__", _create_eq(cls, __dataclass_fields__))

    if hasattr(cls, "__parameters__"):
        setattr(cls, "__class_getitem__", classmethod(_make_class_getitem(cls)))

    setattr(cls, "__cwtch_handle_circular_refs__", handle_circular_refs)

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
            env_prefix=env_prefix,
            env_source=env_source,
            validate=validate,
            extra=extra,
            repr=repr,
            eq=eq,
            recursive=recursive,
            handle_circular_refs=handle_circular_refs,
            rebuild=True,
        )

    setattr(cls, "cwtch_rebuild", classmethod(cwtch_rebuild))
    cls.cwtch_rebuild.__func__.__qualname__ = "cwtch_rebuild"

    def cwtch_update_forward_refs(cls, localns, globalns):
        resolve_types(cls, globalns=globalns, localns=localns)

    setattr(cls, "cwtch_update_forward_refs", classmethod(cwtch_update_forward_refs))
    cls.cwtch_update_forward_refs.__func__.__qualname__ = "cwtch_update_forward_refs"

    setattr(cls, "__cwtch_model__", True)

    setattr(
        cls,
        "__cwtch_params__",
        {
            "slots": slots,
            "env_prefix": env_prefix,
            "env_source": env_source,
            "validate": validate,
            "extra": extra,
            "repr": repr,
            "eq": eq,
            "recursive": recursive,
            "handle_circular_refs": handle_circular_refs,
        },
    )

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
                        view_params.get("attach", UNSET),
                        view_params.get("include", UNSET),
                        view_params.get("exclude", UNSET),
                        view_params.get("slots", UNSET),
                        view_params.get("env_prefix", UNSET),
                        view_params.get("env_source", UNSET),
                        view_params.get("validate", UNSET),
                        view_params.get("extra", UNSET),
                        view_params.get("repr", UNSET),
                        view_params.get("eq", UNSET),
                        view_params.get("recursive", UNSET),
                        view_params.get("handle_circular_refs", UNSET),
                    ),
                )

    return cls


def _build_view(
    cls,
    view_cls,
    name: Unset[str],
    attach: Unset[bool],
    include: Unset[Sequence[str]],
    exclude: Unset[Sequence[str]],
    slots: Unset[bool],
    env_prefix: Unset[str | Sequence[str]],
    env_source: Unset[Callable],
    validate: Unset[bool],
    extra: Unset[Literal["ignore", "forbid"]],
    repr: Unset[bool],
    eq: Unset[bool],
    recursive: Unset[bool | Sequence[str]],
    handle_circular_refs: Unset[bool],
    rebuild: bool = False,
):
    def update_type(tp, view_names: Sequence[str]):
        if getattr(tp, "__origin__", None) is not None:
            return tp.__class__(
                update_type(getattr(tp, "__origin__", tp), view_names),
                (
                    tp.__metadata__
                    if hasattr(tp, "__metadata__")
                    else tuple(update_type(arg, view_names) for arg in tp.__args__)
                ),
            )
        if isinstance(tp, UnionType):
            return Union[*(update_type(arg, view_names) for arg in tp.__args__)]  # type: ignore
        if getattr(tp, "__cwtch_model__", None):
            for view_name in view_names:
                if hasattr(tp, view_name):
                    return getattr(tp, view_name)
        return tp

    __bases__ = view_cls.__bases__
    __annotations__ = view_cls.__annotations__
    __dict__ = {k: v for k, v in view_cls.__dict__.items()}

    defaults = {k: __dict__.pop(k) for k, v in __annotations__.items() if k in __dict__ and not _is_classvar(v)}

    if hasattr(view_cls, "__dataclass_fields__"):
        __dataclass_fields__ = {k: _copy_field(v) for k, v in view_cls.__dataclass_fields__.items()}
    else:
        __dataclass_fields__ = {}
        for base in __bases__[::-1]:
            if hasattr(base, "__dataclass_fields__"):
                __dataclass_fields__.update({k: _copy_field(v) for k, v in base.__dataclass_fields__.items()})

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

    __cwtch_params__ = view_cls.__cwtch_params__

    __cwtch_view_params__ = {
        "slots": __cwtch_params__["slots"],
        "env_prefix": __cwtch_params__["env_prefix"],
        "env_source": __cwtch_params__["env_source"],
        "validate": __cwtch_params__["validate"],
        "repr": __cwtch_params__["repr"],
        "eq": __cwtch_params__["eq"],
        "extra": __cwtch_params__["extra"],
        "recursive": __cwtch_params__["recursive"],
        "handle_circular_refs": __cwtch_params__["handle_circular_refs"],
    }

    if hasattr(view_cls, "__cwtch_view_params__"):
        __cwtch_view_params__.update({k: v for k, v in view_cls.__cwtch_view_params__.items() if v != UNSET})
    if name is not UNSET:
        __cwtch_view_params__["name"] = name
    if attach is not UNSET:
        __cwtch_view_params__["attach"] = attach
    if include is not UNSET:
        __cwtch_view_params__["include"] = include
    if exclude is not UNSET:
        __cwtch_view_params__["exclude"] = exclude
    if slots is not UNSET:
        __cwtch_view_params__["slots"] = slots
    if env_prefix is not UNSET:
        __cwtch_view_params__["env_prefix"] = env_prefix
    if env_source is not UNSET:
        __cwtch_view_params__["env_source"] = env_source
    if validate is not UNSET:
        __cwtch_view_params__["validate"] = validate
    if repr is not UNSET:
        __cwtch_view_params__["repr"] = repr
    if eq is not UNSET:
        __cwtch_view_params__["eq"] = eq
    if extra is not UNSET:
        __cwtch_view_params__["extra"] = extra
    if recursive is not UNSET:
        __cwtch_view_params__["recursive"] = recursive
    if handle_circular_refs is not UNSET:
        __cwtch_view_params__["handle_circular_refs"] = handle_circular_refs

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
        view_names = view_recursive if isinstance(view_recursive, (list, tuple, set)) else [view_name]
        for k, v in __dataclass_fields__.items():
            v.type = update_type(v.type, view_names)
            if k in view_cls.__annotations__:
                view_cls.__annotations__[k] = v.type
            if v.default_factory is not _MISSING:
                v.default_factory = update_type(v.default_factory, view_names)  # type: ignore

    if __cwtch_view_params__["env_prefix"] is UNSET or isinstance(
        __cwtch_view_params__["env_prefix"], (list, tuple, str)
    ):
        env_prefixes = __cwtch_view_params__["env_prefix"]
    else:
        env_prefixes = [__cwtch_view_params__["env_prefix"]]

    if not rebuild:
        if __cwtch_view_params__["slots"]:
            __slots__ = tuple(
                [f_name if f.property is not None else f"_prop_{f_name}" for f_name, f in __dataclass_fields__.items()]
            )

            if "__slots__" in __dict__:
                __slots__ += tuple(x for x in __dict__["__slots__"] if x not in __slots__)
            __dict__["__slots__"] = __slots__
        else:
            for f_name, f in __dataclass_fields__.items():
                __dict__[f_name] = f
        __dict__.pop("__dict__", None)
        view_cls = type(view_cls.__name__, view_cls.__bases__, __dict__)

    setattr(
        view_cls,
        "__init__",
        _create_init(
            view_cls,
            __dataclass_fields__,
            __cwtch_view_params__["validate"],
            __cwtch_view_params__["extra"],
            env_prefixes,
            __cwtch_view_params__["env_source"],
            __cwtch_view_params__["handle_circular_refs"],
        ),
    )

    if __cwtch_view_params__["repr"]:
        setattr(
            view_cls,
            "__rich_repr__",
            _create_rich_repr(view_cls, __dataclass_fields__),
        )
        rich.repr.auto()(view_cls)  # type: ignore

    if __cwtch_view_params__["eq"]:
        setattr(
            view_cls,
            "__eq__",
            _create_eq(view_cls, __dataclass_fields__),
        )

    if getattr(view_cls, "__parameters__", None):
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

    setattr(view_cls, "__cwtch_view_name__", view_name)
    setattr(view_cls, "__cwtch_view__", True)
    setattr(view_cls, "__cwtch_view_base__", cls)
    setattr(view_cls, "__dataclass_fields__", __dataclass_fields__)
    setattr(view_cls, "__cwtch_view_params__", __cwtch_view_params__)

    def cwtch_rebuild(view_cls):
        if not getattr(view_cls, "__cwtch_view__", None):
            raise Exception("not cwtch view")
        return _build_view(
            view_cls.__cwtch_view_base__,
            view_cls,
            name=name,
            attach=attach,
            include=include,
            exclude=exclude,
            slots=slots,
            env_prefix=env_prefix,
            env_source=env_source,
            validate=validate,
            extra=extra,
            repr=repr,
            eq=eq,
            recursive=recursive,
            handle_circular_refs=handle_circular_refs,
            rebuild=True,
        )

    setattr(view_cls, "cwtch_rebuild", classmethod(cwtch_rebuild))

    if attach is True:
        setattr(cls, view_name, _ViewDesc(view_cls))

    return view_cls


# -------------------------------------------------------------------------------------------------------------------- #


def from_attributes(
    cls,
    obj,
    data: dict | None = None,
    exclude: Sequence | None = None,
    suffix: str | None = None,
    reset_circular_refs: bool | None = None,
):
    """
    Build model from attributes of other object.

    Args:
      obj: object from which to build.
      data: additional data to build.
      exclude: list of fields to exclude.
      suffix: fields suffix.
      reset_circular_refs: reset circular references to None.
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

    cache = CACHE.get()
    cache["reset_circular_refs"] = reset_circular_refs
    try:
        return cls(__cwtch_cache_key=(cls, id(obj)), **kwds)
    finally:
        del cache["reset_circular_refs"]


# -------------------------------------------------------------------------------------------------------------------- #


def asdict(
    inst,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    exclude_none: bool | None = None,
    exclude_unset: bool | None = None,
    context: dict | None = None,
) -> dict:
    """Return `cwtch` model as dict."""

    return _asdict(
        inst,
        include_=include,
        exclude_=exclude,
        exclude_none=exclude_none,
        exclude_unset=exclude_unset,
        context=context,
    )


# -------------------------------------------------------------------------------------------------------------------- #


def dumps(inst, encoder: Callable[[Any], Any] | None = None, context: dict | None = None):
    return _dumps_json(inst, encoder, context)


# -------------------------------------------------------------------------------------------------------------------- #


def resolve_types(cls, globalns=None, localns=None, *, include_extras: bool = True, rebuild: bool = True):
    kwds = {"globalns": globalns, "localns": localns, "include_extras": include_extras}

    hints = typing.get_type_hints(cls, **kwds)
    for f_name, f in cls.__dataclass_fields__.items():
        if f_name in hints:
            f.type = hints[f_name]
        if f_name in cls.__annotations__:
            cls.__annotations__[f_name] = hints[f_name]

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
