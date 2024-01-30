**cwtch** redefines `dataclass` decorator and `field` function from Python `dataclasses` module.

!!! note
    Only keyword only arguments are supported at this moment.


``` python
from cwtch import dataclass

@dataclass
class D:
    i: int
    s: str
    b: bool
```

!!! info
    By default **cwtch** validates input arguments according to class annotations.

```python
>>> print(D(i=0, s='s', b=True))
D(i=0, s='s', b=True)
```

```python
>>> print(D(i='0', s=1, b='f'))
D(i=0, s='1', b=False)
```

```python
>>> print(D(i='a', s='s', b=True))
Traceback (most recent call last):
  File "ext/core.pyx", line 599, in cwtch.core.make.validate_value_using_validator
    return validator(value, T)
  File "ext/core.pyx", line 124, in cwtch.core.make.validate_int
    return PyNumber_Long(value)
ValueError: invalid literal for int() with base 10: 'a'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<string>", line 7, in __init__
  File "ext/core.pyx", line 611, in cwtch.core.make.validate_value_using_validator
    raise ValidationError(value, T, [e], parameters=parameters)
cwtch.errors.ValidationError: validation error for <class 'int'>
  - invalid literal for int() with base 10: 'a'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "<string>", line 9, in __init__
cwtch.errors.ValidationError: validation error for <class '__main__.D'> path=['i']
  validation error for <class 'int'>
    - invalid literal for int() with base 10: 'a'
```
