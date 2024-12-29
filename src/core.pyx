# cython: language_level=3
# cython: boundscheck=False
# cython: profile=False
# distutils: language=c

import datetime
import functools
import types
import typing

from abc import ABCMeta
from collections import namedtuple
from collections.abc import Mapping
from contextvars import ContextVar
from enum import Enum, EnumType
from types import WrapperDescriptorType
from typing import (
    Any,
    Generic,
    GenericAlias,
    Type,
    TypeVar,
    _AnnotatedAlias,
    _AnyMeta,
    _CallableType,
    _GenericAlias,
    _LiteralGenericAlias,
    _SpecialGenericAlias,
    _TupleType,
    _UnionGenericAlias,
)
from uuid import UUID

import cython
import orjson

from typing_extensions import Doc

from .errors import ValidationError


__all__ = (
    "get_validator",
    "validate_value",
    "register_validator",
    "get_json_schema_builder",
    "make_json_schema",
    "register_json_schema_builder",
    "asdict",
)


cdef extern from "Python.h":

    object PyNumber_Long(object o)
    object PyNumber_Float(object o)
    int PyNumber_Check(object o)
    int PyUnicode_Check(object o)
    object PyObject_Call(object callable_, object args, object kwargs)


_CACHE = ContextVar("cache", default={})

TRUE_MAP = (True, 1, "1", "true", "t", "y", "yes", "True", "TRUE", "Y", "Yes", "YES")
FALSE_MAP = (False, 0, "0", "false", "f", "n", "no", "False", "FALSE", "N", "No", "NO")


T = TypeVar("T")


date_fromisoformat = datetime.date.fromisoformat
datetime_fromisoformat = datetime.datetime.fromisoformat


class _MissingType:
    """Type to mark value as missing. Internal use only."""

    def __copy__(self, *args, **kwds):
        return self

    def __deepcopy__(self, *args, **kwds):
        return self

    def __bool__(self):
        return False

    def __str__(self):
        return "_MISSING"

    def __repr__(self):
        return "_MISSING"


_MISSING = _MissingType()

_Missing = T | _MissingType


class _DefaultType:
    """Type to mark value has `default` or `default factory`. Internal use only."""

    def __copy__(self, *args, **kwds):
        return self

    def __deepcopy__(self, *args, **kwds):
        return self

    def __bool__(self):
        return False

    def __str__(self):
        return "_DEFAULT"

    def __repr__(self):
        return "_DEFAULT"


_DEFAULT = _DefaultType()


class UnsetType:
    """Type to mark value as unset."""

    def __copy__(self, *args, **kwds):
        return self

    def __deepcopy__(self, *args, **kwds):
        return self

    def __bool__(self):
        return False

    def __str__(self):
        return "UNSET"

    def __repr__(self):
        return "UNSET"

    @classmethod
    def __cwtch_json_schema__(cls, context=None) -> dict:
        return {}


UNSET = UnsetType()

Unset = T | UnsetType


AsDictKwds = namedtuple("AsDictKwds", ("include", "exclude", "exclude_none", "exclude_unset", "context"))


class TypeWrapperMeta(type):
    def __new__(cls, name, bases, ns):
        ns["_cwtch_T"] = ns["__orig_bases__"][0].__args__[0]

        class Desc:
            __slots__ = ("k", "v")

            def __init__(self, k, v):
                self.k = k
                self.v = v

            def __get__(self, instance, owner):
                if instance is not None:
                    return getattr(instance._cwtch_o, self.k)
                return self.v

        ns.update(
            {
                k: Desc(k, v)
                for k, v in getattr(ns["_cwtch_T"], "__dict__", {}).items()
                if type(v) == WrapperDescriptorType and k != "__getattribute__"
            }
        )

        return super().__new__(cls, name, bases, ns)

    def __getattr__(self, name):
        return getattr(self._cwtch_T, name)

    def __subclasscheck__(cls, subclass):
        return issubclass(subclass, cls._cwtch_T)

    def __instancecheck__(self, instance):
        return isinstance(instance, self._cwtch_T)


class TypeWrapper(Generic[T], metaclass=TypeWrapperMeta):
    def __init__(self, o):
        self._cwtch_o = o

    def __getattribute__(self, name):
        object_getattribute = object.__getattribute__
        if name in object_getattribute(self, "__class__").__dict__:
            return object_getattribute(self, name)
        if name in object_getattribute(self, "__dict__"):
            return object_getattribute(self, name)
        return getattr(object_getattribute(self, "_cwtch_o"), name)


class TypeMetadata:
    """Base class for type metadata."""

    def json_schema(self) -> dict:
        return {}

    def before(self, value, /):
        return value

    def after(self, value, /):
        return value


