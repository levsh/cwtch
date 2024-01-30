# cython: language_level=3
# cython: boundscheck=False
# distutils: language=c

from contextvars import ContextVar
from json import JSONDecodeError
from uuid import UUID

import cython
from dataclasses import MISSING
from dataclasses import field as dataclasses_field
from dataclasses import fields as dataclasses_fields
from enum import EnumType, Enum

from .errors import ValidationError
from .types import UnsetType, UNSET
from .metadata import TypeMetadata


cdef extern from "Python.h":

    object PyNumber_Long(object o)
    object PyNumber_Float(object o)
    int PyNumber_Check(object o)
    int PyUnicode_Check(object o)
    object PyObject_Call(object callable_, object args, object kwargs)


_cache = ContextVar("_cache", default={})
_parameters = ContextVar("_parameters", default=[])


class Metaclass(type):
    def __subclasscheck__(self, subclass):
        if isinstance(subclass, type) and getattr(subclass, "__cwtch_view_base__", None) == self:
            return True
        return super().__subclasscheck__(subclass)

    def __instancecheck__(self, instance):
        if getattr(instance, "__cwtch_view_base__", None) == self:
            return True
        return super().__instancecheck__(instance)


class ViewMetaclass(type):
    pass


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
    true_map = (True, 1, "1", "true", "t", "y", "yes", "True", "TRUE", "Y", "Yes", "YES")
    false_map = (False, 0, "0", "false", "f", "n", "no", "False", "FALSE", "N", "No", "NO")
    datetime_fromisoformat = datetime.fromisoformat
    date_fromisoformat = date.fromisoformat
    _UNSET = UNSET
    NoneType = type(None)
    parameters_get = _parameters.get
    object_getattribute = object.__getattribute__

    def class_getitem(cls, parameters, result):
        if not isinstance(parameters, tuple):
            parameters = (parameters,)

        parameters = dict(zip(cls.__parameters__, parameters))

        class Proxy:
            def __getattribute__(self, attr):
                if attr == "is_class_getitem_proxy":
                    return True
                return object_getattribute(result, attr)

            def __str__(self):
                return result.__str__()

            def __repr__(self):
                return result.__repr__()

            def __call__(self, *args, **kwds):
                p = parameters_get()
                p.append(parameters)
                try:
                    return result(*args, **kwds)
                finally:
                    p.pop()

        return Proxy()

    def validate_any(value, T, /):
        return value

    def validate_none(value, T, /):
        if value is not None:
            raise ValidationError(value, T, [ValueError("value is not a None")])

    def validate_bool(value, T, /):
        if value in true_map:
            return True
        if value in false_map:
            return False
        raise ValueError("could not convert value to bool")

    def validate_int(value, T, /):
        return PyNumber_Long(value)

    def validate_float(value, T, /):
        return PyNumber_Float(value)

    def validate_str(value, T, /):
        return f"{value}"

    def validate_type(value, T, /):
        if (origin := getattr(T, "__origin__", T)) == T:
            if isinstance(value, T):
                return value
        if is_dataclass(origin):
            if getattr(origin, "__cwtch_handle_circular_refs__", None):
                cache = cache_get()
                cache_key = (T, id(value))
                if (cache_value := cache.get(cache_key)) is not None:
                    return cache_value if cache["reset_circular_refs"] is False else _UNSET
            if isinstance(value, dict):
                if getattr(T, "is_class_getitem_proxy", None) is True:
                    return PyObject_Call(T, (), value)
                return PyObject_Call(origin, (), value)
            kwds = {f_name: getattr(value, f_name) for f_name in origin.__dataclass_fields__}
            return PyObject_Call(origin, (), kwds)
        if T == UnsetType:
            if value != UNSET:
                raise ValueError(f"value is not a valid {T}")
            return value
        if T == NoneType:
            if value is not None:
                raise ValueError("value is not a None")
            return value
        if origin == type:
            arg = T.__args__[0]
            if hasattr(arg, "__base__") and issubclass(value, T.__args__[0]):
                return value
            raise ValueError(f"invalid value for {T}")
        return origin(value)

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
                except (TypeError, ValueError, ValidationError) as e:
                    i: cython.int = 0
                    validator = get_validator(T_arg)
                    try:
                        for x in value:
                            validator(x, T_arg)
                            i += 1
                    except (TypeError, ValueError, ValidationError) as e:
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
            except (TypeError, ValueError, ValidationError) as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                try:
                    for x in value:
                        validator(x, T_arg)
                        i += 1
                except (TypeError, ValueError, ValidationError) as e:
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
                    except (TypeError, ValueError, ValidationError) as e:
                        i: cython.int = 0
                        validator = get_validator(T_arg)
                        try:
                            for x in value:
                                validator(x, T_arg)
                                i += 1
                        except (TypeError, ValueError, ValidationError) as e:
                            if isinstance(e, ValidationError) and e.path:
                                path = [i] + e.path
                            else:
                                path = [i]
                            raise ValidationError(value, T, [e], path=path)
                        raise e

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
                except (TypeError, ValueError, ValidationError) as e:
                    i: cython.int = 0
                    validator = get_validator(T_arg)
                    try:
                        for x in value:
                            validator(x, T_arg)
                            i += 1
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                        else:
                            path = [i]
                        raise ValidationError(value, T, [e], path=path)
                    raise e

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
                except (TypeError, ValueError, ValidationError) as e:
                    i: cython.int = 0
                    validator = get_validator(T_arg)
                    try:
                        for x in value:
                            validator(x, T_arg)
                            i += 1
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                        else:
                            path = [i]
                        raise ValidationError(value, T, [e], path=path)
                    raise e

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
            except (TypeError, ValueError, ValidationError) as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                try:
                    for x in value:
                        validator(x, T_arg)
                        i += 1
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                    else:
                        path = [i]
                    raise ValidationError(value, T, [e], path=path)
                raise e

        return tuple(x for x in value)

    def validate_set(value, T, /):
        if isinstance(value, set):
            if (args := getattr(T, "__args__", None)) is not None:
                try:
                    T_arg = args[0]
                    if T_arg == int:
                        return set(x if isinstance(x, int) else PyNumber_Long(x) for x in value)
                    if T_arg == str:
                        return set(x if isinstance(x, str) else f"{x}" for x in value)
                    if T_arg == float:
                        return set(x if isinstance(x, float) else PyNumber_Float(x) for x in value)
                    validator = get_validator(T_arg)
                    if validator == validate_type:
                        origin = getattr(T_arg, "__origin__", T_arg)
                        return set(x if isinstance(x, origin) else validator(x, T_arg) for x in value)
                    if validator == validate_any:
                        return value
                    return set(validator(x, T_arg) for x in value)
                except (TypeError, ValueError, ValidationError) as e:
                    i: cython.int = 0
                    validator = get_validator(T_arg)
                    try:
                        for x in value:
                            validator(x, T_arg)
                            i += 1
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [i] + e.path
                        else:
                            path = [i]
                        raise ValidationError(value, T, [e], path=path)
                    raise e

            return value

        if not isinstance(value, (list, tuple)):
            raise ValueError(f"invalid value for {T}")

        if args := getattr(T, "__args__", None):
            try:
                T_arg = args[0]
                if T_arg == int:
                    return set(x if isinstance(x, int) else PyNumber_Long(x) for x in value)
                if T_arg == str:
                    return set(x if isinstance(x, str) else f"{x}" for x in value)
                if T_arg == float:
                    return set(x if isinstance(x, float) else PyNumber_Float(x) for x in value)
                validator = get_validator(T_arg)
                if validator == validate_type:
                    origin = getattr(T_arg, "__origin__", T_arg)
                    return set(x if isinstance(x, origin) else validator(x, T_arg) for x in value)
                if validator == validate_any:
                    return set(x for x in value)
                return set(validator(x, T_arg) for x in value)
            except (TypeError, ValueError, ValidationError) as e:
                i: cython.int = 0
                validator = get_validator(T_arg)
                try:
                    for x in value:
                        validator(x, T_arg)
                        i += 1
                except (TypeError, ValueError, ValidationError) as e:
                    if isinstance(e, ValidationError) and e.path:
                        path = [i] + e.path
                    else:
                        path = [i]
                    raise ValidationError(value, T, [e], path=path)
                raise e

        return set(x for x in value)

    def validate_dict(value, T, /):
        if not isinstance(value, dict):
            raise ValueError(f"invalid value for {T}")
        if (args := getattr(T, "__args__", None)) is not None:
            T_k, T_v = args
            validator_v = get_validator(getattr(T_v, "__origin__", T_v))
            try:
                if T_k == str:
                    return {
                        # k if isinstance(k, str) else f"{k}": v if isinstance(v, T_v) else validator_v(v, T_v)
                        f"{k}": v if isinstance(v, T_v) else validator_v(v, T_v)
                        for k, v in value.items()
                    }
                validator_k = get_validator(getattr(T_k, "__origin__", T_k))
                return {
                    k if isinstance(k, T_k) else validator_k(k, T_k): v if isinstance(v, T_v) else validator_v(v, T_v)
                    for k, v in value.items()
                }
            except (TypeError, ValueError, ValidationError) as e:
                validator_k = get_validator(getattr(T_k, "__origin__", T_k))
                for k, v in value.items():
                    try:
                        validator_k(k, T_k)
                        validator_v(v, T_v)
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [k] + e.path
                        else:
                            path = [k]
                        raise ValidationError(value, T, [e], path=path)
                    raise e
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
            except (TypeError, ValueError, ValidationError) as e:
                validator_k = get_validator(getattr(T_k, "__origin__", T_k))
                for k, v in value.items():
                    try:
                        validator_k(k, T_k)
                        validator_v(v, T_v)
                    except (TypeError, ValueError, ValidationError) as e:
                        if isinstance(e, ValidationError) and e.path:
                            path = [k] + e.path
                        else:
                            path = [k]
                        raise ValidationError(value, T, [e], path=path)
                    raise e
        return value

    def validate_generic_alias(value, T, /):
        return get_validator(T.__origin__)(value, T)

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

    def validate_typevar(value, T, /):
        parameters = parameters_get()[-1]
        T_arg = parameters[T]
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
    validators_map[ViewMetaclass] = validate_type
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

    def validate_value_using_validator(value, T, validator):
        try:
            return validator(value, T)
        except ValidationError as e:
            parameters = parameters_get()
            if parameters:
                e.parameters = parameters[-1]
            raise e
        except (TypeError, ValueError) as e:
            parameters = parameters_get()
            if parameters:
                parameters = parameters[-1]
            else:
                parameters = None
            raise ValidationError(value, T, [e], parameters=parameters)

    def validate_value(value, T):
        try:
            return get_validator(T)(value, T)
        except ValidationError as e:
            parameters = parameters_get()
            if parameters:
                e.parameters = parameters[-1]
            raise e
        except (TypeError, ValueError) as e:
            parameters = parameters_get()
            if parameters:
                parameters = parameters[-1]
            else:
                parameters = None
            raise ValidationError(value, T, [e], parameters=parameters)

    def make_json_schema(
        T,
        ref_builder=lambda T: f"#/$defs/{getattr(T, '__origin__', T).__name__}",
        hook=None,
    ) -> tuple[dict, dict]:
        if builder := getattr(T, "__cwtch_json_schema__", None):
            schema = builder()
            for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
                schema.update(metadata.json_schema())
            return schema, {}
        if builder := get_json_schema_builder(T):
            return builder(T, ref_builder=ref_builder, hook=hook)
        if hook:
            return hook(T, ref_builder=ref_builder, hook=hook)
        raise Exception(f"missing json schema builder for {T}")

    def make_json_schema_none(T, ref_builder=None, hook=None):
        return {"type": "null"}, {}

    def make_json_schema_enum(T, ref_builder=None, hook=None):
        return {"enum": [f"{v}" for v in T.__members__.values()]}, {}

    def make_json_schema_int(T, ref_builder=None, hook=None):
        schema = {"type": "integer"}
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        return schema, {}

    def make_json_schema_float(T, ref_builder=None, hook=None):
        schema = {"type": "number"}
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        return schema, {}

    def make_json_schema_str(T, ref_builder=None, hook=None):
        schema = {"type": "string"}
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        return schema, {}

    def make_json_schema_bool(T, ref_builder=None, hook=None):
        return {"type": "boolean"}, {}

    def make_json_schema_annotated(T, ref_builder=None, hook=None):
        schema, refs = make_json_schema(T.__origin__, ref_builder=ref_builder, hook=hook)
        for metadata in filter(lambda item: isinstance(item, TypeMetadata), getattr(T, "__metadata__", ())):
            schema.update(metadata.json_schema())
        return schema, refs

    def make_json_schema_union(T, ref_builder=None, hook=None):
        schemas = []
        refs = {}
        for arg in T.__args__:
            if arg == UnsetType:
                continue
            arg_schema, arg_refs = make_json_schema(arg, ref_builder=ref_builder, hook=hook)
            schemas.append(arg_schema)
            refs.update(arg_refs)
        return {"oneOf": schemas}, refs

    def make_json_schema_list(T, ref_builder=None, hook=None):
        schema = {"type": "array"}
        refs = {}
        if hasattr(T, "__args__"):
            items_schema, refs = make_json_schema(T.__args__[0], ref_builder=ref_builder, hook=hook)
            schema["items"] = items_schema
        return schema, refs

    def make_json_schema_tuple(T, ref_builder=None, hook=None):
        schema = {"type": "array", "items": False}
        refs = {}
        if hasattr(T, "__args__"):
            schema["prefixItems"] = []
            for arg in T.__args__:
                if arg == ...:
                    raise Exception("Ellipsis is not supported")
                arg_schema, arg_refs = make_json_schema(arg, ref_builder=ref_builder, hook=hook)
                schema["prefixItems"].append(arg_schema)
                refs.update(arg_refs)
        return schema, refs

    def make_json_schema_set(T, ref_builder=None, hook=None):
        schema = {"type": "array", "uniqueItems": True}
        refs = {}
        if hasattr(T, "__args__"):
            items_schema, refs = make_json_schema(T.__args__[0], ref_builder=ref_builder, hook=hook)
            schema["items"] = items_schema
        return schema, refs

    def make_json_schema_dict(T, ref_builder=None, hook=None):
        return {"type": "object"}, {}

    def make_json_schema_literal(T, ref_builder=None, hook=None):
        return {"enum": list(T.__args__)}, {}

    def make_json_schema_datetime(T, ref_builder=None, hook=None):
        return {"type": "string", "format": "date-time"}, {}

    def make_json_schema_date(T, ref_builder=None, hook=None):
        return {"type": "string", "format": "date"}, {}

    def make_json_schema_uuid(T, ref_builder=None, hook=None):
        return {"type": "string", "format": "uuid"}, {}

    def make_json_schema_generic_alias(T, ref_builder=None, hook=None):
        if builder := get_json_schema_builder(T.__origin__):
            return builder(T, ref_builder=ref_builder, hook=hook)
        if hook:
            return hook(T, ref_builder=ref_builder, hook=hook)
        raise Exception(f"missing json schema builder for {T}")

    def make_json_schema_type(T, ref_builder=None, hook=None):
        origin = getattr(T, "__origin__", T)
        if is_dataclass(origin):
            return make_json_schema_dataclass(T, ref_builder=ref_builder, hook=hook)
        raise Exception(f"missing json schema builder for {T}")

    def make_json_schema_dataclass(T, ref_builder=None, hook=None):
        schema = {"type": "object"}
        refs = {}
        properties = {}
        required = []
        origin = getattr(T, "__origin__", T)
        if hasattr(origin, "__parameters__"):
            type_parameters = dict(zip(origin.__parameters__, T.__args__))
        else:
            type_parameters = {}
        for f in origin.__dataclass_fields__.values():
            tp = f.type
            if type_parameters:
                if hasattr(f.type, "__typing_subst__"):
                    tp = type_parameters[f.type]
                elif hasattr(f.type, "__parameters__"):
                    tp = f.type.__class_getitem__(*[type_parameters[tp] for tp in f.type.__parameters__])
            f_schema, f_refs = make_json_schema(tp, ref_builder=ref_builder, hook=hook)
            properties[f.name] = f_schema
            refs.update(f_refs)
            if f.default == MISSING:
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
    json_schema_builders_map[Metaclass] = make_json_schema_dataclass
    json_schema_builders_map[ViewMetaclass] = make_json_schema_dataclass
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
    json_schema_builders_map[UnionType] = make_json_schema_union
    json_schema_builders_map[_UnionGenericAlias] = make_json_schema_union
    json_schema_builders_map[datetime] = make_json_schema_datetime
    json_schema_builders_map[date] = make_json_schema_date
    json_schema_builders_map[UUID] = make_json_schema_uuid

    @functools.cache
    def get_json_schema_builder(T, /):
        return json_schema_builders_map.get(T) or json_schema_builders_map.get(T.__class__)

    return (
        class_getitem,
        validators_map,
        get_validator,
        validate_value,
        validate_value_using_validator,
        json_schema_builders_map,
        get_json_schema_builder,
        make_json_schema,
    )


