from typing import Literal


SLOTS: bool = False
"""Default value for 'slots' argument in dataclass decorator."""

KW_ONLY: bool = False
"""Default value for 'kw_only' argument in dataclass decorator."""

VALIDATE: bool = True
"""Default value for 'validate' argument in dataclass decorator."""

RAISE_ON_FIRST_ERROR: bool = True
"""Raise ValidationError on first validation error. """

ADD_DISABLE_VALIDATION_TO_INIT: bool = False
"""Default value for 'add_disable_validation_to_init' argument in dataclass decorator."""

SHOW_INPUT_VALUE_ON_ERROR: bool = True
"""Show input value on ValidationError."""

EXTRA: Literal["ignore", "forbid"] = "forbid"
"""Default value for 'extra' argument in dataclass decorator."""

REPR: bool = True
"""Default value for 'repr' argument in dataclass decorator."""

EQ: bool = True
"""Default value for 'eq' argument in dataclass decorator."""

ATTACH: bool = True
"""Default value for 'attach' argument in view decorator."""

RECURSIVE: bool = True
"""Default value for 'recursive' argument in dataclass decorator."""
