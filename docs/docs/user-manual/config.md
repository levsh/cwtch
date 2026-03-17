# Global Configuration

Cwtch provides a global configuration module that controls default behavior for all dataclasses:

```python
from cwtch import config
```

## Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `SLOTS` | `bool` | `False` | Default value for `slots` argument |
| `KW_ONLY` | `bool` | `False` | Default value for `kw_only` argument |
| `VALIDATE` | `bool` | `True` | Default value for `validate` argument |
| `EXTRA` | `str` | `"forbid"` | Default value for `extra` argument (`"forbid"` or `"ignore"`) |
| `REPR` | `bool` | `True` | Default value for `repr` argument |
| `EQ` | `bool` | `True` | Default value for `eq` argument |
| `ATTACH` | `bool` | `True` | Default value for `attach` argument in views |
| `RECURSIVE` | `bool` | `True` | Default value for `recursive` argument |
| `RAISE_ON_FIRST_ERROR` | `bool` | `True` | Raise on first validation error or collect all errors |
| `SHOW_INPUT_VALUE_ON_ERROR` | `bool` | `True` | Show input value in validation error messages |
| `ADD_DISABLE_VALIDATION_TO_INIT` | `bool` | `False` | Default value for `add_disable_validation_to_init` argument |

## Usage

The global config is used when the corresponding argument is not explicitly provided to the decorator:

```python
from cwtch import dataclass, config

# Change global default
config.VALIDATE = False
config.EXTRA = "ignore"

# This dataclass will use the global defaults
@dataclass
class User:
    name: str
    age: int

# Now validation is disabled by default
user = User(name="John", age="thirty")  # Works, no validation!
```

## Important Notes

### Config is read at class definition time

The decorator reads config values when the class is defined. Changing `config` values will only affect classes defined *after* the change:

```python
from cwtch import dataclass, config

@dataclass
class First:
    value: int  # Will have validation=True (default)

config.VALIDATE = False  # Change after first class

@dataclass
class Second:
    value: int  # Will have validation=False (from global config)
```

### Use explicit arguments for per-class control

For individual classes, always pass the argument explicitly to ensure consistent behavior:

```python
# Explicit is always clearer and more reliable
@dataclass(validate=True)
class User:
    name: str
```

### Runtime validation control

Use `add_disable_validation_to_init=True` to control validation at runtime:

```python
@dataclass(add_disable_validation_to_init=True)
class User:
    name: str
    age: int

# Validation enabled (default)
user = User(name="John", age=30)

# Validation disabled at runtime
user = User(name="John", age="thirty", disable_validation=True)
```
