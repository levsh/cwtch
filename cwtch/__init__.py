import importlib.metadata

from cwtch.core import field

from .cwtch import (
    asdict,
    define,
    from_attributes,
    register_validator,
    validate_args,
    validate_call,
    validate_value,
    view,
)
from .errors import *
from .metadata import *
from .types import *

__version__ = importlib.metadata.version("cwtch")
