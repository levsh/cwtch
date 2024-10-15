import functools
import json
import os
import typing

from collections.abc import Sequence
from copy import deepcopy
from inspect import _empty, signature
from types import UnionType, new_class
from typing import Any, Callable, ClassVar, Generic, Literal, Type, Union, cast

import rich.repr

from cwtch.config import EXTRA, HANDLE_CIRCULAR_REFS, RECURSIVE, SHOW_INPUT_VALUE_ON_ERROR, VALIDATE
from cwtch.core import CACHE
from cwtch.core import asdict as _asdict
from cwtch.core import get_validator, validate_value, validate_value_using_validator
from cwtch.errors import ValidationError
from cwtch.types import _MISSING, UNSET, Missing, Unset


def is_classvar(tp) -> bool:
    return getattr(tp, "__origin__", tp) is ClassVar


def is_cwtch_model(cls) -> bool:
    return bool(getattr(cls, "__cwtch_model__", None) and not getattr(cls, "__cwtch_view__", None))


def is_cwtch_view(cls) -> bool:
    return bool(getattr(cls, "__cwtch_model__", None) and getattr(cls, "__cwtch_view__", None))


# -------------------------------------------------------------------------------------------------------------------- #


@rich.repr.auto
class Field:
    def __init__(
        self,
        *,
        default=_MISSING,
        default_factory: Missing[Callable] = _MISSING,
        init: bool = True,
        repr: bool = True,
        validate: bool = True,
        metadata: Unset[dict] = UNSET,
    ):
        self.name: str = cast(str, None)
        self.type: Any = cast(Any, None)
        self.default: Any = default
        self.default_factory = default_factory
        self.init = init
        self.repr = repr
        self.validate = validate
        self.metadata = {} if metadata is UNSET else metadata

    def __rich_repr__(self):
        yield "name", self.name
        yield "type", self.type
        yield "default", self.default, True
        yield "default_factory", self.default_factory, False
        yield "init", self.init
        yield "repr", self.repr
        yield "validate", self.validate
        yield "metadata", self.metadata

    def __eq__(self, other) -> bool:
        if not isinstance(other, Field):
            return False
        return (
            self.name,
            self.type,
            self.default,
            self.default_factory,
            self.init,
            self.repr,
            self.validate,
            self.metadata,
        ) == (
            other.name,
            other.type,
            other.default,
            other.default_factory,
            other.init,
            other.repr,
            other.validate,
            other.metadata,
        )


# -------------------------------------------------------------------------------------------------------------------- #


def field(
    default=_MISSING,
    *,
    default_factory: Missing[Callable] = _MISSING,
    init: bool = True,
    repr: bool = True,
    validate: bool = True,
    metadata: Unset[dict] = UNSET,
) -> Any:
    return Field(
        default=default,
        default_factory=default_factory,
        init=init,
        repr=repr,
        validate=validate,
        metadata=metadata,
    )


# -------------------------------------------------------------------------------------------------------------------- #


