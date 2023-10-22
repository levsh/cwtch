# cython: language_level=3
# distutils: language=c

from abc import ABCMeta
from collections.abc import Iterable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import is_dataclass
from datetime import date, datetime
from functools import cache
from json import JSONDecodeError
from json import loads as json_loads
from types import UnionType
from typing import (
    Any,
    GenericAlias,
    Type,
    TypeVar,
    _AnnotatedAlias,
    _AnyMeta,
    _CallableType,
    _GenericAlias,
    _LiteralGenericAlias,
    _SpecialForm,
    _SpecialGenericAlias,
    _TupleType,
    _UnionGenericAlias,
)

import cython
from attrs import field as attrs_field

from .errors import ValidationError
from .types import UNSET

datetime_fromisoformat = datetime.fromisoformat
date_fromisoformat = date.fromisoformat

_validators_map = {}


cdef extern from "Python.h":

    object PyNumber_Long(object o)
    object PyNumber_Float(object o)
    int PyNumber_Check(object o)
    int PyUnicode_Check(object o)
    object PyObject_Call(object callable_, object args, object kwargs)


_cache = ContextVar("_cache", default={})
_cache_get = _cache.get


class Metaclass(type):
    def __subclasscheck__(self, subclass: Type):
        if isinstance(subclass, type) and getattr(subclass, "__cwtch_view_base__", None) == self:
            return True
        return super().__subclasscheck__(subclass)

    def __instancecheck__(self, instance):
        if getattr(instance, "__cwtch_view_base__", None) == self:
            return True
        return super().__instancecheck__(instance)


def _class_getitem(cls, parameters, result):
    if not isinstance(parameters, tuple):
        parameters = (parameters,)

    _parameters = dict(zip(cls.__parameters__, parameters))

    class Proxy:
        def __getattribute__(self, attr):
            if attr not in {"__call__", "__str__", "__repr__"}:
                return object.__getattribute__(cls, attr)
            return object.__getattribute__(self, attr)

        def __str__(self):
            return result.__str__()

        def __repr__(self):
            return result.__repr__()

        def __call__(self, *args, **kwds):
            _cache_get()["parameters"] = _parameters
            try:
                return result(*args, **kwds)
            finally:
                _cache_get().pop("parameters", None)

    return Proxy()


class Base(metaclass=Metaclass):
    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class BaseCache(metaclass=Metaclass):
    def __init__(self, **kwds):
        if (cache_key := kwds.pop("__cache_key", None)) is not None:
            _cache_get()[cache_key]["value"] = self
        PyObject_Call(self.__attrs_init__, (), kwds)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class BaseIgnoreExtra(metaclass=Metaclass):
    def __init__(self, **kwds):
        filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
        PyObject_Call(self.__attrs_init__, (), filtered)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class BaseCacheIgnoreExtra(metaclass=Metaclass):
    def __init__(self, **kwds):
        if cache_key := kwds.pop("__cache_key", None):
            _cache_get()[cache_key]["value"] = self
        filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
        PyObject_Call(self.__attrs_init__, (), filtered)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class ViewBase:
    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class ViewBaseCache:
    def __init__(self, **kwds):
        if cache_key := kwds.pop("__cache_key", None):
            _cache_get()[cache_key]["value"] = self
        PyObject_Call(self.__attrs_init__, (), kwds)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class ViewBaseIgnoreExtra:
    def __init__(self, **kwds):
        filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
        PyObject_Call(self.__attrs_init__, (), filtered)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class ViewBaseCacheIgnoreExtra:
    def __init__(self, **kwds):
        if cache_key := kwds.pop("__cache_key", None):
            _cache_get()[cache_key]["value"] = self
        filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
        PyObject_Call(self.__attrs_init__, (), filtered)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class EnvBase(metaclass=Metaclass):
    def __init__(self, **kwds):
        data = {}
        prefixes = self.__cwtch_env_prefixes__
        if prefixes:
            env_source = self.__cwtch_env_source__()
            for attr in self.__attrs_attrs__:
                if env_var := attr.metadata.get("env_var"):
                    for prefix in prefixes:
                        if isinstance(env_var, str):
                            key = env_var
                        else:
                            key = f"{prefix}{attr.name}".upper()
                        if key in env_source:
                            value = env_source[key]
                            try:
                                value = json_loads(value)
                            except JSONDecodeError:
                                pass
                            data[attr.name] = value
                            break
        data.update(kwds)

        PyObject_Call(self.__attrs_init__, (), data)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class EnvBaseCache(metaclass=Metaclass):
    def __init__(self, **kwds):
        if cache_key := kwds.pop("__cache_key", None):
            _cache_get()[cache_key]["value"] = self

        data = {}
        prefixes = self.__cwtch_env_prefixes__
        if prefixes:
            env_source = self.__cwtch_env_source__()
            for attr in self.__attrs_attrs__:
                if env_var := attr.metadata.get("env_var"):
                    for prefix in prefixes:
                        if isinstance(env_var, str):
                            key = env_var
                        else:
                            key = f"{prefix}{attr.name}".upper()
                        if key in env_source:
                            data[attr.name] = env_source[key]
                            break
        data.update(kwds)

        PyObject_Call(self.__attrs_init__, (), data)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class EnvBaseIgnoreExtra(metaclass=Metaclass):
    def __init__(self, **kwds):
        data = {}
        prefixes = self.__cwtch_env_prefixes__
        if prefixes:
            env_source = self.__cwtch_env_source__()
            for attr in self.__attrs_attrs__:
                if env_var := attr.metadata.get("env_var"):
                    for prefix in prefixes:
                        if isinstance(env_var, str):
                            key = env_var
                        else:
                            key = f"{prefix}{attr.name}".upper()
                        if key in env_source:
                            data[attr.name] = env_source[key]
                            break

        filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
        data.update(filtered)

        PyObject_Call(self.__attrs_init__, (), filtered)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