@cython.cfunc
def asdict_handler(inst, kwds):
    if (fields := getattr(inst, "__dataclass_fields__", None)) is None:
        return inst

    data = {}

    for k in fields:
        v = getattr(inst, k, None)
        if kwds.exclude_unset and v is UNSET:
            continue
        if kwds.exclude_none and v is None:
            continue
        if isinstance(v, list):
            data[k] = [x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v]
        elif isinstance(v, dict):
            data[k] = {
                kk: vv if isinstance(vv, (int, str, float, bool)) else _asdict_handler(vv, kwds) for kk, vv in v.items()
            }
        elif isinstance(v, tuple):
            data[k] = tuple([x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v])
        elif isinstance(v, set):
            data[k] = {x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v}
        else:
            v = _asdict_handler(v, kwds)
            if kwds.exclude_unset and v is UNSET:
                continue
            if kwds.exclude_none and v is None:
                continue
            data[k] = v

    return data


@cython.cfunc
def _asdict_handler(inst, kwds):
    if inst_asdict := getattr(inst, "__cwtch_asdict__", None):
        return inst_asdict(asdict_handler, kwds)
    return asdict_handler(inst, kwds)


@cython.cfunc
def asdict_root_handler(inst, kwds):
    if (keys := getattr(inst, "__dataclass_fields__", None)) is None:
        if isinstance(inst, dict):
            keys = inst
        else:
            raise Exception(f"expect cwtch model or dict")

    use_inc_cond: cython.int = 0
    use_exc_cond: cython.int = 0

    if kwds[0] is not None:
        use_inc_cond = 1
    if kwds[1] is not None:
        use_exc_cond = 1

    kwds_ = AsDictKwds(UNSET, UNSET, kwds[2], kwds[3], kwds[4])

    data = {}

    for k in keys:
        if use_inc_cond and not k in kwds[0]:
            continue
        if use_exc_cond and k in kwds[1]:
            continue
        v = getattr(inst, k, None)
        if kwds.exclude_unset and v is UNSET:
            continue
        if kwds.exclude_none and v is None:
            continue
        if isinstance(v, list):
            data[k] = [x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds_) for x in v]
        elif isinstance(v, dict):
            data[k] = {
                kk: vv if isinstance(vv, (int, str, float, bool)) else _asdict_handler(vv, kwds_)
                for kk, vv in v.items()
            }
        elif isinstance(v, tuple):
            data[k] = tuple([x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds_) for x in v])
        elif isinstance(v, set):
            data[k] = {x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds_) for x in v}
        else:
            v = _asdict_handler(v, kwds_)
            if kwds.exclude_unset and v is UNSET:
                continue
            if kwds.exclude_none and v is None:
                continue
            data[k] = v

    return data


@cython.cfunc
def validate_any(value, T, /):
    return value


@cython.cfunc
def validate_none(value, T, /):
    if value is not None:
        raise ValidationError(value, T, [ValueError("value is not a None")])


@cython.cfunc
def validate_bool(value, T, /):
    if value in TRUE_MAP:
        return True
    if value in FALSE_MAP:
        return False
    raise ValueError("could not convert value to bool")


@cython.cfunc
def validate_int(value, T, /):
    return PyNumber_Long(value)


@cython.cfunc
def validate_float(value, T, /):
    return PyNumber_Float(value)


@cython.cfunc
def validate_str(value, T, /):
    if not isinstance(value, str):
        raise ValueError(f"value is not a valid {T}")
    return f"{value}"


@cython.cfunc
def validate_bytes(value, T, /):
    if isinstance(value, str):
        return value.encode()
    return bytes(value)


@cython.cfunc
def validate_type(value, T, /):
    value = getattr(value, "_cwtch_o", value)
    if (origin := getattr(T, "__origin__", T)) == T:
        if isinstance(value, origin):
            return value
    if (fields := getattr(origin, "__dataclass_fields__", None)) is not None:
        if getattr(origin, "__cwtch_handle_circular_refs__", None):
            cache = _CACHE.get()
            cache_key = (T, id(value))
            if (cache_value := cache.get(cache_key)) is not None:
                return cache_value if not cache["reset_circular_refs"] else UNSET
        if isinstance(value, dict):
            return PyObject_Call(origin, (), value)
        kwds = {f_name: v for f_name in fields if (v := getattr(value, f_name, _MISSING)) is not _MISSING}
        return PyObject_Call(origin, (), kwds)
    if T == UnsetType:
        if value != UNSET:
            raise ValueError(f"value is not a valid {T}")
        return value
    if T == type(None):
        if value is not None:
            raise ValueError("value is not a None")
        return value
    if origin == type:
        if type(value) != type:
            raise ValueError(f"value should be a type")
        if (args := getattr(T, "__args__", None)) is not None:
            arg = T.__args__[0]
            if getattr(arg, "__base__", None) is None or not issubclass(value, arg):
                raise ValueError(f"invalid value for {T}".replace("typing.", ""))
        return value
    return origin(value)


