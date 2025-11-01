``` python
from cwtch import dataclass

@dataclass
class M:
    i: int
    s: str
    b: bool
```

!!! info
    By default **cwtch** validates input arguments according to class annotations.

```python
>>> print(M(i=0, s='s', b=True))
M(i=0, s='s', b=True)
```

```python
>>> print(M(i='0', s=1, b='f'))
M(i=0, s='1', b=False)
```

```python
>>> print(M(i='a', s='s', b=True))
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "<string>", line 32, in __init__
cwtch.errors.ValidationError: 
  Type: --> <class '__main__.M'>
  Path: ['i']
  ValidationError:
    Type: <class 'str'> --> <class 'int'>
    Input: 'a'
    ValueError: invalid literal for int() with base 10: 'a'
```
