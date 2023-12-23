# cython: language_level=3
# cython: boundscheck=False
# distutils: language=c

from contextvars import ContextVar
from json import JSONDecodeError

import cython
from attrs import field as attrs_field

from .errors import ValidationError


cdef extern from "Python.h":

    object PyNumber_Long(object o)
    object PyNumber_Float(object o)
    int PyNumber_Check(object o)
    int PyUnicode_Check(object o)
    object PyObject_Call(object callable_, object args, object kwargs)


_cache = ContextVar("_cache", default={})


class UnsetType:
    def __copy__(self, *args, **kwds):
        return self

    def __deepcopy__(self, *args, **kwds):
        return self


UNSET = UnsetType()


class Metaclass(type):
    def __subclasscheck__(self, subclass):
        if isinstance(subclass, type) and getattr(subclass, "__cwtch_view_base__", None) == self:
            return True
        return super().__subclasscheck__(subclass)

    def __instancecheck__(self, instance):
        if getattr(instance, "__cwtch_view_base__", None) == self:
            return True
        return super().__instancecheck__(instance)


def make_bases():
    cache_get = _cache.get
    object_getattribute = object.__getattribute__

    def class_getitem(cls, parameters, result):
        if not isinstance(parameters, tuple):
            parameters = (parameters,)

        parameters = dict(zip(cls.__parameters__, parameters))

        cls_attrs = ("__call__", "__str__", "__repr__")

        class Proxy:
            def __getattribute__(self, attr):
                if attr not in cls_attrs:
                    return object_getattribute(cls, attr)
                return object_getattribute(self, attr)

            def __str__(self):
                return result.__str__()

            def __repr__(self):
                return result.__repr__()

            def __call__(self, *args, **kwds):
                cache_get()["parameters"] = parameters
                try:
                    return result(*args, **kwds)
                finally:
                    cache_get().pop("parameters", None)

        return Proxy()

    class Base(metaclass=Metaclass):
        def __init__(self, *, _cwtch_cache_key=None, **kwds):
            if _cwtch_cache_key is not None:
                cache_get()[_cwtch_cache_key] = self
            PyObject_Call(self.__attrs_init__, (), kwds)

        def __class_getitem__(cls, parameters):
            result = super().__class_getitem__(parameters)
            return class_getitem(cls, parameters, result)

    class BaseIgnoreExtra(metaclass=Metaclass):
        def __init__(self, *, _cwtch_cache_key=None, **kwds):
            if _cwtch_cache_key is not None:
                cache_get()[_cwtch_cache_key] = self
            filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
            PyObject_Call(self.__attrs_init__, (), filtered)

        def __class_getitem__(cls, parameters):
            result = super().__class_getitem__(parameters)
            return class_getitem(cls, parameters, result)

    class ViewBase:
        def __init__(self, *, _cwtch_cache_key=None, **kwds):
            if _cwtch_cache_key is not None:
                cache_get()[_cwtch_cache_key] = self
            PyObject_Call(self.__attrs_init__, (), kwds)

        def __class_getitem__(cls, parameters):
            result = super().__class_getitem__(parameters)
            return class_getitem(cls, parameters, result)

    class ViewBaseIgnoreExtra:
        def __init__(self, *, _cwtch_cache_key=None, **kwds):
            if _cwtch_cache_key is not None:
                cache_get()[_cwtch_cache_key] = self
            filtered = {attr.name: kwds[attr.name] for attr in self.__attrs_attrs__ if attr.name in kwds}
            PyObject_Call(self.__attrs_init__, (), filtered)

        def __class_getitem__(cls, parameters):
            result = super().__class_getitem__(parameters)
            return class_getitem(cls, parameters, result)

    class EnvBase(metaclass=Metaclass):
        def __init__(self, *, _cwtch_cache_key=None, **kwds):
            if _cwtch_cache_key is not None:
                cache_get()[_cwtch_cache_key] = self

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
            return class_getitem(cls, parameters, result)

    class EnvBaseIgnoreExtra(metaclass=Metaclass):
        def __init__(self, *, _cwtch_cache_key=None, **kwds):
            if _cwtch_cache_key is not None:
                cache_get()[_cwtch_cache_key] = self

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
            return class_getitem(cls, parameters, result)

    return Base, BaseIgnoreExtra, ViewBase, ViewBaseIgnoreExtra, EnvBase, EnvBaseIgnoreExtra