@cython.cfunc
def validate_list(value, T, /):
    if isinstance(value, list):
        if (args := getattr(T, "__args__", None)) is not None:
            try:
                T_arg = args[0]
                if T_arg == int:
                    return [x if type(x) == int else PyNumber_Long(x) for x in value]
                if T_arg == str:
                    return [validate_str(x, str) for x in value]
                if T_arg == float:
                    return [x if type(x) == float else PyNumber_Float(x) for x in value]
                validator = get_validator(T_arg)
                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return [getattr(x, "_cwtch_o", x) if isinstance(x, origin) else validator(x, T_arg) for x in value]
                if validator == validate_any:
                    return value
                return [validator(x, T_arg) for x in value]
            except (TypeError, ValueError, ValidationError) as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                for v in value:
                    try:
                        validator(v, T_arg)
                        i += 1
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                            raise ValidationError(value, T, [e], path=path)
                        else:
                            path = [i]
                            raise ValidationError(value, T, [e], path=path, path_value=v)
                raise e

        return value

    if not isinstance(value, (tuple, set)):
        raise ValueError(f"invalid value for {T}".replace("typing.", ""))

    if args := getattr(T, "__args__", None):
        try:
            T_arg = args[0]
            if T_arg == int:
                return [x if type(x) == int else PyNumber_Long(x) for x in value]
            if T_arg == str:
                return [validate_str(x, str) for x in value]
            if T_arg == float:
                return [x if type(x) == float else PyNumber_Float(x) for x in value]
            validator = get_validator(T_arg)
            if validator == validate_type:
                origin = getattr(T_arg, "__origin__", T_arg)
                return [getattr(x, "_cwtch_o", x) if isinstance(x, origin) else validator(x, T_arg) for x in value]
            if validator == validate_any:
                return [x for x in value]
            return [validator(x, T_arg) for x in value]
        except (TypeError, ValueError, ValidationError) as e:
            i: cython.int = 0
            validator = get_validator(T_arg)
            for v in value:
                try:
                    validator(v, T_arg)
                    i += 1
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                        raise ValidationError(value, T, [e], path=path)
                    else:
                        path = [i]
                        raise ValidationError(value, T, [e], path=path, path_value=v)
            raise e

    return [x for x in value]


