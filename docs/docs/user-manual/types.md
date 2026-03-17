# Specialized Types

Cwtch provides specialized types for common use cases like URLs, secrets, and constrained values.

## Number Types

```python
from cwtch.types import Number, Negative, NonPositive, Positive, NonNegative

# Number can be int or float
value: Number = 1.5

# Negative - less than 0
negative: Negative[int] = -1

# NonPositive - less than or equal to 0
non_positive: NonPositive[int] = 0

# Positive - greater than 0
positive: Positive[int] = 1

# NonNegative - greater than or equal to 0
non_neg: NonNegative[int] = 0
```

## String Types

### LowerStr and UpperStr

Automatically convert strings to lower/upper case:

```python
from cwtch import dataclass
from cwtch.types import LowerStr, UpperStr

@dataclass
class User:
    username: LowerStr   # Converted to lowercase
    country: UpperStr    # Converted to uppercase

user = User(username="JOHN", country="us")
print(user.username)  # "john"
print(user.country)   # "US"
```

### NonEmpty and NonZeroLen

Constrain containers to be non-empty:

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.types import NonEmpty, NonZeroLen

@dataclass
class Config:
    # List must have at least 1 item
    tags: NonEmpty[list]
    
    # String must have at least 1 character
    name: NonZeroLen[str]
```

## URL Types

### Url

Basic URL type with validation:

```python
from cwtch import dataclass
from cwtch.types import Url

@dataclass
class Link:
    url: Url

link = Link(url="https://example.com")
print(link.url.scheme)   # "https"
print(link.url.hostname) # "example.com"
```

### HttpUrl

Restricts to HTTP/HTTPS schemes:

```python
from cwtch import dataclass
from cwtch.types import HttpUrl

@dataclass
class ApiConfig:
    base_url: HttpUrl

# Works
config = ApiConfig(base_url="https://api.example.com")

# Fails - not HTTP/HTTPS
# config = ApiConfig(base_url="ftp://example.com")  # ValidationError
```

### Other URL Types

```python
from cwtch.types import WebsocketpUrl, FtpUrl, FileUrl, SecretUrl, SecretHttpUrl

# WebSocket URLs (ws/wss)
ws_url: WebsocketpUrl

# FTP URLs
ftp_url: FtpUrl

# File URLs
file_url: FileUrl

# Secret URLs (redact credentials)
secret_url: SecretUrl
secret_http_url: SecretHttpUrl
```

## Secret Types

### SecretStr

Hides string values in repr and comparison:

```python
from cwtch import dataclass
from cwtch.types import SecretStr

@dataclass
class User:
    name: str
    password: SecretStr

user = User(name="John", password="secret123")
print(user)  # User(name='John', password=SecretStr(***))

# Get the actual value
print(user.password.get_secret_value())  # "secret123"
```

### SecretBytes

Similar to SecretStr but for bytes:

```python
from cwtch import dataclass
from cwtch.types import SecretBytes

@dataclass
class Config:
    api_key: SecretBytes

config = Config(api_key=b"secret-key")
print(config)  # Config(api_key=SecretBytes(***))
print(config.api_key.get_secret_value())  # b"secret-key"
```

## Strict Type

Ensures exact type matching without implicit conversions:

```python
from cwtch import dataclass
from cwtch.types import Strict

@dataclass
class User:
    age: Strict[int]
    height: Strict[float]
    
# These work
user = User(age=30, height=5.9)

# These fail
# user = User(age="30", ...)    # str not allowed
# user = User(height=5, ...)     # int not allowed as float
# user = User(age=True, ...)     # bool not allowed as int
```

## Unset Type

The `Unset` type is used internally to distinguish between "not provided" and "None":

```python
from cwtch.types import UNSET, Unset, UnsetType

# UNSET is a singleton representing an unset value
value = UNSET

# Use in type hints
def func(value: Unset[str] = UNSET):
    if value is UNSET:
        print("not provided")
    else:
        print(f"value: {value}")
```

## Combining with Validators

You can combine specialized types with validators:

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.types import LowerStr
from cwtch.metadata import MinLen

@dataclass
class Config:
    # LowerStr with minimum length
    username: Annotated[LowerStr, MinLen(3)]
```

## Custom Types with TypeWrapper

Use `TypeWrapper` to extend existing types with custom serialization and JSON schema behavior.

### Custom Serialization

Create a subclass of `TypeWrapper` with a wrapped type as generic parameter and implement `__cwtch_asjson__`:

```python
import datetime
from cwtch import dataclass, asjson, TypeWrapper

class DateTime(TypeWrapper[datetime.datetime]):
    def __cwtch_asjson__(self, **kwds):
        return self.strftime("%Y-%m-%d %H:%M:%S")

@dataclass
class Event:
    title: str
    timestamp: DateTime

event = Event(title="Party", timestamp=datetime.datetime(2024, 12, 25, 18, 0, 0))
print(asjson(event))
# b'{"title":"Party","timestamp":"2024-12-25 18:00:00"}'
```

### Custom JSON Schema

Implement `__cwtch_json_schema__` as a classmethod to customize the JSON schema:

```python
import datetime
from cwtch import TypeWrapper
from cwtch.core import make_json_schema

class DateTime(TypeWrapper[datetime.datetime]):
    @classmethod
    def __cwtch_json_schema__(cls, **kwds):
        return {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 datetime"
        }

schema = make_json_schema(DateTime)
print(schema)
# ({"type": "string", "format": "date-time", "description": "ISO 8601 datetime"}, {})
```

### Multiple Methods

You can combine both custom serialization and JSON schema:

```python
import datetime
from cwtch import dataclass, asjson, TypeWrapper
from cwtch.core import make_json_schema

class DateTime(TypeWrapper[datetime.datetime]):
    def __cwtch_asjson__(self, **kwds):
        return self.isoformat()

    @classmethod
    def __cwtch_json_schema__(cls, **kwds):
        return {"type": "string", "format": "date-time"}

@dataclass
class Event:
    created_at: DateTime

event = Event(created_at=datetime.datetime(2024, 1, 1, 12, 0, 0))
print(asjson(event))  # b'{"created_at":"2024-01-01T12:00:00"}'
print(make_json_schema(DateTime))  # ({"type": "string", "format": "date-time"}, {})
```

### Validation with TypeWrapper

TypeWrapper preserves the original type, so validation works seamlessly:

```python
import datetime
from cwtch import dataclass, TypeWrapper, ValidationError

class DateTime(TypeWrapper[datetime.datetime]):
    def __cwtch_asjson__(self, **kwds):
        return "DATE"

@dataclass
class Event:
    timestamp: DateTime

# Works - input is converted to datetime
event = Event(timestamp="2024-01-01")
print(type(event.timestamp))  # <class 'DateTime'>

# Fails - not a valid datetime
# Event(timestamp="invalid")  # ValidationError
```
