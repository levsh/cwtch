Синтакстис **cwtch** dataclass очень похож на стандартный `dataclasses.dataclass`.

```python
from cwtch import dataclass

@dataclass
class M:
    i: int
    s: str
    b: bool
```

!!! info
    С настройками по умолчанию входные аргументы при создании экземпляра класса будут провалидированы
    согласно аннотации типов.

```python
>>> print(M(i=0, s='s', b=True))
M(i=0, s='s', b=True)
```

```python
>>> print(M(i='0', s=1, b='f'))
M(i=0, s='1', b=False)
```

В случае ошибки валидации будет выброшено исключение `ValidationError`.

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