@cython.cfunc
def validate_tuple(value, T, /):
    if isinstance(value, tuple):
        if (T_args := getattr(T, "__args__", None)) is not None:
            if (len_v := len(value)) == 0 or (len_v == len(T_args) and T_args[-1] != Ellipsis):
                try:
                    return tuple(
                        [
                            (
                                PyNumber_Long(x)
                                if T_args == int
                                else get_validator(getattr(T_arg, "__origin__", T_arg))(x, T_arg)
                            )
                            for x, T_arg in zip(value, T_args)
                        ]
                    )
                except (TypeError, ValueError, ValidationError) as e:
                    i: cython.int = 0
                    for v, T_arg in zip(value, T_args):
                        try:
                            validator = get_validator(T_arg)
                            validator(v, T_arg)
                            i += 1
                        except (TypeError, ValueError, ValidationError) as e:
                            if isinstance(e, ValidationError) and e.path:
                                path = [i] + e.path
                                raise ValidationError(value, T, [e], path=path)
                            else:
                                path = [i]
                                raise ValidationError(value, T, [e], path=path, path_value=v)
                    raise e

            if T_args[-1] != Ellipsis:
                raise ValueError(f"invalid arguments count for {T}")

            T_arg = T_args[0]
            try:
                if T_arg == int:
                    return tuple([x if type(x) == int else PyNumber_Long(x) for x in value])
                if T_arg == str:
                    return tuple([validate_str(x, str) for x in value])
                if T_arg == float:
                    return tuple([x if type(x) == float else PyNumber_Float(x) for x in value])
                validator = get_validator(T_arg)
                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return tuple(
                        [getattr(x, "_cwtch_o", x) if isinstance(x, origin) else validator(x, T_arg) for x in value]
                    )
                if validator == validate_any:
                    return value
                return tuple([validator(x, T_arg) for x in value])
            except (TypeError, ValueError, ValidationError) as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                for v in value:
                    try:
                        validator(v, T_arg)
                        i += 1
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                            raise ValidationError(value, T, [e], path=path)
                        else:
                            path = [i]
                            raise ValidationError(value, T, [e], path=path, path_value=v)
                raise e

        return value

    if not isinstance(value, (list, set)):
        raise ValueError(f"invalid value for {T}".replace("typing.", ""))

    if (T_args := getattr(T, "__args__", None)) is not None:
        if (len_v := len(value)) == 0 or (len_v == len(T_args) and T_args[-1] != Ellipsis):
            try:
                return tuple(
                    [
                        (
                            PyNumber_Long(x)
                            if T_args == int
                            else get_validator(getattr(T_arg, "__origin__", T_arg))(x, T_arg)
                        )
                        for x, T_arg in zip(value, T_args)
                    ]
                )
            except (TypeError, ValueError, ValidationError) as e:
                i: cython.int = 0
                for v, T_arg in zip(value, T_args):
                    try:
                        validator = get_validator(T_arg)
                        validator(v, T_arg)
                        i += 1
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                            raise ValidationError(value, T, [e], path=path)
                        else:
                            path = [i]
                            raise ValidationError(value, T, [e], path=path, path_value=v)
                raise e

        if T_args[-1] != Ellipsis:
            raise ValueError(f"invalid arguments count for {T}")

        T_arg = T_args[0]
        try:
            if T_arg == int:
                return tuple([x if type(x) == int else PyNumber_Long(x) for x in value])
            if T_arg == str:
                return tuple([validate_str(x, str) for x in value])
            if T_arg == float:
                return tuple([x if type(x) == float else PyNumber_Float(x) for x in value])
            validator = get_validator(T_arg)
            if validator == validate_type:
                origin = getattr(T_arg, "__origin__", T_arg)
                return tuple(
                    [getattr(x, "_cwtch_o", x) if isinstance(x, origin) else validator(x, T_arg) for x in value]
                )
            if validator == validate_any:
                return tuple(value)
            return tuple([validator(x, T_arg) for x in value])
        except (TypeError, ValueError, ValidationError) as e:
            i: cython.int = 0
            validator = get_validator(T_arg)
            for v in value:
                try:
                    validator(v, T_arg)
                    i += 1
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                        raise ValidationError(value, T, [e], path=path)
                    else:
                        path = [i]
                        raise ValidationError(value, T, [e], path=path, path_value=v)
            raise e

    return tuple([x for x in value])


@cython.cfunc
def validate_set(value, T, /):
    if isinstance(value, set):
        if (args := getattr(T, "__args__", None)) is not None:
            try:
                T_arg = args[0]
                if T_arg == int:
                    return set(x if type(x) == int else PyNumber_Long(x) for x in value)
                if T_arg == str:
                    return set(validate_str(x, str) for x in value)
                if T_arg == float:
                    return set(x if type(x) == float else PyNumber_Float(x) for x in value)
                validator = get_validator(T_arg)
                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return set(
                        getattr(x, "_cwtch_o", x) if isinstance(x, origin) else validator(x, T_arg) for x in value
                    )
                if validator == validate_any:
                    return value
                return set(validator(x, T_arg) for x in value)
            except (TypeError, ValueError, ValidationError) as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                for v in value:
                    try:
                        validator(v, T_arg)
                        i += 1
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                            raise ValidationError(value, T, [e], path=path)
                        else:
                            path = [i]
                            raise ValidationError(value, T, [e], path=path, path_value=v)
                raise e

        return value

    if not isinstance(value, (list, tuple)):
        raise ValueError(f"invalid value for {T}".replace("typing.", ""))

    if args := getattr(T, "__args__", None):
        try:
            T_arg = args[0]
            if T_arg == int:
                return set(x if type(x) == int else PyNumber_Long(x) for x in value)
            if T_arg == str:
                return set(validate_str(x, str) for x in value)
            if T_arg == float:
                return set(x if type(x) == float else PyNumber_Float(x) for x in value)
            validator = get_validator(T_arg)
            if validator == validate_type:
                origin = getattr(T_arg, "__origin__", T_arg)
                return set(getattr(x, "_cwtch_o", x) if isinstance(x, origin) else validator(x, T_arg) for x in value)
            if validator == validate_any:
                return set(x for x in value)
            return set(validator(x, T_arg) for x in value)
        except (TypeError, ValueError, ValidationError) as e:
            i: cython.int = 0
            validator = get_validator(T_arg)
            for v in value:
                try:
                    validator(v, T_arg)
                    i += 1
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                        raise ValidationError(value, T, [e], path=path)
                    else:
                        path = [i]
                        raise ValidationError(value, T, [e], path=path, path_value=v)
            raise e

    return set(x for x in value)