class EnvBaseCacheIgnoreExtra(metaclass=Metaclass):
    def __init__(self, **kwds):
        if cache_key := kwds.pop("__cache_key", None):
            _cache_get()[cache_key]["value"] = self

        data = {}
        prefixes = self.__cwtch_env_prefixes__
        if prefixes:
            env_source = self.__cwtch_env_source__()
            for attr in self.__attrs_attrs__:
                if env_var := attr.metadata.get("env_var"):
                    for prefix in prefixes:
                        if isinstance(env_var, str):
                            key = env_var
                        else:
                            key = f"{prefix}{attr.name}".upper()
                        if key in env_source:
                            data[attr.name] = env_source[key]
                            break

        filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
        data.update(filtered)

        PyObject_Call(self.__attrs_init__, (), filtered)

    def __class_getitem__(cls, parameters):
        result = super().__class_getitem__(parameters)
        return _class_getitem(cls, parameters, result)


def _validate_any(value, T, /):
    return value


def _validate_type(value, T, /):
    if (origin := getattr(T, "__origin__", None)) is None:
        if isinstance(value, T):
            return value
        origin = T
    if hasattr(origin, "__attrs_attrs__"):
        if getattr(origin, "__cwtch_use_cache__", None):
            cache_key = (T, id(value))
            cache = _cache_get()
            if (cache_item := cache.get(cache_key)) is not None:
                return cache_item["value"] if cache_item["reset_circular_refs"] is False else UNSET
        if isinstance(value, dict):
            return PyObject_Call(origin, (), value)
        if isinstance(value, origin):
            return value
        kwds = {a.name: getattr(value, a.name) for a in origin.__attrs_attrs__}
        return PyObject_Call(origin, (), kwds)
    if is_dataclass(origin) and isinstance(value, dict):
        return PyObject_Call(origin, (), value)
    return origin(value)


def _validate_bool(value, T, /):
    if PyNumber_Check(value) == 1:
        if value == 1:
            return True
        if value == 0:
            return False
    if PyUnicode_Check(value):
        if value in {"1", "true", "t", "y", "yes", "True", "TRUE", "Y", "Yes", "YES"}:
            return True
        if value in {"0", "false", "f", "n", "no", "False", "FALSE", "N", "No", "NO"}:
            return False
    raise ValueError(f"invalid value for {T}")


