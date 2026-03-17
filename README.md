# cwtch - Python dataclasses with validation and views

[![PyPI version](https://img.shields.io/pypi/v/cwtch)](https://pypi.org/project/cwtch/)
![tests](https://github.com/levsh/cwtch/workflows/Checks/badge.svg)
![coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/levsh/f079c374abda6c5bd393c3ac723f1182/raw/coverage.json)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)

Cwtch extends Python's built-in `dataclasses` with automatic validation, views, and serialization support.

## Installation

```bash
pip install cwtch
```

## Quick Start

```python
from cwtch import dataclass

@dataclass
class User:
    name: str
    age: int
    email: str

user = User(name="John", age=30, email="john@example.com")
print(user)
# Output: User(name='John', age=30, email='john@example.com')
```

## Features

- **Automatic Validation** - Field types are validated on initialization
- **Views** - Create multiple representations of the same data model
- **Environment Variables** - Automatically populate fields from env vars
- **JSON Schema** - Generate JSON schemas from your models
- **Serialization** - Built-in `asdict` and `asjson` support

## Examples

### Validation

```python
from cwtch import dataclass, field

@dataclass
class M:
    i: int
    s: str = field(validate=False)

M(i=1, s='s')
# Output: M(i=1, s='s')

M(i='i', s='s')
# Raises ValidationError:
# ValidationError:
#   Type: <class '__main__.M'>
#   Path: ['i']
#   ValidationError:
#     Type: <class 'str'> --> <class 'int'>
#     Input: 'i'
#     ValueError: invalid literal for int() with base 10: 'i'
```

### Views

```python
from cwtch import dataclass, view
from cwtch.types import SecretStr

@dataclass
class User:
    name: str
    email: str
    password: SecretStr

@view(User, exclude={'password'})
class PublicUser:
    pass

user = User(name="John", email="john@example.com", password=SecretStr("secret"))
public = user.PublicUser()
print(public)
# Output: PublicUser(name='John', email='john@example.com')
```

### Serialization

```python
from cwtch import dataclass, asdict, asjson

@dataclass
class User:
    name: str
    age: int

user = User(name="John", age=30)

# To dictionary
asdict(user)
# Output: {'name': 'John', 'age': 30}

# To JSON
asjson(user)
# Output: b'{"name":"John","age":30}'
```

## Documentation

For full documentation, visit: https://levsh.github.io/cwtch

## License

MIT License - see [LICENSE](LICENSE) file for details.