@cython.cfunc
def validate_dict(value, T, /):
    if not isinstance(value, dict):
        raise ValueError(f"invalid value for {T}".replace("typing.", ""))
    if (args := getattr(T, "__args__", None)) is not None:
        T_k, T_v = args
        origin_v = getattr(T_v, "__origin__", None)
        validator_v = get_validator(origin_v or T_v)
        try:
            if T_k == str:
                if origin_v:
                    return {validate_str(k, T_k): validator_v(v, T_v) for k, v in value.items()}
                return {validate_str(k, T_k): v if type(v) == T_v else validator_v(v, T_v) for k, v in value.items()}
            origin_k = getattr(T_k, "__origin__", None)
            validator_k = get_validator(origin_k or T_k)
            if origin_k is None and origin_v is None:
                return {
                    k if type(k) == T_k else validator_k(k, T_k): v if type(v) == T_v else validator_v(v, T_v)
                    for k, v in value.items()
                }
            if origin_k and origin_v:
                return {validator_k(k, T_k): validator_v(v, T_v) for k, v in value.items()}
            if origin_v:
                return {k if type(k) == T_k else validator_k(k, T_k): validator_v(v, T_v) for k, v in value.items()}
            return {validator_k(k, T_k): v if type(v) == T_v else validator_v(v, T_v) for k, v in value.items()}
        except (TypeError, ValueError, ValidationError) as e:
            validator_k = get_validator(getattr(T_k, "__origin__", T_k))
            for k, v in value.items():
                try:
                    validator_k(k, T_k)
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = ["$", k] + e.path
                        raise ValidationError(value, T, [e], path=path)
                    else:
                        path = ["$", k]
                        raise ValidationError(value, T, [e], path=path, path_value=k)
                try:
                    validator_v(v, T_v)
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [k] + e.path
                        raise ValidationError(value, T, [e], path=path)
                    else:
                        path = [k]
                        raise ValidationError(value, T, [e], path=path, path_value=v)
            raise e

    return value


@cython.cfunc
def validate_mapping(value, T, /):
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid value for {T}".replace("typing.", ""))
    if (args := getattr(T, "__args__", None)) is not None:
        T_k, T_v = args
        origin_v = getattr(T_v, "__origin__", None)
        validator_v = get_validator(origin_v or T_v)
        try:
            if T_k == str:
                if origin_v:
                    return {validate_str(k, T_k): validator_v(v, T_v) for k, v in value.items()}
                return {validate_str(k, T_k): v if type(v) == T_v else validator_v(v, T_v) for k, v in value.items()}
            origin_k = getattr(T_k, "__origin__", None)
            validator_k = get_validator(origin_k or T_k)
            if origin_k is None and origin_v is None:
                return {
                    k if type(k) == T_k else validator_k(k, T_k): v if type(v) == T_v else validator_v(v, T_v)
                    for k, v in value.items()
                }
            if origin_k and origin_v:
                return {validator_k(k, T_k): validator_v(v, T_v) for k, v in value.items()}
            if origin_v:
                return {k if type(k) == T_k else validator_k(k, T_k): validator_v(v, T_v) for k, v in value.items()}
            return {validator_k(k, T_k): v if type(v) == T_v else validator_v(v, T_v) for k, v in value.items()}
        except (TypeError, ValueError, ValidationError) as e:
            validator_k = get_validator(getattr(T_k, "__origin__", T_k))
            for k, v in value.items():
                try:
                    validator_k(k, T_k)
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = ["$", k] + e.path
                        raise ValidationError(value, T, [e], path=path)
                    else:
                        path = ["$", k]
                        raise ValidationError(value, T, [e], path=path, path_value=k)
                try:
                    validator_v(v, T_v)
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [k] + e.path
                        raise ValidationError(value, T, [e], path=path)
                    else:
                        path = [k]
                        raise ValidationError(value, T, [e], path=path, path_value=v)
            raise e

    return value


@cython.cfunc
def validate_generic_alias(value, T, /):
    return get_validator(T.__origin__)(value, T)


@cython.cfunc
def validate_callable(value, T, /):
    if not callable(value):
        raise ValueError("not callable")
    return value


@cython.cfunc
def validate_annotated(value, T, /):
    __metadata__ = T.__metadata__

    for metadata in __metadata__:
        if isinstance(metadata, TypeMetadata):
            value = metadata.before(value)

    __origin__ = T.__origin__
    value = get_validator(__origin__)(value, __origin__)

    for metadata in __metadata__:
        if isinstance(metadata, TypeMetadata):
            value = metadata.after(value)

    return value