def _validate_list(value, T, /):
    if isinstance(value, list):
        if (args := getattr(T, "__args__", None)) is not None:
            try:
                T_arg = args[0]
                if T_arg == int:
                    return [x if isinstance(x, int) else PyNumber_Long(x) for x in value]
                    # return [PyNumber_Long(x) for x in value]
                if T_arg == str:
                    return [x if isinstance(x, str) else f"{x}" for x in value]
                    # return [f"{x}" for x in value]
                if T_arg == float:
                    # return [x if isinstance(x, float) else float(x) for x in value]
                    return [x if isinstance(x, float) else PyNumber_Float(x) for x in value]
                    # return [PyNumber_Float(x) for x in value]
                validator = get_validator(T_arg)
                if validator == _validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return [x if isinstance(x, origin) else validator(x, T_arg) for x in value]
                if validator == _validate_any:
                    return value
                return [validator(x, T_arg) for x in value]
            except Exception as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                try:
                    for x in value:
                        validator(x, T_arg)
                        i += 1
                except Exception as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                    else:
                        path = [i]
                    raise ValidationError(value, T, [e], path=path)
        return value

    if not isinstance(value, (tuple, set)):
        raise ValueError(f"invalid value for {T}")

    if args := getattr(T, "__args__", None):
        try:
            T_arg = args[0]
            if T_arg == int:
                return [x if isinstance(x, int) else PyNumber_Long(x) for x in value]
                # return [PyNumber_Long(x) for x in value]
            if T_arg == str:
                return [x if isinstance(x, str) else f"{x}" for x in value]
                # return [f"{x}" for x in value]
            if T_arg == float:
                # return [x if isinstance(x, float) else float(x) for x in value]
                return [x if isinstance(x, float) else PyNumber_Float(x) for x in value]
                # return [PyNumber_Float(x) for x in value]
            validator = get_validator(T_arg)
            if validator == _validate_type:
                origin = getattr(T_arg, "__origin__", T_arg)
                return [x if isinstance(x, origin) else validator(x, T_arg) for x in value]
            if validator == _validate_any:
                return [x for x in value]
            return [validator(x, T_arg) for x in value]
        except Exception as e:
            i: cython.int = 0
            validator = get_validator(T_arg)
            try:
                for x in value:
                    validator(x, T_arg)
                    i += 1
            except Exception as e:
                if isinstance(e, ValidationError) and e.path:
                    path = [i] + e.path
                else:
                    path = [i]
                raise ValidationError(value, T, [e], path=path)

    return [x for x in value]


def _validate_tuple(value, T, /):
    if isinstance(value, tuple):
        if (T_args := getattr(T, "__args__", None)) is not None:
            if (len_v := len(value)) == 0 or (len_v == len(T_args) and T_args[-1] != Ellipsis):
                try:
                    return tuple(
                        PyNumber_Long(x)
                        if T_args == int
                        else get_validator(getattr(T_arg, "__origin__", T_arg))(x, T_arg)
                        for x, T_arg in zip(value, T_args)
                    )
                except Exception as e:
                    i: cython.int = 0
                    validator = get_validator(T_arg)
                    try:
                        for x in value:
                            validator(x, T_arg)
                            i += 1
                    except Exception as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                        else:
                            path = [i]
                        raise ValidationError(value, T, [e], path=path)

            if T_args[-1] != Ellipsis:
                raise ValueError(f"invalid arguments count for {T}")

            T_arg = T_args[0]
            try:
                if T_arg == int:
                    return tuple(x if isinstance(x, int) else PyNumber_Long(x) for x in value)
                    # return tuple(PyNumber_Long(x) for x in value)
                if T_arg == str:
                    return tuple(x if isinstance(x, str) else f"{x}" for x in value)
                    # return tuple(f"{x}" for x in value)
                if T_arg == float:
                    # return tuple(x if isinstance(x, float) else float(x) for x in value)
                    return tuple(x if isinstance(x, float) else PyNumber_Float(x) for x in value)
                    # return tuple(PyNumber_Float(x) for x in value)
                validator = get_validator(T_arg)
                if validator == _validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return tuple(x if isinstance(x, origin) else T_arg(x) for x in value)
                if validator == _validate_any:
                    return value
                return tuple(validator(x, T_arg) for x in value)
            except Exception as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                try:
                    for x in value:
                        validator(x, T_arg)
                        i += 1
                except Exception as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                    else:
                        path = [i]
                    raise ValidationError(value, T, [e], path=path)
        return value

    if not isinstance(value, (list, set)):
        raise ValueError(f"invalid value for {T}")

    if (T_args := getattr(T, "__args__", None)) is not None:
        if (len_v := len(value)) == 0 or (len_v == len(T_args) and T_args[-1] != Ellipsis):
            try:
                return tuple(
                    PyNumber_Long(x) if T_args == int else get_validator(getattr(T_arg, "__origin__", T_arg))(x, T_arg)
                    for x, T_arg in zip(value, T_args)
                )
            except Exception as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                try:
                    for x in value:
                        validator(x, T_arg)
                        i += 1
                except Exception as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                    else:
                        path = [i]
                    raise ValidationError(value, T, [e], path=path)

        if T_args[-1] != Ellipsis:
            raise ValueError(f"invalid arguments count for {T}")

        T_arg = T_args[0]
        try:
            if T_arg == int:
                return tuple(x if isinstance(x, int) else PyNumber_Long(x) for x in value)
                # return tuple(PyNumber_Long(x) for x in value)
            if T_arg == str:
                return tuple(x if isinstance(x, str) else f"{x}" for x in value)
                # return tuple(f"{x}" for x in value)
            if T_arg == float:
                # return tuple(x if isinstance(x, float) else float(x) for x in value)
                return tuple(x if isinstance(x, float) else PyNumber_Float(x) for x in value)
                # return tuple(PyNumber_Float(x) for x in value)
            validator = get_validator(T_arg)
            if validator == _validate_type:
                origin = getattr(T_arg, "__origin__", T_arg)
                return tuple(x if isinstance(x, origin) else T_arg(x) for x in value)
            if validator == _validate_any:
                return tuple(value)
            return tuple(validator(x, T_arg) for x in value)
        except Exception as e:
            i: cython.int = 0
            validator = get_validator(T_arg)
            try:
                for x in value:
                    validator(x, T_arg)
                    i += 1
            except Exception as e:
                if isinstance(e, ValidationError) and e.path:
                    path = [i] + e.path
                else:
                    path = [i]
                raise ValidationError(value, T, [e], path=path)

    return tuple(x for x in value)


