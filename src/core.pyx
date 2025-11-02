# cython: language_level=3
# cython: profile=False
# distutils: language=c

import functools
import types
import typing

import datetime

from abc import ABCMeta
from collections import namedtuple
from collections.abc import Mapping
from contextvars import ContextVar
from enum import Enum, EnumType
from inspect import _ParameterKind, isclass, signature
from itertools import chain
from types import UnionType, WrapperDescriptorType
from typing import (
    Any,
    Generic,
    GenericAlias,
    NewType,
    Type,
    TypeVar,
    Union,
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

from . import utils
from .errors import ValidationError

from cpython.list cimport PyList_New, PyList_SET_ITEM
from cpython.object cimport PyObject_Call
from cpython.ref cimport Py_INCREF
from cpython.tuple cimport PyTuple_New, PyTuple_SET_ITEM


__all__ = (
    "get_validator",
    "validate_value",
    "register_validator",
    "get_json_schema_builder",
    "make_json_schema",
    "register_json_schema_builder",
    "asdict",
)


T = TypeVar("T")


_CACHE = cython.declare(cython.object, ContextVar("cache", default={}))
_CACHE_get = cython.declare(cython.object, _CACHE.get)


def get_cache():
    return _CACHE.get()


def nop(v: Any) -> Any:
    """No-op function."""

    return v


BOOL_MAP = cython.declare(
    cython.object,
    {
        True: True,
        1: True,
        "1": True,
        "t": True,
        "true": True,
        "True": True,
        "TRUE": True,
        "y": True,
        "Y": True,
        "yes": True,
        "Yes": True,
        "YES": True,
        False: False,
        0: False,
        "0": False,
        "f": False,
        "false": False,
        "False": False,
        "FALSE": False,
        "n": False,
        "N": False,
        "no": False,
        "No": False,
        "NO": False,
    },
)


datetime_datetime = cython.declare(cython.object, datetime.datetime)
datetime_date = cython.declare(cython.object, datetime.date)
datetime_time = cython.declare(cython.object, datetime.time)

datetime_fromisoformat = cython.declare(cython.object, datetime_datetime.fromisoformat)
date_fromisoformat = cython.declare(cython.object, datetime_date.fromisoformat)


class _MissingType:
    """
    Type to mark value as missing.
    Internal use only.
    """

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
    """
    Type to mark value has `default` or `default factory`.
    Internal use only.
    """

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


Unset = T | UnsetType


UNSET = UnsetType()


AsDictKwds = namedtuple("AsDictKwds", ("include", "exclude", "exclude_none", "exclude_unset", "context"))


def _check_cwtch_asjson_signature(fn):
    sig = signature(fn)
    if len(sig.parameters) < 2:
        raise TypeError("invalid signature for __cwtch_asjson__ method")
    it = iter(sig.parameters.values())
    p = next(it)
    if p.kind not in (_ParameterKind.POSITIONAL_ONLY, _ParameterKind.POSITIONAL_OR_KEYWORD):
        raise TypeError("invalid signature for __cwtch_asjson__ method")
    p = next(it)
    if p.kind == _ParameterKind.POSITIONAL_OR_KEYWORD:
        if p.name != "context":
            raise TypeError("invalid signature for __cwtch_asjson__ method")
    elif p.kind != _ParameterKind.VAR_KEYWORD:
        raise TypeError("invalid signature for __cwtch_asjson__ method")
    try:
        p = next(it)
    except StopIteration:
        return
    if p.kind != _ParameterKind.VAR_KEYWORD:
        raise TypeError("invalid signature for __cwtch_asjson__ method")


class TypeWrapperMeta(type):
    def __new__(cls, name, bases, ns):
        ns["_cwtch_T"] = ns["__orig_bases__"][0].__args__[0]

        if "__cwtch_asjson__" in ns:
            _check_cwtch_asjson_signature(ns["__cwtch_asjson__"])

        class Desc:
            __slots__ = ("k", "v")

            def __init__(self, k, v):
                self.k = k
                self.v = v

            def __get__(self, instance, owner=None):
                if instance is not None:
                    o = getattr(instance, "_cwtch_o", None)
                    return getattr(o, self.k)
                return self.v

        ns.update(
            {
                k: Desc(k, getattr(ns["_cwtch_T"], k, v))
                for k, v in getattr(ns["_cwtch_T"], "__dict__", {}).items()
                if type(v) == WrapperDescriptorType and k not in ["__new__", "__init__", "__getattribute__"]
            }
        )

        def __hash__(self):
            return hash(ns["_cwtch_T"])

        ns["__hash__"] = __hash__

        return super().__new__(cls, name, bases, ns)

    def __getattr__(self, name):
        return getattr(self._cwtch_T, name)

    def __subclasscheck__(cls, subclass):
        return issubclass(subclass, cls._cwtch_T)

    def __instancecheck__(self, instance):
        return isinstance(instance, self._cwtch_T)


class TypeWrapper(Generic[T], metaclass=TypeWrapperMeta):
    """Class to wrap any type for adding __cwtch_asdict__, __cwtch_asjson__ or __cwtch_json_schema__ methods."""

    def __init__(self, o):
        object.__setattr__(self, "_cwtch_o", o)

    def __getattribute__(self, name):
        object_getattribute = object.__getattribute__
        if name in object_getattribute(self, "__dict__"):
            return object_getattribute(self, name)
        if name in object_getattribute(self, "__class__").__dict__:
            return object_getattribute(self, name)
        return getattr(object_getattribute(self, "_cwtch_o"), name)

    def __call__(self, *args, **kwds):
        return object.__getattribute__(self, "_cwtch_o")(*args, **kwds)

    def __eq__(self, *args, **kwds):
        return object.__getattribute__(self, "_cwtch_o").__eq__(*args, **kwds)

    def __ne__(self, *args, **kwds):
        return object.__getattribute__(self, "_cwtch_o").__ne__(*args, **kwds)


@cython.cclass
class TypeMetadata:
    """Base class for type metadata."""

    @cython.ccall
    def json_schema(self):
        return {}


@cython.cclass
class ValidatorBefore(TypeMetadata):
    @cython.ccall
    def before(self, value):
        return value


@cython.cclass
class ValidatorAfter(TypeMetadata):
    @cython.ccall
    def after(self, value):
        return value


@cython.cclass
class _Ge(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if value >= self.value:
            return value
        raise ValueError(f"value should be >= {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _Gt(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if value > self.value:
            return value
        raise ValueError(f"value should be > {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _Le(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if value <= self.value:
            return value
        raise ValueError(f"value should be <= {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _Lt(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if value < self.value:
            return value
        raise ValueError(f"value should be < {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _MinLen(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if len(value) >= self.value:
            return value
        raise ValueError(f"value length should be >= {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _MaxLen(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if len(value) <= self.value:
            return value
        raise ValueError(f"value length should be <= {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _Len(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if len(value) < self.min_value:
            raise ValueError(f"value length should be >= {self.min_value}")
        if len(value) > self.max_value:
            raise ValueError(f"value length should be  {self.max_value}")
        return value

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _MinItems(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if len(value) >= self.value:
            return value
        raise ValueError(f"items count should be >= {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _MaxItems(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if len(value) <= self.value:
            return value
        raise ValueError(f"items count should be <= {self.value}")

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _ToLowerB(ValidatorBefore):
    @cython.inline
    @cython.cfunc
    def c_before(self, value):
        if self.mode == "before":
            return value.lower()
        return value

    @cython.ccall
    def before(self, value):
        return self.c_before(value)


@cython.cclass
class _ToLowerA(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if self.mode == "after":
            return value.lower()
        return value

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


@cython.cclass
class _ToUpperB(ValidatorBefore):
    @cython.inline
    @cython.cfunc
    def c_before(self, value):
        if self.mode == "before":
            return value.upper()
        return value

    @cython.ccall
    def before(self, value):
        return self.c_before(value)


@cython.cclass
class _ToUpperA(ValidatorAfter):
    @cython.inline
    @cython.cfunc
    def c_after(self, value):
        if self.mode == "after":
            return value.upper()
        return value

    @cython.ccall
    def after(self, value):
        return self.c_after(value)


def type_adapter(T):
    if hasattr(T, "__metadata__"):
        before, after = [], []
        for x in T.__metadata__:
            if isinstance(x, ValidatorBefore) and x.before != nop:
                before.append(x)
            if isinstance(x, ValidatorAfter) and x.after != nop:
                after.append(x)
        T.__dict__["__cwtch_metadata__"] = (tuple(before), tuple(after), get_validator(T.__origin__), T.__origin__)
    elif hasattr(T, "__args__"):
        t = getattr(T, "__origin__", T)
        if t.__class__ == UnionType:
            t = Union
        T = utils.make_type_with_args(t, [type_adapter(arg) for arg in T.__args__])

    return T


def asdict_handler(inst, kwds):
    fields = getattr(inst, "__dataclass_fields__", None)

    if fields is None:
        return inst

    data = {}

    keys = tuple(fields.keys()) + inst.__cwtch_extra_fields__

    exclude_unset = kwds.exclude_unset
    exclude_none = kwds.exclude_none

    if exclude_unset or exclude_none:
        for k in keys:
            v = getattr(inst, k, None)
            if exclude_unset and v is UNSET:
                continue
            if exclude_none and v is None:
                continue
            if k in fields:
                field_alias = fields[k].asdict_alias
                if field_alias is not UNSET:
                    k = field_alias
            if isinstance(v, (int, str, float, bool)) and getattr(v, "__cwtch_asjson__", None) is None:
                data[k] = v
            elif isinstance(v, list):
                data[k] = [x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v]
            elif isinstance(v, dict):
                data[k] = {
                    kk: vv if isinstance(vv, (int, str, float, bool)) else _asdict_handler(vv, kwds)
                    for kk, vv in v.items()
                }
            elif isinstance(v, tuple):
                data[k] = tuple([x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v])
            elif isinstance(v, set):
                data[k] = {x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v}
            else:
                v = _asdict_handler(v, kwds)
                if exclude_unset and v is UNSET:
                    continue
                if exclude_none and v is None:
                    continue
                data[k] = v
    else:
        for k in keys:
            v = getattr(inst, k, None)
            if k in fields:
                field_alias = fields[k].asdict_alias
                if field_alias is not UNSET:
                    k = field_alias
            if isinstance(v, (int, str, float, bool)) and getattr(v, "__cwtch_asjson__", None) is None:
                data[k] = v
            elif isinstance(v, list):
                data[k] = [x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v]
            elif isinstance(v, dict):
                data[k] = {
                    kk: vv if isinstance(vv, (int, str, float, bool)) else _asdict_handler(vv, kwds)
                    for kk, vv in v.items()
                }
            elif isinstance(v, tuple):
                data[k] = tuple([x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v])
            elif isinstance(v, set):
                data[k] = {x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, kwds) for x in v}
            else:
                data[k] = _asdict_handler(v, kwds)

    return data


def _asdict_handler(inst, kwds):
    inst_asdict = getattr(inst, "__cwtch_asdict__", None)
    if inst_asdict:
        return inst_asdict(asdict_handler, kwds)
    return asdict_handler(inst, kwds)


@cython.inline
@cython.ccall
def _asdictkwds(kwds):
    return AsDictKwds(UNSET, UNSET, kwds[2], kwds[3], kwds[4])


def asdict_root_handler(inst, kwds):
    is_cwtch_model: cython.int = 0

    fields = getattr(inst, "__dataclass_fields__", None)

    keys = fields
    if keys is None:
        if isinstance(inst, dict):
            keys = inst
        else:
            raise Exception(f"expect cwtch model or dict")
    else:
        is_cwtch_model = 1
        keys = tuple(keys.keys()) + inst.__cwtch_extra_fields__

    use_inc_cond: cython.int = 0
    use_exc_cond: cython.int = 0

    if kwds[0] is not None:
        use_inc_cond = 1
        inc = kwds[0]
    if kwds[1] is not None:
        use_exc_cond = 1
        exc = kwds[1]

    data = {}

    exclude_unset = kwds.exclude_unset
    exclude_none = kwds.exclude_none

    if exclude_unset or exclude_none:
        for k in keys:
            if use_inc_cond and not k in inc:
                continue
            if use_exc_cond and k in exc:
                continue
            v = getattr(inst, k, None)
            if exclude_unset and v is UNSET:
                continue
            if exclude_none and v is None:
                continue
            if is_cwtch_model:
                if k in fields:
                    field_alias = fields[k].asdict_alias
                    if field_alias is not UNSET:
                        k = field_alias
            if isinstance(v, (int, str, float, bool)) and getattr(v, "__cwtch_asjson__", None) is None:
                data[k] = v
            elif isinstance(v, list):
                data[k] = [
                    x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, _asdictkwds(kwds)) for x in v
                ]
            elif isinstance(v, dict):
                data[k] = {
                    kk: vv if isinstance(vv, (int, str, float, bool)) else _asdict_handler(vv, _asdictkwds(kwds))
                    for kk, vv in v.items()
                }
            elif isinstance(v, tuple):
                data[k] = tuple(
                    [x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, _asdictkwds(kwds)) for x in v]
                )
            elif isinstance(v, set):
                data[k] = {
                    x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, _asdictkwds(kwds)) for x in v
                }
            else:
                v = _asdict_handler(v, _asdictkwds(kwds))
                if exclude_unset and v is UNSET:
                    continue
                if exclude_none and v is None:
                    continue
                data[k] = v
    else:
        for k in keys:
            if use_inc_cond and not k in inc:
                continue
            if use_exc_cond and k in exc:
                continue
            v = getattr(inst, k, None)
            if is_cwtch_model:
                if k in fields:
                    field_alias = fields[k].asdict_alias
                    if field_alias is not UNSET:
                        k = field_alias
            if isinstance(v, (int, str, float, bool)) and getattr(v, "__cwtch_asjson__", None) is None:
                data[k] = v
            elif isinstance(v, list):
                data[k] = [
                    x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, _asdictkwds(kwds)) for x in v
                ]
            elif isinstance(v, dict):
                data[k] = {
                    kk: vv if isinstance(vv, (int, str, float, bool)) else _asdict_handler(vv, _asdictkwds(kwds))
                    for kk, vv in v.items()
                }
            elif isinstance(v, tuple):
                data[k] = tuple(
                    [x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, _asdictkwds(kwds)) for x in v]
                )
            elif isinstance(v, set):
                data[k] = {
                    x if isinstance(x, (int, str, float, bool)) else _asdict_handler(x, _asdictkwds(kwds)) for x in v
                }
            else:
                data[k] = _asdict_handler(v, _asdictkwds(kwds))

    return data


def validate_any(value, T, /):
    return value


@cython.inline
@cython.ccall
def validate_none(value, T):
    if value is not None:
        raise ValueError("value is not a None")


@cython.inline
@cython.ccall
def validate_bool(value, T):
    if isinstance(value, bool):
        return value
    v = BOOL_MAP.get(value)
    if v is not None:
        return v
    raise ValueError("could not convert value to bool")


@cython.inline
@cython.ccall
def validate_int(value, T):
    return int(value)


@cython.inline
@cython.ccall
def validate_float(value, T):
    return float(value)


@cython.inline
@cython.ccall
def validate_str(value, T):
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode()
    raise ValueError(f"value is not a valid {T}")


@cython.inline
@cython.ccall
def validate_bytes(value, T):
    if isinstance(value, str):
        return value.encode()
    return bytes(value)


empty_args = cython.declare(cython.object, ())


@cython.cfunc
def _validate_type(value, T, origin, fields, handle_circular_refs, cache):
    value = getattr(value, "_cwtch_o", value)
    if origin == T and isinstance(value, origin):
        return value
    if fields is not None:
        if handle_circular_refs:
            cache_key = (T, id(value))
            cache_value = cache.get(cache_key)
            if cache_value is not None:
                return cache_value if not cache["reset_circular_refs"] else UNSET
        if isinstance(value, dict):
            return PyObject_Call(origin, empty_args, value)
        kwds = {f_name: v for f_name in fields if (v := getattr(value, f_name, _MISSING)) is not _MISSING}
        return PyObject_Call(origin, empty_args, value)
    if origin == type:
        if type(value) != type:
            raise ValueError(f"value should be a type")
        if (args := getattr(T, "__args__", None)) is not None:
            arg = T.__args__[0]
            if getattr(arg, "__base__", None) is None or not issubclass(value, arg):
                raise ValueError(f"invalid value for {T}".replace("typing.", ""))
        return value
    if isclass(origin) and getattr(origin, "__cwtch_type_config__", {}).get("strict_validation") is not True:
        if origin.__module__ == "builtins" or type(value) in origin.__bases__:
            return origin(value)
        if issubclass(origin, (UUID, datetime_datetime, datetime_date, datetime_time)):
            return origin(value)
    raise ValueError(f"invalid value for {T}".replace("typing.", ""))


@cython.ccall
def validate_type(value, T):
    origin = getattr(T, "__origin__", T)
    fields = getattr(origin, "__dataclass_fields__", None)
    handle_circular_refs = getattr(origin, "__cwtch_handle_circular_refs__", None)
    if handle_circular_refs:
        cache = _CACHE_get()
    else:
        cache = None
    return _validate_type(value, T, origin, fields, handle_circular_refs, cache)


@cython.inline
@cython.ccall
def validate_unset(value, T):
    if value != UNSET:
        raise ValueError(f"value is not a valid {T}")
    return value


def validate_list(value, T, /):
    result: cython.object
    n: cython.Py_ssize_t
    i: cython.Py_ssize_t = 0
    x: cython.object
    is_list: cython.bint = isinstance(value, list)

    if is_list or isinstance(value, (tuple, set)):
        T_args = getattr(T, "__args__", None)

        if T_args is not None:
            try:
                T_arg = T_args[0]

                if T_arg == int:
                    n = len(value)
                    result = PyList_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_int(x, int)
                        PyList_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == str:
                    n = len(value)
                    result = PyList_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_str(x, str)
                        PyList_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == float:
                    n = len(value)
                    result = PyList_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_float(x, float)
                        PyList_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == bool:
                    n = len(value)
                    result = PyList_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_bool(x, bool)
                        PyList_SET_ITEM(result, i, v)
                        i += 1
                    return result

                if T_arg == bytes:
                    n = len(value)
                    result = PyList_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_bytes(x, bytes)
                        PyList_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == Any:
                    if is_list:
                        return value
                    n = len(value)
                    result = PyList_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        PyList_SET_ITEM(result, i, x)
                        Py_INCREF(x)
                        i += 1
                    return result

                validator = get_validator(T_arg)

                n = len(value)
                result = PyList_New(n)
                if result is None:
                    raise MemoryError

                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    fields = getattr(origin, "__dataclass_fields__", None)
                    handle_circular_refs = getattr(origin, "__cwtch_handle_circular_refs__", None)
                    if handle_circular_refs:
                        cache = _CACHE_get()
                    else:
                        cache = None
                    for x in value:
                        v = _validate_type(x, T_arg, origin, fields, handle_circular_refs, cache)
                        PyList_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                for x in value:
                    v = validator(x, T_arg)
                    PyList_SET_ITEM(result, i, v)
                    Py_INCREF(v)
                    i += 1
                return result

            except (TypeError, ValueError) as e:
                path = [i]
                if "x" in locals():
                    raise ValidationError(value, T, [ValidationError(x, T_arg, [e])], path=path)
                raise ValidationError(value, T, [e], path=path)
            except ValidationError as e:
                path = [i] + (e.path or [])
                raise ValidationError(value, T, [e], path=path)

        if is_list:
            return value

        n = len(value)
        result = PyList_New(n)
        if result is None:
            raise MemoryError
        for x in value:
            PyList_SET_ITEM(result, i, x)
            Py_INCREF(x)
            i += 1
        return result

    raise ValueError(f"invalid value for {T}".replace("typing.", ""))


def validate_tuple(value, T, /):
    result: cython.object
    n: cython.Py_ssize_t
    i: cython.Py_ssize_t = 0
    x: cython.object
    is_tuple: cython.bint = isinstance(value, tuple)

    if is_tuple or isinstance(value, (list, set)):
        n = len(value)

        T_args = getattr(T, "__args__", None)

        if T_args is not None:
            try:
                if T_args[-1] != Ellipsis:
                    if n == len(T_args):
                        result = PyTuple_New(n)
                        if result is None:
                            raise MemoryError
                        for x, T_arg in zip(value, T_args):
                            if T_arg == int:
                                v = validate_int(x, int)
                            elif T_arg == str:
                                v = validate_str(x, str)
                            elif T_arg == float:
                                v = validate_float(x, float)
                            elif T_arg == bool:
                                v = validate_bool(x, bool)
                            elif T_arg == bytes:
                                v = validate_bool(x, bytes)
                            elif T_arg == Any:
                                pass
                            else:
                                validator = get_validator(T_arg)
                                if validator == validate_type:
                                    v = validate_type(x, T_arg)
                                else:
                                    v = validator(x, T_arg)
                            PyTuple_SET_ITEM(result, i, v)
                            Py_INCREF(v)
                            i += 1
                        return result
                    raise ValueError(f"invalid arguments count for {T}")

                if len(T_args) != 2:
                    raise TypeError("variable tuple must have only one type")

                T_arg = T_args[0]

                if T_arg == int:
                    result = PyTuple_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_int(x, int)
                        PyTuple_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == str:
                    result = PyTuple_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_str(x, str)
                        PyTuple_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == float:
                    result = PyTuple_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_float(x, float)
                        PyTuple_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == bool:
                    result = PyTuple_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_bool(x, bool)
                        PyTuple_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == bytes:
                    result = PyTuple_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        v = validate_bytes(x, bytes)
                        PyTuple_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                if T_arg == Any:
                    if is_tuple:
                        return value
                    result = PyTuple_New(n)
                    if result is None:
                        raise MemoryError
                    for x in value:
                        PyTuple_SET_ITEM(result, i, x)
                        Py_INCREF(x)
                        i += 1
                    return result

                validator = get_validator(T_arg)

                result = PyTuple_New(n)
                if result is None:
                    raise MemoryError

                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    fields = getattr(origin, "__dataclass_fields__", None)
                    handle_circular_refs = getattr(origin, "__cwtch_handle_circular_refs__", None)
                    if handle_circular_refs:
                        cache = _CACHE_get()
                    else:
                        cache = None
                    for x in value:
                        v = _validate_type(x, T_arg, origin, fields, handle_circular_refs, cache)
                        PyTuple_SET_ITEM(result, i, v)
                        Py_INCREF(v)
                        i += 1
                    return result

                for x in value:
                    v = validator(x, T_arg)
                    PyTuple_SET_ITEM(result, i, v)
                    Py_INCREF(v)
                    i += 1
                return result

            except (TypeError, ValueError) as e:
                path = [i]
                if "x" in locals():
                    raise ValidationError(value, T, [ValidationError(x, T_arg, [e])], path=path)
                raise ValidationError(value, T, [e], path=path)
            except ValidationError as e:
                path = [i] + (e.path or [])
                raise ValidationError(value, T, [e], path=path)

        if is_tuple:
            return value

        result = PyTuple_New(n)
        if result is None:
            raise MemoryError
        for x in value:
            PyTuple_SET_ITEM(result, i, x)
            Py_INCREF(x)
            i += 1
        return result

    raise ValueError(f"invalid value for {T}".replace("typing.", ""))


def validate_set(value, T, /):
    result: cython.object = set()
    i: cython.Py_ssize_t = 0
    x: cython.object
    is_set: cython.bint = isinstance(value, set)

    if is_set or isinstance(value, (list, tuple)):
        T_args = getattr(T, "__args__", None)

        if T_args is not None:
            try:
                T_arg = T_args[0]

                if T_arg == int:
                    for x in value:
                        v = validate_int(x, int)
                        result.add(v)
                        i += 1
                    return result

                if T_arg == str:
                    for x in value:
                        v = validate_str(x, str)
                        result.add(v)
                        i += 1
                    return result

                if T_arg == float:
                    for x in value:
                        v = validate_float(x, float)
                        result.add(v)
                        i += 1
                    return result

                if T_arg == bool:
                    for x in value:
                        v = validate_bool(x, bool)
                        result.add(v)
                        i += 1
                    return result

                if T_arg == bytes:
                    for x in value:
                        v = validate_bytes(x, bytes)
                        result.add(v)
                        i += 1
                    return result

                validator = get_validator(T_arg)

                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    fields = getattr(origin, "__dataclass_fields__", None)
                    handle_circular_refs = getattr(origin, "__cwtch_handle_circular_refs__", None)
                    if handle_circular_refs:
                        cache = _CACHE_get()
                    else:
                        cache = None
                    for x in value:
                        v = _validate_type(x, T_arg, origin, fields, handle_circular_refs, cache)
                        result.add(v)
                        i += 1
                    return result

                for x in value:
                    v = validator(x, T_arg)
                    result.add(v)
                    i += 1
                return result

            except (TypeError, ValueError) as e:
                path = [i]
                if "x" in locals():
                    raise ValidationError(value, T, [ValidationError(x, T_arg, [e])], path=path)
                raise ValidationError(value, T, [e], path=path)
            except ValidationError as e:
                path = [i] + (e.path or [])
                raise ValidationError(value, T, [e], path=path)

        if is_set:
            return value

        for x in value:
            result.add(x)
        return result

    raise ValueError(f"invalid value for {T}".replace("typing.", ""))


def validate_dict(value, T, /):
    if not isinstance(value, dict):
        raise ValueError(f"invalid value for {T}".replace("typing.", ""))

    T_args = getattr(T, "__args__", None)

    if T_args is not None:
        T_k, T_v = T_args
        try:
            if T_k == str:
                if T_v == int:
                    return {validate_str(k, str): validate_int(v, int) for k, v in value.items()}
                if T_v == str:
                    return {validate_str(k, str): validate_str(v, str) for k, v in value.items()}
                if T_v == float:
                    return {validate_str(k, str): validate_float(v, float) for k, v in value.items()}
                if T_v == bool:
                    return {validate_str(k, str): validate_bool(v, bool) for k, v in value.items()}
                if T_v == bytes:
                    return {validate_str(k, str): validate_bytes(v, bytes) for k, v in value.items()}
                if T_v == Any:
                    return {validate_str(k, str): v for k, v in value.items()}
                validator_v = get_validator(T_v)
                if validator_v == validate_type:
                    return {validate_str(k, str): validate_type(v, T_v) for k, v in value.items()}
                return {validate_str(k, str): validator_v(v, T_v) for k, v in value.items()}

            validator_k = get_validator(T_k)

            if T_v == int:
                return {validator_k(k, T_k): validate_int(v, int) for k, v in value.items()}
            if T_v == str:
                return {validator_k(k, T_k): validate_str(v, str) for k, v in value.items()}
            if T_v == float:
                return {validator_k(k, T_k): validate_float(v, float) for k, v in value.items()}
            if T_v == bool:
                return {validator_k(k, T_k): validate_bool(v, bool) for k, v in value.items()}
            if T_v == bytes:
                return {validator_k(k, T_k): validate_bytes(v, bytes) for k, v in value.items()}
            if T_v == Any:
                return {validator_k(k, T_k): v for k, v in value.items()}
            validator_v = get_validator(T_v)
            if validator_v == validate_type:
                return {validator_k(k, T_k): validate_type(v, T_v) for k, v in value.items()}
            return {validator_k(k, T_k): validator_v(v, T_v) for k, v in value.items()}

        except (TypeError, ValueError, ValidationError) as e:
            validator_k = get_validator(T_k)
            validator_v = get_validator(T_v)
            for k, v in value.items():
                try:
                    validator_k(k, T_k)
                except (TypeError, ValueError) as e:
                    path = ["$", k]
                    raise ValidationError(value, T, [ValidationError(k, T_k, [e])], path=path)
                except ValidationError as e:
                    path = ["$", k] + e.path
                    raise ValidationError(value, T, [e], path=path)
                try:
                    validator_v(v, T_v)
                except (TypeError, ValueError) as e:
                    path = [k]
                    raise ValidationError(value, T, [ValidationError(v, T_v, [e])], path=path)
                except ValidationError as e:
                    path = [k] + e.path
                    raise ValidationError(value, T, [e], path=path)
            raise e

    return value


def validate_mapping(value, T, /):
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid value for {T}".replace("typing.", ""))

    T_args = getattr(T, "__args__", None)

    if T_args is not None:
        T_k, T_v = T_args
        try:
            if T_k == str:
                if T_v == int:
                    return {validate_str(k, str): validate_int(v, int) for k, v in value.items()}
                if T_v == str:
                    return {validate_str(k, str): validate_str(v, str) for k, v in value.items()}
                if T_v == float:
                    return {validate_str(k, str): validate_float(v, float) for k, v in value.items()}
                if T_v == bool:
                    return {validate_str(k, str): validate_bool(v, bool) for k, v in value.items()}
                if T_v == bytes:
                    return {validate_str(k, str): validate_bytes(v, bytes) for k, v in value.items()}
                if T_v == Any:
                    return {validate_str(k, str): v for k, v in value.items()}
                validator_v = get_validator(T_v)
                if validator_v == validate_type:
                    return {validate_str(k, str): validate_type(v, T_v) for k, v in value.items()}
                return {validate_str(k, str): validator_v(v, T_v) for k, v in value.items()}

            validator_k = get_validator(T_k)

            if T_v == int:
                return {validator_k(k, T_k): validate_int(v, int) for k, v in value.items()}
            if T_v == str:
                return {validator_k(k, T_k): validate_str(v, str) for k, v in value.items()}
            if T_v == float:
                return {validator_k(k, T_k): validate_float(v, float) for k, v in value.items()}
            if T_v == bool:
                return {validator_k(k, T_k): validate_bool(v, bool) for k, v in value.items()}
            if T_v == bytes:
                return {validator_k(k, T_k): validate_bytes(v, bytes) for k, v in value.items()}
            if T_v == Any:
                return {validator_k(k, T_k): v for k, v in value.items()}
            validator_v = get_validator(T_v)
            if validator_v == validate_type:
                return {validator_k(k, T_k): validate_type(v, T_v) for k, v in value.items()}
            return {validator_k(k, T_k): validator_v(v, T_v) for k, v in value.items()}

        except (TypeError, ValueError, ValidationError) as e:
            validator_k = get_validator(T_k)
            validator_v = get_validator(T_v)
            for k, v in value.items():
                try:
                    validator_k(k, T_k)
                except (TypeError, ValueError) as e:
                    path = ["$", k]
                    raise ValidationError(value, T, [ValidationError(k, T_k, [e])], path=path)
                except ValidationError as e:
                    path = ["$", k] + e.path
                    raise ValidationError(value, T, [e], path=path)
                try:
                    validator_v(v, T_v)
                except (TypeError, ValueError) as e:
                    path = [k]
                    raise ValidationError(value, T, [ValidationError(v, T_v, [e])], path=path)
                except ValidationError as e:
                    path = [k] + e.path
                    raise ValidationError(value, T, [e], path=path)
            raise e

    return value


def validate_generic_alias(value, T, /):
    return get_validator(T.__origin__)(value, T)


def validate_callable(value, T, /):
    if callable(value):
        return value
    raise ValueError("not callable")


def validate_annotated(value, T, /):
    metadata_before, metadata_after, validator, __origin__ = T.__cwtch_metadata__

    for metadata in metadata_before:
        if isinstance(metadata, _ToLowerB):
            value = _ToLowerB.c_before(metadata, value)
        elif isinstance(metadata, _ToUpperB):
            value = _ToUpperB.c_before(metadata, value)
        else:
            value = metadata.before(value)

    value = validator(value, __origin__)

    for metadata in metadata_after:
        if isinstance(metadata, _Ge):
            value = _Ge.c_after(metadata, value)
        elif isinstance(metadata, _Le):
            value = _Le.c_after(metadata, value)
        elif isinstance(metadata, _MinLen):
            value = _MinLen.c_after(metadata, value)
        elif isinstance(metadata, _MaxLen):
            value = _MaxLen.c_after(metadata, value)
        elif isinstance(metadata, _Len):
            value = _Len.c_after(metadata, value)
        elif isinstance(metadata, _MaxItems):
            value = _MaxItems.c_after(metadata, value)
        elif isinstance(metadata, _MinItems):
            value = _MinItems.c_after(metadata, value)
        elif isinstance(metadata, _ToLowerA):
            value = _ToLowerA.c_after(metadata, value)
        elif isinstance(metadata, _ToUpperA):
            value = _ToUpperA.c_after(metadata, value)
        else:
            value = metadata.after(value)

    return value


def validate_union(value, T, /):
    T_args = T.__args__
    for T_arg in T_args:
        if getattr(T_arg, "__origin__", None) is None and (T_arg == Any or type(value) == T_arg):
            return value
    errors = []
    for T_arg in T_args:
        try:
            if T_arg == int:
                return validate_int(value, int)
            if T_arg == str:
                return validate_str(value, str)
            if T_arg == bool:
                return validate_bool(value, bool)
            if T_arg == None:
                return validate_none(value, None)
            if T_arg == UnsetType:
                return validate_unset(value, UnsetType)
            validator = get_validator(T_arg)
            if validator == validate_type:
                return validate_type(value, T_arg)
            return validator(value, T_arg)
        except ValidationError as e:
            e.__cause__ = None
            if e.value == ...:
                e.value = value
            errors.append(e)
        except Exception as e:
            err = ValidationError(value, T_arg, [e])
            err.__cause__ = None
            errors.append(err)
    raise ValidationError(value, T, errors)


def validate_literal(value, T, /):
    if value not in T.__args__:
        raise ValueError(f"value is not a one of {list(T.__args__)}")
    return value


def validate_abcmeta(value, T, /):
    if isinstance(value, getattr(T, "__origin__", T)):
        return value
    raise ValueError(f"value is not a valid {T}")


def validate_date(value, T, /):
    if isinstance(value, str):
        return date_fromisoformat(value)
    return default_validator(value, T)


def validate_datetime(value, T, /):
    if isinstance(value, str):
        return datetime_fromisoformat(value)
    return default_validator(value, T)


def validate_typevar(value, T, /):
    return value


def validate_type_wrapper(value, T, /):
    if type(value) == T:
        return value
    return T(get_validator(T._cwtch_T)(value, T._cwtch_T))


def validate_new_type(value, T, /):
    try:
        return get_validator(T.__supertype__)(value, T.__supertype__)
    except ValidationError as e:
        e.type = T
        raise e


def default_validator(value, T, /):
    if getattr(T, "__bases__", None) is None:
        raise TypeError(f"{T} is not a type")
    value = getattr(value, "_cwtch_o", value)
    if getattr(T, "__origin__", None) is None and isinstance(value, T):
        return value
    return T(value)


validators_map = cython.declare(cython.object, {})


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
validators_map[Any] = validate_any
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
validators_map[datetime_datetime] = validate_datetime
validators_map[datetime_date] = validate_date
validators_map[TypeVar] = validate_typevar
validators_map[TypeWrapperMeta] = validate_type_wrapper
validators_map[NewType] = validate_new_type
validators_map[UnsetType] = validate_unset


validators_map_get = cython.declare(cython.object, validators_map.get)


# @functools.cache
def get_validator(T: Type, /) -> Callabel[[Any, Type], Any]:
    return validators_map_get(T) or validators_map_get(T.__class__) or default_validator


def validate_value(value: Any, T: Type):
    try:
        return get_validator(T)(value, type_adapter(T))
    except ValidationError as e:
        e.__cause__ = None
        if e.value == ...:
            e.value = value
        raise e
    except Exception as e:
        err = ValidationError(value, T, [e])
        err.__cause__ = None
        raise err


def register_validator(T: Type, validator: Callable[[Any, Type], Any], force: bool | None = None):
    if (T in validators_map or T.__class__ in validators_map) and not force:
        raise Exception(f"validator for '{T}' already registered")
    validators_map[T] = validator
    validators_map[T.__class__] = validator
    # get_validator.cache_clear()


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
        items_schema, refs = make_json_schema(T.__args__[0], ref_builder=ref_builder, context=context, default=default)
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
        items_schema, refs = make_json_schema(T.__args__[0], ref_builder=ref_builder, context=context, default=default)
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


def make_json_schema_type_wrapper(T, ref_builder=None, context=None, default=None):
    if builder := get_json_schema_builder(T._cwtch_T):
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


json_schema_builders_map = cython.declare(cython.object, {})


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
json_schema_builders_map[datetime_datetime] = make_json_schema_datetime
json_schema_builders_map[datetime_date] = make_json_schema_date
json_schema_builders_map[UUID] = make_json_schema_uuid
json_schema_builders_map[TypeWrapperMeta] = make_json_schema_type_wrapper


def get_json_schema_builder(T, /):
    return json_schema_builders_map.get(T) or json_schema_builders_map.get(T.__class__)


def register_json_schema_builder(T, builder, force: bool | None = None):
    if T in json_schema_builders_map and not force:
        raise Exception(f"json schema builder for '{T}' already registered")
    json_schema_builders_map[T] = builder
    get_json_schema_builder.cache_clear()


cpdef inline asdict(
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
    inst_asdict = getattr(inst, "__cwtch_asdict__", None)
    if inst_asdict:
        return inst_asdict(asdict_root_handler, kwds)
    return asdict_root_handler(inst, kwds)


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
            if isinstance(obj, (datetime_datetime, datetime_time)):
                return obj.isoformat(timespec="seconds")
            if isinstance(obj, datetime_date):
                return obj.isoformat()
            return encoder(obj)

    else:

        def _encoder(obj):
            if (handler := getattr(obj, "__cwtch_asjson__", None)) is not None:
                return handler(context=context)
            if isinstance(obj, UUID):
                return f"{obj}"
            if isinstance(obj, (datetime_datetime, datetime_time)):
                return obj.isoformat(timespec="seconds")
            if isinstance(obj, datetime_date):
                return obj.isoformat()
            raise TypeError

    return orjson.dumps(obj, default=_encoder, option=option)


cdef class ToView:
    view_cls: object
    view_name: object
    data: object

    def __init__(self, view_cls, obj):
        self.view_cls = view_cls
        self.view_name = view_cls.__cwtch_view_name__
        self.data = obj.__dict__

    cdef dump(self, value):
        if getattr(value, "__cwtch_model__", None):
            view = getattr(value, self.view_name, None)
            if view:
                return view()
            return asdict(value)
        if isinstance(value, dict):
            return {k: self.dump(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return value.__class__(self.dump(v) for v in value)
        return value

    def __call__(self):
        kwds = {
            k: self.dump(self.data[k])
            for k in self.view_cls.__dataclass_fields__
            if k in self.data
        }
        return PyObject_Call(self.view_cls, empty_args, kwds)