@cython.cfunc
def validate_union(value, T, /):
    for T_arg in T.__args__:
        if getattr(T_arg, "__origin__", None) is None and (T_arg == Any or type(value) == T_arg):
            return value
    errors = []
    for T_arg in T.__args__:
        try:
            return validate_value(value, T_arg)
        except Exception as e:
            errors.append(e)
    raise ValidationError(value, T, errors)


@cython.cfunc
def validate_literal(value, T, /):
    if value not in T.__args__:
        raise ValidationError(value, T, [ValueError(f"value is not a one of {list(T.__args__)}")])
    return value


@cython.cfunc
def validate_abcmeta(value, T, /):
    if isinstance(value, getattr(T, "__origin__", T)):
        return value
    raise ValidationError(value, T, [ValueError(f"value is not a valid {T}")])


@cython.cfunc
def validate_date(value, T, /):
    if isinstance(value, str):
        return date_fromisoformat(value)
    return default_validator(value, T)


@cython.cfunc
def validate_datetime(value, T, /):
    if isinstance(value, str):
        return datetime_fromisoformat(value)
    return default_validator(value, T)


@cython.cfunc
def validate_typevar(value, T, /):
    return value


@cython.cfunc
def validate_type_wrapper(value, T, /):
    if type(value) == T:
        return value
    return T(get_validator(T._cwtch_T)(value, T._cwtch_T))


@cython.cfunc
def default_validator(value, T, /):
    if getattr(T, "__bases__", None) is None:
        raise TypeError(f"{T} is not a type")
    value = getattr(value, "_cwtch_o", value)
    if getattr(T, "__origin__", None) is None and isinstance(value, T):
        return value
    return T(value)


