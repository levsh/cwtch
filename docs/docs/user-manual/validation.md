# Validation

Cwtch provides comprehensive validation capabilities through the `Annotated` type and metadata validators.

## Automatic Validation

By default, Cwtch validates all field types:

```python
from cwtch import dataclass

@dataclass
class User:
    name: str
    age: int
    email: str

# Valid
user = User(name="John", age=30, email="john@example.com")

# Invalid - raises ValidationError
try:
    user = User(name="John", age="thirty", email="john@example.com")
except Exception as e:
    print(e)
```

## Built-in Validators

### Numeric Constraints

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.metadata import Ge, Gt, Le, Lt

@dataclass
class Product:
    # Greater than or equal to 0
    quantity: Annotated[int, Ge(0)]
    
    # Greater than 0 (positive)
    price: Annotated[float, Gt(0)]
    
    # Less than or equal to 100
    discount_percent: Annotated[float, Le(100)]
    
    # Less than 18 (not for children)
    minimum_age: Annotated[int, Lt(18)]
```

### String Constraints

```python
import re
from typing import Annotated
from cwtch import dataclass
from cwtch.metadata import MinLen, MaxLen, Len, Match

@dataclass
class User:
    # String length constraints
    username: Annotated[str, MinLen(3), MaxLen(20)]
    password: Annotated[str, Len(8, 128)]  # min, max
    
    # Pattern matching (use re.compile)
    phone: Annotated[str, Match(re.compile(r"^\+?[1-9]\d{1,14}$"))]
```

### List/Collection Constraints

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.metadata import MinItems, MaxItems

@dataclass
class Team:
    # At least 1 member
    members: Annotated[list[str], MinItems(1)]
    
    # At most 10 members
    max_members: Annotated[list[str], MaxItems(10)]
```

### Case Conversion

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.types import LowerStr, UpperStr

@dataclass
class User:
    # Automatically converted to lowercase
    username: LowerStr
    
    # Automatically converted to uppercase
    country_code: UpperStr

user = User(username="JOHN", country_code="us")
print(user.username)     # "john"
print(user.country_code) # "US"
```

## Custom Validators

### Using Validator Class

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.metadata import Validator

def is_even(value: int) -> int:
    if value % 2 != 0:
        raise ValueError("value must be even")
    return value

@dataclass
class Number:
    value: Annotated[int, Validator(after=is_even)]

num = Number(value=4)  # Works
num = Number(value=5)  # Raises ValidationError
```

### URL Constraints

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.types import HttpUrl, WebsocketpUrl, FtpUrl, FileUrl

@dataclass
class Config:
    # Only HTTP/HTTPS URLs
    api_url: HttpUrl
    
    # Only WS/WSS URLs  
    websocket_url: WebsocketpUrl
    
    # Only FTP URLs
    ftp_url: FtpUrl
    
    # Only file:// URLs
    local_path: FileUrl
```

## Strict Type Validation

Use `Strict` to enforce exact type matching:

```python
from cwtch import dataclass
from cwtch.types import Strict

@dataclass
class User:
    # Won't accept "1" (str) as int
    age: Strict[int]
    
    # Won't accept 1 (int) as float  
    height: Strict[float]
    
    # Won't accept True (bool) as int
    count: Strict[int]

# These work
user = User(age=30, height=5.9, count=5)

# These raise ValidationError
# user = User(age="30", ...)    # str not accepted as int
# user = User(height=5, ...)    # int not accepted as float
# user = User(count=True, ...)  # bool not accepted as int
```

## Disabling Validation

### Per-Field

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    # Disable validation for this field
    age: int = field(validate=False)
```

### Per-Model

```python
from cwtch import dataclass

@dataclass(validate=False)
class User:
    name: str
    age: int
```

### At Runtime

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

## Manual Validation

You can validate values manually using `validate_value`:

```python
from typing import Annotated
from cwtch import validate_value
from cwtch.metadata import Ge, MinLen

# Validate a single value
result = validate_value(5, Annotated[int, Ge(0)])
print(result)  # 5

# Validation error
try:
    validate_value(-1, Annotated[int, Ge(0)])
except Exception as e:
    print(e)
```

## Post-Init and Post-Validate Hooks

You can define `__post_init__` and `__post_validate__` methods:

```python
from cwtch import dataclass

@dataclass
class User:
    name: str
    age: int
    
    def __post_init__(self):
        print(f"User created: {self.name}")
    
    def __post_validate__(self):
        if self.age < 0:
            raise ValueError("Age cannot be negative")
```

## Differences Between `__post_init__` and `__post_validate__`

The actual execution order in Cwtch is:

1. **Base type validation** (e.g., converting "10" to int)
2. **Custom validators** (Ge, MinLen, etc.) - validate the **original input value**
3. **`__post_init__`** - runs after validators, can modify values
4. **`__post_validate__`** - final validation hook

| Feature | `__post_init__` | `__post_validate__` |
|---------|------------------|---------------------|
| **Execution order** | Runs 3rd (after validators) | Runs 4th (last) |
| **Can modify fields** | Yes - changes are NOT re-validated | Yes - changes are NOT re-validated |
| **Validators run** | Already completed before this hook | Already completed |
| **Inheritance** | Only from own class (`__dict__`) | Inherits from parents (`getattr`) |


### Inheritance Difference

```python
from cwtch import dataclass

class Base:
    def __post_init__(self):
        print("Base.__post_init__")
    
    def __post_validate__(self):
        print("Base.__post_validate__")

@dataclass
class Child(Base):
    name: str
    # No hooks defined here

child = Child(name="John")
# Output: Base.__post_validate__
# Note: __post_init__ from parent is NOT called (only from __dict__)
```

## Function Validation

Cwtch provides utilities to validate function arguments and decorate functions with automatic validation.

### validate_call

Use `validate_call` as a decorator to automatically validate function arguments:

```python
from cwtch import validate_call

@validate_call
def create_user(name: str, age: int):
    return {"name": name, "age": age}

# Valid call - arguments are validated and converted
user = create_user("John", "30")  # age is converted to int
print(user)  # {'name': 'John', 'age': 30}

# Invalid call - raises ValidationError
# user = create_user("John", "thirty")  # ValidationError
```

### validate_args

Use `validate_args` to manually validate function arguments:

```python
from cwtch import validate_args

def create_user(name: str, age: int):
    validated_args, validated_kwds = validate_args(create_user, ("John", "30"), {})
    return {"name": validated_args[0], "age": validated_args[1]}

user = create_user("John", "30")
print(user)  # {'name': 'John', 'age': 30}
```
