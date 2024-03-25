import importlib.metadata

from cwtch.core import (
    field,
    get_current_parameters,
    make_json_schema,
    register_json_schema_builder,
    register_validator,
    validate_value,
)

from .cwtch import (
    asdict,
    dataclass,
    from_attributes,
    instantiate_generic_dataclass,
    resolve_types,
    validate_args,
    validate_call,
    view,
)

__version__ = importlib.metadata.version("cwtch")