def dataclass(
    cls=None,
    *,
    slots: bool = False,
    env_prefix: Unset[str | Sequence[str]] = UNSET,
    env_source: Unset[Callable] = UNSET,
    validate: Unset[bool] = UNSET,
    show_input_value_on_error: Unset[bool] = UNSET,
    extra: Unset[Literal["ignore", "forbid"]] = UNSET,
    repr: bool = True,
    eq: bool = True,
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

    if validate is UNSET:
        validate = VALIDATE
    if show_input_value_on_error is UNSET:
        show_input_value_on_error = SHOW_INPUT_VALUE_ON_ERROR
    if extra is UNSET:
        extra = EXTRA
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
        return _build(
            cls,
            slots,
            cast(
                Unset[Sequence[str]],
                env_prefix if env_prefix is UNSET or isinstance(env_prefix, (list, tuple, set)) else [env_prefix],
            ),
            env_source,
            validate,
            extra,
            repr,
            eq,
            recursive,
            handle_circular_refs,
        )

    if cls is None:
        return wrapper

    return wrapper(cls)


# -------------------------------------------------------------------------------------------------------------------- #


def view(
    view_cls=None,
    *,
    name: Unset[str] = UNSET,
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
        name: view name.
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

    def wrapper(
        view_cls,
        *,
        name=name,
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

        cls = next((x for x in view_cls.__bases__ if getattr(x, "__cwtch_model__", None)), None)

        if not cls:
            raise Exception("view class must inherit from cwtch model or view")

        if getattr(cls, "__cwtch_view__", None):
            cls = cls.__cwtch_view_base__

        return _build_view(
            cls,
            view_cls,
            name,
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

    if view_cls is None:
        return wrapper

    return wrapper(view_cls)


# -------------------------------------------------------------------------------------------------------------------- #


class ViewDesc:
    def __init__(self, view_cls: Type):
        self.view_cls = view_cls

    def __get__(self, obj, owner=None):
        view_cls = self.view_cls
        if obj:
            # TODO
            return lambda: view_cls(**{k: v for k, v in _asdict(obj).items() if k in view_cls.__cwtch_fields__})
        return view_cls


# -------------------------------------------------------------------------------------------------------------------- #


def default_env_source() -> dict:
    return cast(dict, os.environ)


# -------------------------------------------------------------------------------------------------------------------- #


def is_generic(cls) -> bool:
    return bool(
        (origin := getattr(cls, "__origin__", None))
        and getattr(origin, "__parameters__", None)
        and getattr(cls, "__args__", None)
    )


# -------------------------------------------------------------------------------------------------------------------- #


@functools.cache
def _instantiate_generic(tp):
    if not is_generic(tp):
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
        cls.__cwtch_fields__ = _get_substituted_fields(cls, fields_subst)
        cls.__annotations__ = _get_substituted_annotations(cls, fields_subst)

    for k, v in cls.__cwtch_fields__.items():
        setattr(cls, k, v)

    cls = cls.cwtch_rebuild()

    # build views
    for f_k in __origin__.__dict__:
        f_v = getattr(cls, f_k)

        if not is_cwtch_view(f_v):
            continue

        bases: tuple[Type[Any], ...] = (f_v,)

        if Generic in f_v.__bases__:
            bases += (Generic[*f_v.__parameters__],)

        view_cls = new_class(
            f_v.__name__,
            bases,
            exec_body=lambda ns: ns.update(
                {f_name: f.default for f_name, f in f_v.__cwtch_fields__.items() if f.default is not _MISSING},
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
            view_cls.__cwtch_fields__ = _get_substituted_fields(f_v, view_fields_subst)
            view_cls.__annotations__ = _get_substituted_annotations(f_v, view_fields_subst)

        view_params = view_cls.__cwtch_view_params__

        setattr(
            cls,
            f_k,
            _build_view(
                cls,
                view_cls,
                view_params.get("name", UNSET),
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
    if is_generic(cls):
        parameters_map = dict(
            zip(
                cls.__origin__.__parameters__,
                (_instantiate_generic(arg) if is_generic(arg) else arg for arg in cls.__args__),
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
        for f_name, f in origin.__cwtch_fields__.items():  # type: ignore
            for k in ("type", "default", "default_factory"):
                k_v = getattr(f, k)
                if hasattr(k_v, "__typing_subst__") and k_v in parameters_map:
                    fields_subst[k][f_name] = k_v.__typing_subst__(parameters_map[k_v])
                elif getattr(k_v, "__parameters__", None):
                    fields_subst[k][f_name] = k_v[*[parameters_map[tp] for tp in k_v.__parameters__]]
    return fields_subst


# -------------------------------------------------------------------------------------------------------------------- #


def _get_substituted_fields(cls, fields_subst: dict[str, dict]) -> dict[str, Field]:
    fields = {k: v for k, v in cls.__cwtch_fields__.items()}
    for f_name, f in fields.items():
        new_f = None
        for k in ("type", "default", "default_factory"):
            subst = fields_subst[k]
            if f_name not in subst:
                continue
            if getattr(f, k) != subst[f_name]:
                new_f = new_f or copy_field(f)
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


def copy_field(f: Field) -> Field:
    new_f = Field(
        default=f.default,
        default_factory=f.default_factory,
        init=f.init,
        repr=f.repr,
        metadata=deepcopy(f.metadata),
    )
    new_f.name = f.name
    new_f.type = f.type
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
        "_env_source": env_source or default_env_source,
        "_json_loads": json.loads,
        "_builtins_id": id,
        "ValidationError": ValidationError,
        "JSONDecodeError": json.JSONDecodeError,
    }

    fields = {k: v for k, v in fields.items() if v.init is True}

    args = ["__cwtch_self__"]

    if fields:
        args.append("*")

    if handle_circular_refs:
        args.append("_cwtch_cache_key=None")

    sorted_fields = sorted(
        fields.keys(),
        key=lambda name: not (fields[name].default is _MISSING and fields[name].default_factory is _MISSING),
    )

    body = [
        "if _cache_get().get(f'{_builtins_id(__cwtch_self__)}post_init'):",
        "    return",
    ]

    body += ["__cwtch_fields_set__ = ()"]

    if env_prefixes is not UNSET:
        body += [
            "env_source_data = _env_source()",
            "env_data = {}",
            "for f_name, f in __cwtch_self__.__cwtch_fields__.items():",
            "   if env_var := f.metadata.get('env_var', True):",
            "       for env_prefix in _env_prefixes:",
            "           if isinstance(env_var, str):",
            "               key = env_var",
            "           else:",
            "               key = f'{env_prefix}{f_name}'.upper()",
            "           if key in env_source_data:",
            "               try:",
            "                   env_data[f_name] = _json_loads(env_source_data[key])",
            "               except JSONDecodeError:",
            "                   env_data[f_name] = env_source_data[key]",
            "               break",
        ]

    if fields:
        indent = ""
        if handle_circular_refs:
            body += [
                "if _cwtch_cache_key is not None:",
                "    _cache_get()[_cwtch_cache_key] = __cwtch_self__",
                "try:",
            ]
            indent = " " * 4

        for f_name in sorted_fields:
            field = fields[f_name]
            locals[f"f_{f_name}"] = field
            locals[f"t_{f_name}"] = field.type
            locals[f"d_{f_name}"] = field.default
            locals[f"df_{f_name}"] = field.default_factory
            args.append(f"{f_name}: t_{f_name} = _MISSING")  #
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
                        f'{indent}        raise TypeError(f"{{__class__.__name__}}.__init__()'
                        f" missing required keyword-only argument: '{f_name}'\")",
                    ]
                body += [
                    f"{indent}else:",
                    f"{indent}    __cwtch_fields_set__ += ('{f_name}',)",
                ]
            else:
                body += [
                    f"{indent}if {f_name} is _MISSING:",
                ]
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
                        f'{indent}    raise TypeError(f"{{__class__.__name__}}.__init__()'
                        f" missing required keyword-only argument: '{f_name}'\")",
                    ]
                body += [
                    f"{indent}else:",
                    f"{indent}    __cwtch_fields_set__ += ('{f_name}',)",
                ]
            if validate and field.validate:
                locals[f"v_{f_name}"] = get_validator(field.type)
                body += [
                    f"{indent}try:",
                    f"{indent}    __cwtch_self__.{f_name} = _validate({f_name}, t_{f_name}, v_{f_name})",
                    f"{indent}except (TypeError, ValueError, ValidationError) as e:",
                    f"    {indent}raise ValidationError({f_name}, __class__, [e], path=[f_{f_name}.name])",
                ]
            else:
                body += [
                    f"{indent}__cwtch_self__.{f_name} = {f_name}",
                ]

        body += [
            f"{indent}__cwtch_self__.__cwtch_fields_set__ = __cwtch_fields_set__",
        ]

        if handle_circular_refs:
            body += [
                "finally:",
                "    _cache_get().pop(_cwtch_cache_key, None)",
            ]

    else:
        body = ["pass"]

    body += [
        "if '__post_init__' in __class__.__dict__:",
        "    try:",
        "        __cwtch_self__.__post_init__()",
        "    except ValueError as e:",
        "        raise ValidationError(",
        "            __cwtch_self__,",
        "            __cwtch_self__.__class__,",
        "            [e],",
        "            path=[f'{__cwtch_self__.__class__.__name__}.__post_init__']",
        "        )",
    ]

    if extra == "ignore":
        args += ["**__cwtch_kwds__"]

    __init__ = _create_fn(cls, "__init__", args, body, globals=globals, locals=locals)

    __init__.__module__ = cls.__module__
    __init__.__qualname__ = f"{cls.__name__}.__init__"

    return __init__


def _create_rich_repr(cls, fields):
    globals = {}
    locals = {}

    fields = {k: v for k, v in fields.items() if v.repr is True}

    args = ["__cwtch_self__"]

    body = []

    if fields:
        for f_name in fields:
            body.append(f"yield '{f_name}', __cwtch_self__.{f_name}")
    else:
        body = ["pass"]

    __rich_repr__ = _create_fn(cls, "__rich_repr__", args, body, globals=globals, locals=locals)

    __rich_repr__.__module__ = cls.__module__
    __rich_repr__.__qualname__ = f"{cls.__name__}.__rich_repr__"

    return __rich_repr__


def _create_eq(cls):
    globals = {}
    locals = {}

    args = ["__cwtch_self__", "other"]

    body = [
        "if not hasattr(other, '__cwtch_model__') or __cwtch_self__.__class__ != other.__class__:",
        "   return False",
    ]

    body += [
        "if not sorted(__cwtch_self__.__cwtch_fields__.keys()) == sorted(other.__cwtch_fields__.keys()):",
        "    return False",
        "l = [getattr(__cwtch_self__, f_name) for f_name in __cwtch_self__.__cwtch_fields__]",
        "r = [getattr(other, f_name) for f_name in other.__cwtch_fields__]",
        "return l == r",
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

    defaults = {k: __dict__.pop(k) for k, v in __annotations__.items() if k in __dict__ and not is_classvar(v)}

    __cwtch_fields__ = getattr(cls, "__cwtch_fields__", {})

    for base in __bases__[::-1]:
        if hasattr(base, "__cwtch_fields__"):
            __cwtch_fields__.update({k: v for k, v in base.__cwtch_fields__.items() if k not in __cwtch_fields__})

    for f_name, f_type in __annotations__.items():
        f = defaults.get(f_name, _MISSING)
        if not isinstance(f, Field):
            f = Field(default=f)
        f.name = f_name
        f.type = f_type
        __cwtch_fields__[f_name] = f

    # if env_prefix is not UNSET:
    #     for f in __cwtch_fields__.values():
    #         if f.metadata.get("env_var", True) and f.default == _MISSING and f.default_factory == _MISSING:
    #             raise TypeError(f"environment field[{f.name}] should has default or default_factory value")

    if not rebuild:
        if slots:
            if "__slots__" in __dict__:
                raise TypeError(f"{cls.__name__} already specifies __slots__")
            __dict__["__slots__"] = tuple(__cwtch_fields__.keys()) + ("__cwtch_fields_set__",)
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
            __cwtch_fields__,
            validate,
            extra,
            env_prefixes,
            env_source,
            handle_circular_refs,
        ),
    )

    if repr:
        setattr(cls, "__rich_repr__", _create_rich_repr(cls, __cwtch_fields__))
        rich.repr.auto()(cls)  # type: ignore

    if eq:
        setattr(cls, "__eq__", _create_eq(cls))

    if hasattr(cls, "__parameters__"):
        setattr(cls, "__class_getitem__", classmethod(_make_class_getitem(cls)))

    setattr(cls, "__cwtch_handle_circular_refs__", handle_circular_refs)

    setattr(cls, "__cwtch_fields__", __cwtch_fields__)

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

    defaults = {k: __dict__.pop(k) for k, v in __annotations__.items() if k in __dict__ and not is_classvar(v)}

    if hasattr(view_cls, "__cwtch_fields__"):
        __cwtch_fields__ = {k: copy_field(v) for k, v in view_cls.__cwtch_fields__.items()}
    else:
        __cwtch_fields__ = {}
        for base in __bases__[::-1]:
            if hasattr(base, "__cwtch_fields__"):
                __cwtch_fields__.update({k: copy_field(v) for k, v in base.__cwtch_fields__.items()})

    for f_name, f_type in __annotations__.items():
        f = defaults.get(f_name, _MISSING)
        if not isinstance(f, Field):
            f = Field(default=f)
        f.name = f_name
        f.type = f_type
        __cwtch_fields__[f_name] = f

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
    if include and (missing_fields := set(include) - __cwtch_fields__.keys()):
        raise Exception(f"fields {list(missing_fields)} not present")

    exclude = __cwtch_view_params__.get("exclude", UNSET)

    __cwtch_fields__ = {
        k: v
        for k, v in __cwtch_fields__.items()
        if (include is UNSET or k in include) and (exclude is UNSET or k not in exclude)
    }

    view_recursive = __cwtch_view_params__["recursive"]
    if view_recursive:
        view_names = view_recursive if isinstance(view_recursive, (list, tuple, set)) else [view_name]
        for k, v in __cwtch_fields__.items():
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
            __slots__ = tuple(__cwtch_fields__.keys())
            if "__slots__" in __dict__:
                __slots__ += tuple(x for x in __dict__["__slots__"] if x not in __slots__)
            __dict__["__slots__"] = __slots__
        for f_name, f in __cwtch_fields__.items():
            __dict__[f_name] = f
        __dict__.pop("__dict__", None)
        view_cls = type(view_cls.__name__, view_cls.__bases__, __dict__)

    setattr(
        view_cls,
        "__init__",
        _create_init(
            view_cls,
            __cwtch_fields__,
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
            _create_rich_repr(view_cls, __cwtch_fields__),
        )
        rich.repr.auto()(view_cls)  # type: ignore

    if __cwtch_view_params__["eq"]:
        setattr(
            view_cls,
            "__eq__",
            _create_eq(view_cls),
        )

    if getattr(view_cls, "__parameters__", None):
        setattr(view_cls, "__class_getitem__", classmethod(_make_class_getitem(view_cls)))

    __class__ = view_cls  # noqa: F841

    def __getattribute__(self, name: str, /) -> Any:
        result = super().__getattribute__(name)
        if isinstance(result, Field) and result.name not in object.__getattribute__(self, "__cwtch_fields__"):
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
    setattr(view_cls, "__cwtch_fields__", __cwtch_fields__)
    setattr(view_cls, "__cwtch_view_params__", __cwtch_view_params__)

    def cwtch_rebuild(view_cls):
        if not getattr(view_cls, "__cwtch_view__", None):
            raise Exception("not cwtch view")
        return _build_view(
            view_cls.__cwtch_view_base__,
            view_cls,
            name=name,
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

    setattr(cls, view_name, ViewDesc(view_cls))

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
        for f_name, f in cls.__cwtch_fields__.items()
        if (not exclude or f_name not in exclude) and hasattr(obj, f"{f.name}{suffix}" if suffix else f_name)
    }
    if data:
        kwds.update(data)
    if exclude:
        kwds = {k: v for k, v in kwds.items() if k not in exclude}

    cache = CACHE.get()
    cache["reset_circular_refs"] = reset_circular_refs
    try:
        return cls(_cwtch_cache_key=(cls, id(obj)), **kwds)
    finally:
        del cache["reset_circular_refs"]


# -------------------------------------------------------------------------------------------------------------------- #


def asdict(
    inst,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    exclude_unset: bool | None = None,
    exclude_none: bool | None = None,
    context: dict | None = None,
) -> dict:
    """Return `cwtch` model as dict."""
    return _asdict(
        inst,
        include_=include,
        exclude_=exclude,
        exclude_unset=exclude_unset,
        exclude_none=exclude_none,
        context=context,
    )


# -------------------------------------------------------------------------------------------------------------------- #


def resolve_types(cls, globalns=None, localns=None, *, include_extras: bool = True, rebuild: bool = True):
    kwds = {"globalns": globalns, "localns": localns, "include_extras": include_extras}

    hints = typing.get_type_hints(cls, **kwds)
    for f_name, f in cls.__cwtch_fields__.items():
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
