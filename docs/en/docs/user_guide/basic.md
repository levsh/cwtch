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
...
ValidationError: type[ <class '__main__.D'> ] path[ 'i' ]
  type[ <class 'int'> ] input_type[ <class 'str'> ] input_value[ 'a' ]
    Error: invalid literal for int() with base 10: 'a'
```
