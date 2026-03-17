# Serialization

Cwtch provides built-in support for converting models to dictionaries and JSON.

## Converting to Dictionary

Use `asdict` to convert a model to a dictionary:

```python
from cwtch import dataclass, asdict

@dataclass
class User:
    name: str
    age: int

user = User(name="John", age=30)
data = asdict(user)
print(data)  # {'name': 'John', 'age': 30}
```

### Nested Models

`asdict` automatically handles nested models:

```python
from cwtch import dataclass, asdict

@dataclass
class Address:
    city: str
    zip_code: str

@dataclass
class User:
    name: str
    address: Address

user = User(name="John", address=Address(city="Boston", zip_code="02101"))
data = asdict(user)
print(data)
# {'name': 'John', 'address': {'city': 'Boston', 'zip_code': '02101'}}
```

### Options

```python
from cwtch import dataclass, asdict
from cwtch.types import SecretStr

@dataclass
class User:
    name: str
    email: str
    password: SecretStr

user = User(
    name="John",
    email="john@example.com",
    password="secret"
)

# Default - hides secret values
data = asdict(user)
print(data)  # {'name': 'John', 'email': 'john@example.com', 'password': SecretStr(***)}

# Show secrets (for SecretStr, SecretBytes, SecretUrl)
data = asdict(user, context={"show_secrets": True})
print(data)  # {'name': 'John', 'email': 'john@example.com', 'password': 'secret'}
```

## Converting to JSON

Use `asjson` to convert a model to a JSON string:

```python
from cwtch import dataclass, asjson

@dataclass
class User:
    name: str
    age: int

user = User(name="John", age=30)
json_str = asjson(user)
print(json_str)  # b'{"name": "John", "age": 30}'
```

### Nested Models

```python
from cwtch import dataclass, asjson

@dataclass
class Address:
    city: str
    zip_code: str

@dataclass
class User:
    name: str
    address: Address

user = User(name="John", address=Address(city="Boston", zip_code="02101"))
print(asjson(user))
# b'{"name": "John", "address": {"city": "Boston", "zip_code": "02101"}}'
```

### Options

```python
from cwtch import dataclass, asjson
from cwtch.types import SecretStr

@dataclass
class User:
    name: str
    email: str
    password: SecretStr

user = User(name="John", email="john@example.com", password="secret")

# Default
print(asjson(user))
# b'{"name":"John","email":"john@example.com","password":"***"}'

# Show secrets
print(asjson(user, context={"show_secrets": True}))
# b'{"name":"John","email":"john@example.com","password":"secret"}'
```

## JSON Schema

Generate JSON schema from models:

```python
from cwtch import dataclass, make_json_schema

@dataclass
class User:
    name: str
    age: int

schema = make_json_schema(User)
print(schema)
# Output:
# (
#     {'$ref': '#/$defs/User'},
#     {
#         'User': {
#             'type': 'object',
#             'properties': {
#                 'name': {'type': 'string'},
#                 'age': {'type': 'integer'}
#             },
#             'required': ['name', 'age']
#         }
#     }
# )
```

## Field Aliases

Use `asdict_alias` to rename fields in the output:

```python
from cwtch import dataclass, asdict, field

@dataclass
class User:
    first_name: str = field(asdict_alias="firstName")
    last_name: str = field(asdict_alias="lastName")
    email: str

user = User(first_name="John", last_name="Doe", email="john@example.com")
data = asdict(user)
print(data)
# {'firstName': 'John', 'lastName': 'Doe', 'email': 'john@example.com'}
```

## Custom Type Handling

You can customize how types are serialized by implementing `__cwtch_asdict__` or `__cwtch_asjson__` methods:

```python
from cwtch import dataclass, asdict

class CustomType:
    def __init__(self, value):
        self.value = value
    
    def __cwtch_asdict__(self, handler, kwds):
        return {"custom": self.value}
    
    def __cwtch_asjson__(self, context):
        return {"custom": self.value}

@dataclass
class Container:
    data: CustomType

container = Container(data=CustomType("test"))
print(asdict(container))  # {'data': {'custom': 'test'}}
```

## Using TypeWrapper

For a more powerful approach, use `TypeWrapper` to wrap existing types with custom serialization.
This is especially useful when you need the wrapped type to pass type validation:

```python
import datetime
from cwtch import dataclass, asjson, TypeWrapper

class DateTime(TypeWrapper[datetime.datetime]):
    def __cwtch_asjson__(self, **kwds):
        return self.strftime("%Y-%m-%d")

@dataclass
class Event:
    title: str
    timestamp: DateTime

event = Event(title="Party", timestamp=datetime.datetime(2024, 12, 25))
print(asjson(event))
# b'{"title":"Party","timestamp":"2024-12-25"}'
```

See [Types Guide](../user-manual/types.md#custom-types-with-typewrapper) for more examples.