def __():
    validators_map = {}

    validators_map[None] = validate_none
    validators_map[None.__class__] = validate_none
    validators_map[type] = validate_type
    validators_map[int] = validate_int
    validators_map[float] = validate_float
    validators_map[str] = validate_str
    validators_map[bytes] = validate_bytes
    validators_map[bool] = validate_bool
    validators_map[list] = validate_list
    validators_map[tuple] = validate_tuple
    validators_map[_TupleType] = validate_tuple
    validators_map[set] = validate_set
    validators_map[dict] = validate_dict
    validators_map[Mapping] = validate_mapping
    validators_map[_AnyMeta] = validate_any
    validators_map[_AnnotatedAlias] = validate_annotated
    validators_map[GenericAlias] = validate_generic_alias
    validators_map[_GenericAlias] = validate_generic_alias
    validators_map[_SpecialGenericAlias] = validate_generic_alias
    validators_map[_LiteralGenericAlias] = validate_literal
    validators_map[_CallableType] = validate_callable
    validators_map[types.UnionType] = validate_union
    validators_map[typing.Union] = validate_union
    validators_map[_UnionGenericAlias] = validate_union
    validators_map[ABCMeta] = validate_abcmeta
    validators_map[datetime.datetime] = validate_datetime
    validators_map[datetime.date] = validate_date
    validators_map[TypeVar] = validate_typevar
    validators_map[TypeWrapperMeta] = validate_type_wrapper

    validators_map_get = validators_map.get

    # @functools.cache
    def get_validator(T: Type, /) -> Callabel[[Any, Type], Any]:
        return validators_map_get(T) or validators_map_get(T.__class__) or default_validator

    def validate_value_using_validator(value: Any, T: Type, validator: Callable[[Any, Type], Any]):
        try:
            return validator(value, T)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise ValidationError(value, T, [e])

    def validate_value(value: Any, T: Type):
        try:
            return get_validator(T)(value, T)
        except ValidationError as e:
            raise e
        except Exception as e:
            raise ValidationError(value, T, [e])

    def register_validator(T: Type, validator: Callable[[Any, Type], Any], force: bool | None = None):
        if T in validators_map and not force:
            raise Exception(f"validator for '{T}' already registered")
        validators_map[T] = validator
        get_validator.cache_clear()

    def make_json_schema(
        T,
        ref_builder=lambda T: f"#/$defs/{getattr(T, '__origin__', T).__name__}",
        context=None,
        default=None,
    ) -> tuple[dict, dict]:
        if builder := getattr(T, "__cwtch_json_schema__", None):
            schema = builder(context=context)
            for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
                schema.update(metadata.json_schema())
            return schema, {}
        if builder := get_json_schema_builder(T):
            return builder(T, ref_builder=ref_builder, context=context, default=default)
        if default:
            return default(T, ref_builder=ref_builder, context=context, default=default)
        raise Exception(f"missing json schema builder for {T}")

    def make_json_schema_none(T, ref_builder=None, context=None, default=None):
        return {"type": "null"}, {}

    def make_json_schema_enum(T, ref_builder=None, context=None, default=None):
        return {"enum": [f"{v}" for v in T.__members__.values()]}, {}

    def make_json_schema_int(T, ref_builder=None, context=None, default=None):
        schema = {"type": "integer"}
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        return schema, {}

    def make_json_schema_float(T, ref_builder=None, context=None, default=None):
        schema = {"type": "number"}
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        return schema, {}

    def make_json_schema_str(T, ref_builder=None, context=None, default=None):
        schema = {"type": "string"}
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        return schema, {}

    def make_json_schema_bool(T, ref_builder=None, context=None, default=None):
        return {"type": "boolean"}, {}

    def make_json_schema_annotated(T, ref_builder=None, context=None, default=None):
        schema, refs = make_json_schema(T.__origin__, ref_builder=ref_builder, context=context, default=default)
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        if getattr(T.__origin__, "__origin__", None) is None:
            for metadata in filter(lambda item: isinstance(item, Doc), getattr(T, "__metadata__", ())):
                schema["description"] = metadata.documentation
        return schema, refs

    def make_json_schema_union(T, ref_builder=None, context=None, default=None):
        schemas = []
        refs = {}
        for arg in T.__args__:
            if arg == UnsetType:
                continue
            arg_schema, arg_refs = make_json_schema(arg, ref_builder=ref_builder, context=context, default=default)
            schemas.append(arg_schema)
            refs.update(arg_refs)
        if len(schemas) > 1:
            return {"anyOf": schemas}, refs
        return schemas[0], refs

    def make_json_schema_list(T, ref_builder=None, context=None, default=None):
        schema = {"type": "array"}
        refs = {}
        if hasattr(T, "__args__"):
            items_schema, refs = make_json_schema(
                T.__args__[0], ref_builder=ref_builder, context=context, default=default
            )
            schema["items"] = items_schema
        return schema, refs

    def make_json_schema_tuple(T, ref_builder=None, context=None, default=None):
        schema = {"type": "array", "items": False}
        refs = {}
        if hasattr(T, "__args__"):
            schema["prefixItems"] = []
            for arg in T.__args__:
                if arg == ...:
                    raise Exception("Ellipsis is not supported")
                arg_schema, arg_refs = make_json_schema(arg, ref_builder=ref_builder, context=context, default=default)
                schema["prefixItems"].append(arg_schema)
                refs.update(arg_refs)
        return schema, refs

    def make_json_schema_set(T, ref_builder=None, context=None, default=None):
        schema = {"type": "array", "uniqueItems": True}
        refs = {}
        if hasattr(T, "__args__"):
            items_schema, refs = make_json_schema(
                T.__args__[0], ref_builder=ref_builder, context=context, default=default
            )
            schema["items"] = items_schema
        return schema, refs

    def make_json_schema_dict(T, ref_builder=None, context=None, default=None):
        return {"type": "object"}, {}

    def make_json_schema_literal(T, ref_builder=None, context=None, default=None):
        return {"enum": list(T.__args__)}, {}

    def make_json_schema_datetime(T, ref_builder=None, context=None, default=None):
        return {"type": "string", "format": "date-time"}, {}

    def make_json_schema_date(T, ref_builder=None, context=None, default=None):
        return {"type": "string", "format": "date"}, {}

    def make_json_schema_uuid(T, ref_builder=None, context=None, default=None):
        return {"type": "string", "format": "uuid"}, {}

    def make_json_schema_generic_alias(T, ref_builder=None, context=None, default=None):
        if builder := get_json_schema_builder(T.__origin__):
            return builder(T, ref_builder=ref_builder, context=context, default=default)
        if default:
            return default(T, ref_builder=ref_builder, context=context, default=default)
        raise Exception(f"missing json schema builder for {T}")

    def make_json_schema_type(T, ref_builder=None, context=None, default=None):
        origin = getattr(T, "__origin__", T)
        if hasattr(origin, "__cwtch_model__"):
            return make_json_schema_cwtch(T, ref_builder=ref_builder, context=context, default=default)
        raise Exception(f"missing json schema builder for {T}")

    def make_json_schema_cwtch(T, ref_builder=None, context=None, default=None):
        schema = {"type": "object"}
        refs = {}
        properties = {}
        required = []
        origin = getattr(T, "__origin__", T)
        for f in origin.__dataclass_fields__.values():
            tp = f.type
            f_schema, f_refs = make_json_schema(tp, ref_builder=ref_builder, context=context, default=default)
            properties[f.name] = f_schema
            refs.update(f_refs)
            if f.default == _MISSING:
                required.append(f.name)
        if properties:
            schema["properties"] = properties
        if required:
            schema["required"] = required
        if ref_builder:
            ref = ref_builder(T)
            name = ref.rsplit("/", 1)[-1]
            refs[name] = schema
            return {"$ref": ref}, refs
        return schema, refs

    json_schema_builders_map = {}
    json_schema_builders_map[None] = make_json_schema_none
    json_schema_builders_map[None.__class__] = make_json_schema_none
    json_schema_builders_map[Enum] = make_json_schema_enum
    json_schema_builders_map[EnumType] = make_json_schema_enum
    json_schema_builders_map[int] = make_json_schema_int
    json_schema_builders_map[float] = make_json_schema_float
    json_schema_builders_map[str] = make_json_schema_str
    json_schema_builders_map[bool] = make_json_schema_bool
    json_schema_builders_map[type] = make_json_schema_type
    json_schema_builders_map[list] = make_json_schema_list
    json_schema_builders_map[tuple] = make_json_schema_tuple
    json_schema_builders_map[set] = make_json_schema_set
    json_schema_builders_map[dict] = make_json_schema_dict
    json_schema_builders_map[Mapping] = make_json_schema_dict
    json_schema_builders_map[_AnnotatedAlias] = make_json_schema_annotated
    json_schema_builders_map[GenericAlias] = make_json_schema_generic_alias
    json_schema_builders_map[_GenericAlias] = make_json_schema_generic_alias
    json_schema_builders_map[_SpecialGenericAlias] = make_json_schema_generic_alias
    json_schema_builders_map[_LiteralGenericAlias] = make_json_schema_literal
    json_schema_builders_map[types.UnionType] = make_json_schema_union
    json_schema_builders_map[typing.Union] = make_json_schema_union
    json_schema_builders_map[_UnionGenericAlias] = make_json_schema_union
    json_schema_builders_map[datetime.datetime] = make_json_schema_datetime
    json_schema_builders_map[datetime.date] = make_json_schema_date
    json_schema_builders_map[UUID] = make_json_schema_uuid

    @functools.cache
    def get_json_schema_builder(T, /):
        return json_schema_builders_map.get(T) or json_schema_builders_map.get(T.__class__)

    def register_json_schema_builder(T, builder, force: bool | None = None):
        if T in json_schema_builders_map and not force:
            raise Exception(f"json schema builder for '{T}' already registered")
        json_schema_builders_map[T] = builder
        get_json_schema_builder.cache_clear()

    def asdict(
        inst,
        include_=None,
        exclude_=None,
        exclude_none=None,
        exclude_unset=None,
        context=None,
    ):
        kwds = AsDictKwds(
            include_,
            exclude_,
            exclude_none,
            exclude_unset,
            context,
        )
        if inst_asdict := getattr(inst, "__cwtch_asdict__", None):
            return inst_asdict(asdict_root_handler, kwds)
        return asdict_root_handler(inst, kwds)

    return (
        get_validator,
        validate_value,
        validate_value_using_validator,
        register_validator,
        get_json_schema_builder,
        make_json_schema,
        register_json_schema_builder,
        asdict,
    )


