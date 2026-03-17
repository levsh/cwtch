# Field Configuration

The `field()` function allows you to customize individual field behavior.

## Basic Usage

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    age: int = field(default=0)
```

## Field Options

### `default`

Set a default value for the field:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    age: int = field(default=18)
```

### `default_factory`

Use a callable to generate the default value:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
```

### `init`

Control whether the field is included in `__init__`:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    internal_id: str = field(init=False, default="generated-id")
```

### `init_alias`

Provide an alternative name for the field in `__init__`:

```python
from cwtch import dataclass, field

@dataclass
class User:
    first_name: str = field(init_alias="name")

# Use the alias
user = User(name="John")
print(user.first_name)  # "John"
```

### `asdict_alias`

Provide an alternative name when converting to dictionary:

```python
from cwtch import dataclass, field, asdict

@dataclass
class User:
    first_name: str = field(asdict_alias="name")
    age: int

user = User(first_name="John", age=30)
print(asdict(user))  # {'name': 'John', 'age': 30}
```

### `repr`

Control whether the field appears in `__repr__`:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    password: str = field(repr=False)

user = User(name="John", password="secret")
print(user)  # User(name='John')
```

### `compare`

Control whether the field is used in comparisons:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    internal_id: str = field(compare=False)

user1 = User(name="John", internal_id="1")
user2 = User(name="John", internal_id="2")
print(user1 == user2)  # True (internal_id ignored)
```

### `property`

Convert the field to a property. The value is validated and converted during initialization:

```python
from cwtch import dataclass, field

@dataclass
class User:
    first_name: str
    last_name: str
    full_name: str = field(property=True)

# Value is validated and converted to property
user = User(first_name="John", last_name="Doe", full_name="John Doe")
print(user.full_name)  # "John Doe"
```

### `validate`

Disable validation for a specific field:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    # age won't be validated
    age: int = field(validate=False)
```

### `metadata`

Attach custom metadata to a field:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str = field(metadata={"description": "User's full name"})
```

### `kw_only`

Make the field keyword-only:

```python
from cwtch import dataclass, field

@dataclass
class User:
    name: str
    age: int = field(kw_only=True)

# age must be passed as keyword argument
user = User("John", age=30)
# Output: User(name='John', age=30)
```

## Computed Fields

Create computed fields using `computed_field`:

```python
from cwtch import dataclass, computed_field

@dataclass
class Rectangle:
    width: float
    height: float
    
    @computed_field
    @property
    def area(self) -> float:
        return self.width * self.height

rect = Rectangle(width=5, height=3)
print(rect.area)  # 15.0
```