(
    _class_getitem,
    _validators_map,
    get_validator,
    validate_value,
    validate_value_using_validator,
    _json_schema_builders_map,
    get_json_schema_builder,
    make_json_schema,
) = make()


def field(*args, validate: bool | None = None, env_var: bool | str | list[str] = None, **kwds):
    metadata = {}

    if validate is not None:
        metadata["validate"] = validate

    if env_var is not None:
        metadata["env_var"] = env_var

    kwds.setdefault("metadata", {})["cwtch"] = metadata

    return dataclasses_field(*args, **kwds)


def register_validator(T, validator, force: bool | None = None):
    if T in _validators_map and not force:
        raise Exception(f"validator for '{T}' already registered")
    _validators_map[T] = validator
    get_validator.cache_clear()


def register_json_schema_builder(T, builder, force: bool | None = None):
    if T in _json_schema_builders_map and not force:
        raise Exception(f"json schema builder for '{T}' already registered")
    _json_schema_builders_map[T] = builder
    get_json_schema_builder.cache_clear()


def _asdict(inst, root: bool, **kwds):
    show_secrets = kwds.get("show_secrets", None)

    if not getattr(inst, "__cwtch_model__", None) is True and not getattr(inst, "__cwtch_view__", None) is True:
        if root:
            raise Exception("not a cwtch model")
        if show_secrets and hasattr(v, "get_secret_value"):
            return inst.get_secret_value()
        return inst

    include_ = kwds.get("include", None)
    exclude_ = kwds.get("exclude", None)
    exclude_unset = kwds.get("exclude_unset", None)

    conditions = []
    if include_ is not None:
        conditions.append(lambda k, v: k in include_)
    if exclude_ is not None:
        conditions.append(lambda k, v: k not in exclude_)
    if exclude_unset:
        conditions.append(lambda k, v: v != UNSET)

    if hasattr(inst, "to_dict"):
        items = inst.to_dict().items()
    else:
        items = ((f.name, getattr(inst, f.name)) for f in dataclasses_fields(inst))
    data = {}
    for k, v in items:
        if all(condition(k, v) for condition in conditions):
            if isinstance(v, list):
                data[k] = [_asdict(x, False, exclude_unset=exclude_unset, show_secrets=show_secrets) for x in v]
            elif isinstance(v, tuple):
                data[k] = tuple(_asdict(x, False, exclude_unset=exclude_unset, show_secrets=show_secrets) for x in v)
            elif isinstance(v, dict):
                data[k] = {
                    kk: _asdict(vv, False, exclude_unset=exclude_unset, show_secrets=show_secrets)
                    for kk, vv in v.items()
                }
            else:
                data[k] = _asdict(v, False, exclude_unset=exclude_unset)
    return data
