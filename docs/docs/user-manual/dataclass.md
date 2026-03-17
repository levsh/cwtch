# Dataclass

The `@dataclass` decorator is the primary way to create Cwtch models.

It extends Python's built-in dataclass with additional features.

## Basic Usage

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    age: int
    email: str

user = User(name="John", age=30, email="john@example.com")
print(user)
# Output: User(name='John', age=30, email='john@example.com')
```

## Automatic Validation

Cwtch automatically validates field types during initialization:

```python
from cwtch import dataclass

@dataclass
class User:
    name: str
    age: int

# This will raise a ValidationError
try:
    user = User(name="John", age="thirty")
except Exception as e:
    print(e)
```

Output:
```
ValidationError: 
  Type: <class 'str'> --> <class 'int'>
  Input: 'thirty'
  ValueError: invalid literal for int() with base 10: 'thirty'
```

## Options

The `@dataclass` decorator accepts several options:

### `slots`

Use `__slots__` for memory efficiency:

```python
@dataclass(slots=True)
class User:
    name: str
```

### `kw_only`

Make all fields keyword-only:

```python
@dataclass(kw_only=True)
class User:
    name: str
    age: int

# Must use keyword arguments
user = User(name="John", age=30)
```

### `validate`

Disable validation for the entire class:

```python
@dataclass(validate=False)
class User:
    name: str
    age: int

# No validation occurs
user = User(name="John", age="thirty")  # Works!
```

### `repr`

Control `__repr__` generation (default: True):

```python
@dataclass(repr=True)  # Default
class User:
    name: str

print(User(name="John"))  # User(name='John')
```

### `eq`

Control `__eq__` generation (default: True):

```python
@dataclass(eq=True)  # Default
class User:
    name: str

print(User(name="John") == User(name="John"))  # True
```

### `extra`

Control handling of extra arguments:

```python
@dataclass(extra="forbid")  # Raises error on extra args
class User:
    name: str

# This will raise TypeError
# user = User(name="John", extra_field="value")
```

### `add_disable_validation_to_init`

Add a `disable_validation` parameter to `__init__`:

```python
from cwtch import dataclass

@dataclass(add_disable_validation_to_init=True)
class User:
    name: str
    age: int

# Validation enabled (default)
user = User(name="John", age=30)

# Validation disabled
user = User(name="John", age="thirty", disable_validation=True)
```

## Environment Variables

Cwtch can automatically populate fields from environment variables:

```python
import os
from cwtch import dataclass

os.environ["USER_NAME"] = "John"
os.environ["USER_AGE"] = "30"

@dataclass(env_prefix="USER_")
class User:
    name: str
    age: int

user = User()
print(user.name)  # "John"
print(user.age)   # 30
```

### Custom Environment Source

You can provide a custom environment source. Note: `env_prefix` must also be specified:

```python
from cwtch import dataclass

@dataclass(
    env_prefix="CUSTOM_",
    env_source=lambda: {"CUSTOM_NAME": "John", "CUSTOM_AGE": "30"}
)
class User:
    name: str
    age: int

user = User()     # Values loaded from custom source
print(user.name)  # "John"
```

### Multiple Environment Prefixes

You can use multiple `env_prefix` values as a list.
This is useful when you have environment variables coming from different sources with different naming conventions:

```python
import os
from cwtch import dataclass

# Set up environment variables from different sources
os.environ["APP_USER_NAME"] = "John"           # from app config
os.environ["DATABASE_USER_NAME"] = "Jane"      # from database config
os.environ["USER_AGE"] = "30"                  # generic prefix

# With single prefix - checks only one source
@dataclass(env_prefix="USER_")
class User1:
    name: str
    age: int

user1 = User1()
print(user1.name)  # "30" (matches USER_AGE, not USER_NAME)

# With multiple prefixes - checks each in order
@dataclass(env_prefix=["APP_", "DATABASE_", "USER_"])
class User2:
    name: str
    age: int

user2 = User2()
print(user2.name)   # "John" (found first in APP_USER_NAME)
print(user2.age)    # "30" (found in USER_AGE)
```

**How it works:**

- When multiple prefixes are provided, Cwtch checks each prefix in order
- For each field, it looks for an environment variable using the pattern `{prefix}{field_name}`
- The first match wins - order matters!
- You can also use custom field names via metadata:

```python
from cwtch import dataclass, field

@dataclass(env_prefix=["APP_", "CFG_"])
class Config:
    # Use custom env_var name in metadata
    debug_mode: bool = field(default=False, metadata={"env_var": "DEBUG"})
```

## Lifecycle Hooks

Cwtch supports `__post_init__` and `__post_validate__` lifecycle hooks. See the [Validation](validation.md) section for details.

## Resolving Types

Use `resolve_types` or `.cwtch_update_forward_refs()` to resolve forward references in type annotations:

```python
from cwtch import dataclass, resolve_types

@dataclass
class Child:
    parent: list['Parent']

@dataclass
class Parent:
    childern: list['Child']
    
resolve_types(Child)  # or Child.cwtch_update_forward_refs()
resolve_types(Parent) # or Parent.cwtch_update_forward_refs()
```
