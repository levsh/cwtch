from typing import Literal


SHOW_INPUT_VALUE_ON_ERROR: bool = True
"""Show input value on ValidationError."""

SLOTS: bool = False
"""Default value for 'slots' argument in dataclass decorator."""

KW_ONLY: bool = False
"""Default value for 'kw_only' argument in dataclass diecorator."""

VALIDATE: bool = True
"""Default value for 'validate' argument in dataclass decorator."""

ADD_DISABLE_VALIDATION_TO_INIT: bool = False
"""Default value for 'add_disable_validation_to_init' argument in dataclass decorator."""

EXTRA: Literal["ignore", "forbid"] = "ignore"
"""Default value for 'extra' argument in dataclass decorator."""

REPR: bool = True
"""Default value for 'repr' argument in dataclass decorator."""

EQ: bool = True
"""Default value for 'eq' argument in dataclass decorator."""

ATTACH: bool = True
"""Default value for 'attach' argument in view decorator."""

RECURSIVE: bool = True
"""Default value for 'recursive' argument in dataclass decorator."""

HANDLE_CIRCULAR_REFS: bool = False
"""Default value for 'handle_circular_refs' argument in dataclass decorator."""
