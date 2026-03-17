# Cwtch

**Cwtch** is a Python library that provides enhanced dataclass functionality with built-in validation and views support.

## Features

- **Automatic Validation**: Field types are automatically validated on initialization
- **Views**: Create multiple representations of the same data model
- **Environment Variables**: Automatically populate fields from environment variables
- **JSON Schema Generation**: Generate JSON schemas from your models
- **Serialization**: Built-in support for converting models to dictionaries and JSON
- **Global Configuration**: Customize default behavior for all dataclasses

## Quick Start

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

## Why Cwtch?

Python's built-in `dataclasses` are great for simple data containers, but they lack:
- Automatic type validation
- Multiple views of the same data
- Environment variable integration
- JSON schema generation

Cwtch extends dataclasses with these features while maintaining a familiar API.