(
    get_validator,
    validate_value,
    validate_value_using_validator,
    register_validator,
    get_json_schema_builder,
    make_json_schema,
    register_json_schema_builder,
    asdict,
) = __()


def dumps_json(obj, encoder, context, omit_microseconds: bool | None = None) -> bytes:
    option = orjson.OPT_PASSTHROUGH_SUBCLASS
    if omit_microseconds:
        option |= orjson.OPT_OMIT_MICROSECONDS

    if encoder:

        def _encoder(obj):
            if (handler := getattr(obj, "__cwtch_asjson__", None)) is not None:
                return handler(context=context)
            if isinstance(obj, UUID):
                return f"{obj}"
            if isinstance(obj, datetime.date):
                return obj.isoformat()
            if isinstance(obj, (datetime.datetime, datetime.time)):
                return obj.isoformat(timespec="seconds")
            return encoder(obj)

    else:

        def _encoder(obj):
            if (handler := getattr(obj, "__cwtch_asjson__", None)) is not None:
                return handler(context=context)
            if isinstance(obj, UUID):
                return f"{obj}"
            if isinstance(obj, datetime.date):
                return obj.isoformat()
            if isinstance(obj, (datetime.datetime, datetime.time)):
                return obj.isoformat(timespec="seconds")
            raise TypeError

    return orjson.dumps(obj, default=_encoder, option=option)