_validate_set = _validate_list


def _validate_mapping(value, T, /):
    if not isinstance(value, Mapping):
        raise ValueError(f"invalid value for {T}")
    if (args := getattr(T, "__args__", None)) is not None:
        T_k = args[0]
        T_v = args[1]
        validator_v = get_validator(getattr(T_v, "__origin__", T_v))
        try:
            if T_k == str:
                return {
                    k if isinstance(k, str) else f"{k}": v if isinstance(v, T_v) else validator_v(v, T_v)
                    for k, v in value.items()
                }
            validator_k = get_validator(getattr(T_k, "__origin__", T_k))
            return {
                k if isinstance(k, T_k) else validator_k(k, T_k): v if isinstance(v, T_v) else validator_v(v, T_v)
                for k, v in value.items()
            }
        except Exception as e:
            validator_k = get_validator(getattr(T_k, "__origin__", T_k))
            for k, v in value.items():
                try:
                    validator_k(k, T_k)
                    validator_v(v, T_v)
                except Exception as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [k] + e.path
                    else:
                        path = [k]
                    raise ValidationError(value, T, [e], path=path)
    return value


def _validate_dict(value, T, /):
    if not isinstance(value, dict):
        raise ValueError(f"invalid value for {T}")
    if (args := getattr(T, "__args__", None)) is not None:
        T_k = args[0]
        T_v = args[1]
        validator_v = get_validator(getattr(T_v, "__origin__", T_v))
        try:
            if T_k == str:
                return {
                    k if isinstance(k, str) else f"{k}": v if isinstance(v, T_v) else validator_v(v, T_v)
                    for k, v in value.items()
                }
            validator_k = get_validator(getattr(T_k, "__origin__", T_k))
            return {
                k if isinstance(k, T_k) else validator_k(k, T_k): v if isinstance(v, T_v) else validator_v(v, T_v)
                for k, v in value.items()
            }
        except Exception as e:
            validator_k = get_validator(getattr(T_k, "__origin__", T_k))
            for k, v in value.items():
                try:
                    validator_k(k, T_k)
                    validator_v(v, T_v)
                except Exception as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [k] + e.path
                    else:
                        path = [k]
                    raise ValidationError(value, T, [e], path=path)
    return value


def _validate_generic_alias(value, T, /):
    return get_validator(T.__origin__)(value, T)


def _validate_int(value, T, /):
    return PyNumber_Long(value)


def _validate_float(value, T, /):
    return PyNumber_Float(value)


def _validate_str(value, T, /):
    return f"{value}"


def _validate_callable(value, T, /):
    if not callable(value):
        raise ValueError("not callable")
    return value


def _validate_annotated(value, T, /):
    __metadata__ = T.__metadata__

    for metadata in __metadata__:
        if converter := getattr(metadata, "convert", None):
            value = converter(value)

    for metadata in __metadata__:
        if validator := getattr(metadata, "validate_before", None):
            validator(value)

    __origin__ = T.__origin__
    value = get_validator(__origin__)(value, __origin__)

    for metadata in __metadata__:
        if validator := getattr(metadata, "validate_after", None):
            validator(value)

    return value


