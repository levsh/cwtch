### Disable validation by default

```python
from cwtch import dataclass

@dataclass(validate=False)
class D:
    i: int
```

```python
>>> print(D(i="a")
D(i="a")
```

### Setting up validation per field

```python
from cwtch import dataclass, field

@dataclass
class D:
    i: int = field(validate=False)
    s: str
```

```python
>>> D(i="a", s=1)
D(i="a", s="1")
```

### Boolean value validation

Values from the list 
```python
[True, 1, "1", "true", "t", "y", "yes", "True", "TRUE", "Y", "Yes", "YES"]
```
are treated as `True`.

Values from the list 
```python
[False, 0, "0", "false", "f", "n", "no", "False", "FALSE", "N", "No", "NO"]
```
are treated as `False`.


### Model post validattion

To validate model after init use `dataclass` `__post_init__` method.

**cwtch** listens `ValueError` and `TypeError` exceptions and reraise them as `ValidationError`.

```python

@dataclass
class D:
    i: int
    j: int

    def __post_init__(self):
        if self.i + self.j < 10:
            raise ValueError("sum of i and j should be >= 10")
```

### Type metadata

To validate field value (`before` or `after` mode) use validators based on `cwtch.TypeMetadata`
together with Python `Annotated` feature.

```python
from cwtch import TypeMetadata

class CustomValidator(TypeMetadata):
    def convert(self, value) -> Any:
        """Convert field value before validation."""
        ...
        return value

    def validate_before(self, value, /):
        """
        Validate field value before validation
        based on dataclass type annotations.
        """
        ...

    def validate_after(self, value, /):
        """
        Validate field value after validation
        based on dataclass type annotations.
        """
        ...

@dataclass
class D:
    i: Annotated[int, CustomValidator()]
```

#### Built-in validators


```python
from typing import Annotated
from cwtch import Ge, Gt, Le, Lt, MaxItems, MaxLen, MinItems, MinLen, dataclass

@dataclass
class D:
    i: Annotated[int, Ge(1)]
    items: Annotated[list[int], MinItems(1)]
```

```python
>>> D(i=0, items=[0])
Traceback (most recent call last):
...
During handling of the above exception, another exception occurred:

Traceback (most recent call last):
    ...
    D(i=0, items=[0])
  File "<string>", line 9, in __init__
cwtch.errors.ValidationError: validation error for <class '__main__.D'> path=['i']
  validation error for typing.Annotated[int, Ge(value=1)]
    - value should be >= 1
```

```python
>>> D(i=0, items=[0])
Traceback (most recent call last):
...
During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "...", line 12, in <module>
    D(i=1, items=[])
  File "<string>", line 13, in __init__
cwtch.errors.ValidationError: validation error for <class '__main__.D'> path=['items']
  validation error for typing.Annotated[list[int], MinLen(value=1)]
    - items count should be >= 1
```