Base, BaseIgnoreExtra, ViewBase, ViewBaseIgnoreExtra, EnvBase, EnvBaseIgnoreExtra = make_bases()


def make():
    import functools
    from abc import ABCMeta
    from collections.abc import Iterable, Mapping, Sequence
    from dataclasses import is_dataclass
    from datetime import date, datetime
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
        _SpecialGenericAlias,
        _TupleType,
        _UnionGenericAlias,
    )

    cache_get = _cache.get
    true_map = {"1", "true", "t", "y", "yes", "True", "TRUE", "Y", "Yes", "YES"}
    false_map = {"0", "false", "f", "n", "no", "False", "FALSE", "N", "No", "NO"}
    datetime_fromisoformat = datetime.fromisoformat
    date_fromisoformat = date.fromisoformat
    _UNSET = UNSET

    def validate_any(value, T, /):
        return value

    def validate_type(value, T, /):
        if (origin := getattr(T, "__origin__", None)) is None:
            if isinstance(value, T):
                return value
            origin = T
        if hasattr(origin, "__cwtch_model__"):
            cache = cache_get()
            cache_key = (T, id(value))
            if (cache_value := cache.get(cache_key)) is not None:
                return cache_value if cache["reset_circular_refs"] is False else _UNSET
            try:
                if isinstance(value, dict):
                    return origin(_cwtch_cache_key=cache_key, **value)
                if isinstance(value, origin):
                    return value
                kwds = {a.name: getattr(value, a.name) for a in origin.__attrs_attrs__}
                return origin(_cwtch_cache_key=cache_key, **kwds)
            finally:
                cache.pop(cache_key, None)
        if hasattr(origin, "__attrs_attrs__"):
            if isinstance(value, dict):
                return origin(**value)
            if isinstance(value, origin):
                return value
            kwds = {a.name: getattr(value, a.name) for a in origin.__attrs_attrs__}
            return origin(**kwds)
        if is_dataclass(origin) and isinstance(value, dict):
            return PyObject_Call(origin, (), value)
        return origin(value)

    def validate_bool(value, T, /):
        if PyNumber_Check(value) == 1:
            if value == 1:
                return True
            if value == 0:
                return False
        if PyUnicode_Check(value):
            if value in true_map:
                return True
            if value in false_map:
                return False
        raise ValueError(f"invalid value for {T}")

    def validate_list(value, T, /):
        if isinstance(value, list):
            if (args := getattr(T, "__args__", None)) is not None:
                try:
                    T_arg = args[0]
                    if T_arg == int:
                        return [x if isinstance(x, int) else PyNumber_Long(x) for x in value]
                    if T_arg == str:
                        return [x if isinstance(x, str) else f"{x}" for x in value]
                    if T_arg == float:
                        return [x if isinstance(x, float) else PyNumber_Float(x) for x in value]
                    validator = get_validator(T_arg)
                    if validator == validate_type:
                        origin = getattr(T_arg, "__origin__", T_arg)
                        return [x if isinstance(x, origin) else validator(x, T_arg) for x in value]
                    if validator == validate_any:
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
                if T_arg == str:
                    return [x if isinstance(x, str) else f"{x}" for x in value]
                if T_arg == float:
                    return [x if isinstance(x, float) else PyNumber_Float(x) for x in value]
                validator = get_validator(T_arg)
                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return [x if isinstance(x, origin) else validator(x, T_arg) for x in value]
                if validator == validate_any:
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

    def validate_tuple(value, T, /):
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
                    if T_arg == str:
                        return tuple(x if isinstance(x, str) else f"{x}" for x in value)
                    if T_arg == float:
                        return tuple(x if isinstance(x, float) else PyNumber_Float(x) for x in value)
                    validator = get_validator(T_arg)
                    if validator == validate_type:
                        origin = getattr(T_arg, "__origin__", T_arg)
                        return tuple(x if isinstance(x, origin) else T_arg(x) for x in value)
                    if validator == validate_any:
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
                if T_arg == str:
                    return tuple(x if isinstance(x, str) else f"{x}" for x in value)
                if T_arg == float:
                    return tuple(x if isinstance(x, float) else PyNumber_Float(x) for x in value)
                validator = get_validator(T_arg)
                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return tuple(x if isinstance(x, origin) else T_arg(x) for x in value)
                if validator == validate_any:
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

    validate_set = validate_list

    def validate_dict(value, T, /):
        if not isinstance(value, dict):
            raise ValueError(f"invalid value for {T}")
        if (args := getattr(T, "__args__", None)) is not None:
            T_k, T_v = args
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

    def validate_mapping(value, T, /):
        if not isinstance(value, Mapping):
            raise ValueError(f"invalid value for {T}")
        if (args := getattr(T, "__args__", None)) is not None:
            T_k, T_v = args
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

    def validate_generic_alias(value, T, /):
        return get_validator(T.__origin__)(value, T)

    def validate_int(value, T, /):
        return PyNumber_Long(value)

    def validate_float(value, T, /):
        return PyNumber_Float(value)

    def validate_str(value, T, /):
        return f"{value}"

    def validate_callable(value, T, /):
        if not callable(value):
            raise ValueError("not callable")
        return value

    def validate_annotated(value, T, /):
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

    def validate_union(value, T, /):
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

    def validate_literal(value, T, /):
        if value not in T.__args__:
            raise ValidationError(value, T, [ValueError(f"value is not a one of {list(T.__args__)}")])
        return value

    def validate_abcmeta(value, T, /):
        if isinstance(value, getattr(T, "__origin__", T)):
            return value
        raise ValidationError(value, T, [ValueError(f"value is not a instance of {T}")])

    def validate_datetime(value, T, /):
        if isinstance(value, str):
            return datetime_fromisoformat(value)
        return default_validator(value, T)

    def validate_date(value, T, /):
        if isinstance(value, str):
            return date_fromisoformat(value)
        return default_validator(value, T)

    def validate_none(value, T, /):
        if value is not None:
            raise ValidationError(value, T, [ValueError("value is not a None")])

    def validate_typevar(value, T, /):
        T_arg = cache_get()["parameters"][T]
        return get_validator(T_arg)(value, T_arg)

    def default_validator(value, T, /):
        if not hasattr(T, "__origin__") and isinstance(value, T):
            return value
        return T(value)

    validators_map = {}

    validators_map[None] = validate_none
    validators_map[None.__class__] = validate_none
    validators_map[type] = validate_type
    validators_map[Metaclass] = validate_type
    validators_map[int] = validate_int
    validators_map[float] = validate_float
    validators_map[str] = validate_str
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
    validators_map[UnionType] = validate_union
    validators_map[_UnionGenericAlias] = validate_union
    validators_map[ABCMeta] = validate_abcmeta
    validators_map[datetime] = validate_datetime
    validators_map[date] = validate_date
    validators_map[TypeVar] = validate_typevar

    validators_map_get = validators_map.get

    @functools.cache
    def get_validator(T, /):
        return validators_map_get(T) or validators_map_get(T.__class__) or default_validator

    def validate_value(value, T):
        try:
            return get_validator(T)(value, T)
        except ValidationError as e:
            if parameters := cache_get().get("parameters"):
                e.parameters = parameters
            raise e
        except Exception as e:
            parameters = cache_get().get("parameters")
            raise ValidationError(value, T, [e], parameters=parameters)

    return validators_map, get_validator, validate_value