def _validate_union(value, T, /):
    for T_arg in T.__args__:
        if not hasattr(T_arg, "__origin__") and (T_arg == Any or isinstance(value, T_arg)):
            return value
    errors = []
    for T_arg in T.__args__:
        try:
            return validate_value(value, T_arg)
        except ValidationError as e:
            errors.extend(e.errors)
    raise ValidationError(value, T, errors)


def _validate_literal(value, T, /):
    if value not in T.__args__:
        raise ValidationError(value, T, [ValueError(f"value is not a one of {list(T.__args__)}")])
    return value


def _validate_abcmeta(value, T, /):
    if isinstance(value, getattr(T, "__origin__", T)):
        return value
    raise ValidationError(value, T, [ValueError(f"value is not a instance of {T}")])


def _validate_datetime(value, T, /):
    if isinstance(value, str):
        return datetime_fromisoformat(value)
    return default_validator(value, T)


def _validate_date(value, T, /):
    if isinstance(value, str):
        return date_fromisoformat(value)
    return default_validator(value, T)


def _validate_none(value, T, /):
    if value is not None:
        raise ValidationError(value, T, [ValueError("value is not a None")])


def _validate_typevar(value, T, /):
    T_arg = _cache_get()["parameters"][T]
    return get_validator(T_arg)(value, T_arg)


def default_validator(value, T, /):
    if not hasattr(T, "__origin__") and isinstance(value, T):
        return value
    return T(value)


_validators_map[None] = _validate_none
_validators_map[None.__class__] = _validate_none
_validators_map[type] = _validate_type
_validators_map[Metaclass] = _validate_type
_validators_map[int] = _validate_int
_validators_map[float] = _validate_float
_validators_map[str] = _validate_str
_validators_map[bool] = _validate_bool
_validators_map[list] = _validate_list
_validators_map[tuple] = _validate_tuple
_validators_map[_TupleType] = _validate_tuple
_validators_map[set] = _validate_set
_validators_map[dict] = _validate_dict
_validators_map[Mapping] = _validate_mapping
_validators_map[_AnyMeta] = _validate_any
_validators_map[_AnnotatedAlias] = _validate_annotated
_validators_map[GenericAlias] = _validate_generic_alias
_validators_map[_GenericAlias] = _validate_generic_alias
_validators_map[_SpecialGenericAlias] = _validate_generic_alias
_validators_map[_LiteralGenericAlias] = _validate_literal
_validators_map[_CallableType] = _validate_callable
_validators_map[UnionType] = _validate_union
_validators_map[_UnionGenericAlias] = _validate_union
_validators_map[ABCMeta] = _validate_abcmeta
_validators_map[datetime] = _validate_datetime
_validators_map[date] = _validate_date
_validators_map[TypeVar] = _validate_typevar

_validators_map_get = _validators_map.get


@cache
def get_validator(T, /):
    return _validators_map_get(T) or _validators_map_get(T.__class__) or default_validator


def validate_value(value, T):
    try:
        return get_validator(T)(value, T)
    except ValidationError as e:
        if parameters := _cache_get().get("parameters"):
            e.parameters = parameters
        raise e
    except Exception as e:
        parameters = _cache_get().get("parameters")
        raise ValidationError(value, T, [e], parameters=parameters)


def field(*args, validate: bool = True, env_var: bool | str | list[str] = None, **kwds):
    kwds.setdefault("metadata", {})["extra"] = {}

    if env_var:
        kwds["metadata"]["env_var"] = env_var

    if validate:
        __setattr__ = object.__setattr__

        if original_validators := kwds.get("validator", []):
            kwds["metadata"]["validator"] = original_validators
            if not isinstance(original_validators, list):
                original_validators = [original_validators]

            def validator(self, attribute, value):
                try:
                    if value == UNSET:
                        validated_value = value
                    else:
                        validated_value = validate_value(value, attribute.type)
                    if validated_value != value:
                        __setattr__(self, attribute.name, validated_value)
                    for validator in original_validators:
                        validator(self, attribute, validated_value)
                except Exception as e:
                    raise ValidationError(value, self.__class__, [e], path=[attribute.name])

        else:

            def validator(self, attribute, value):
                try:
                    if value == UNSET:
                        validated_value = value
                    else:
                        validated_value = validate_value(value, attribute.type)
                    if validated_value != value:
                        __setattr__(self, attribute.name, validated_value)
                except Exception as e:
                    raise ValidationError(value, self.__class__, [e], path=[attribute.name])

        kwds["validator"] = validator

    return attrs_field(*args, **kwds)