validators_map, get_validator, validate_value = make()


def field(*args, validate: bool = True, env_var: bool | str | list[str] = None, **kwds):
    kwds.setdefault("metadata", {})["extra"] = {}

    if env_var:
        kwds["metadata"]["env_var"] = env_var

    if validate:
        _setattr = object.__setattr__
        _UNSET = UNSET
        _validate_value = validate_value

        if original_validators := kwds.get("validator", []):
            kwds["metadata"]["validator"] = original_validators
            if not isinstance(original_validators, list):
                original_validators = [original_validators]

            def validator(self, attribute, value):
                try:
                    if value == _UNSET:
                        validated_value = value
                    else:
                        validated_value = _validate_value(value, attribute.type)
                    if validated_value != value:
                        _setattr(self, attribute.name, validated_value)
                    for validator in original_validators:
                        validator(self, attribute, validated_value)
                except Exception as e:
                    raise ValidationError(value, self.__class__, [e], path=[attribute.name])

        else:

            def validator(self, attribute, value):
                try:
                    if value == _UNSET:
                        validated_value = value
                    else:
                        validated_value = _validate_value(value, attribute.type)
                    if validated_value != value:
                        _setattr(self, attribute.name, validated_value)
                except Exception as e:
                    raise ValidationError(value, self.__class__, [e], path=[attribute.name])

        kwds["validator"] = validator

    return attrs_field(*args, **kwds)


def register_validator(T, validator):
    validators_map[T] = validator
    get_validator.cache_clear()
