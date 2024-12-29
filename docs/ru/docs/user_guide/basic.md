Синтакстис **cwtch** dataclass очень похож на стандартный `dataclasses.dataclass`.

```python
from cwtch import dataclass

@dataclass
class D:
    i: int
    s: str
    b: bool
```

!!! info
    С настройками по умолчанию входные аргументы при создании экземпляра класса будут провалидированы
    согласно аннотации типов.

```python
>>> print(D(i=0, s='s', b=True))
D(i=0, s='s', b=True)
```

```python
>>> print(D(i='0', s=1, b='f'))
D(i=0, s='1', b=False)
```

В случае ошибки валидации будет выброшено исключение `ValidationError`.

```python
>>> print(D(i='a', s='s', b=True))
...
ValidationError: type[ <class '__main__.D'> ] path[ 'i' ]
  type[ <class 'int'> ] input_type[ <class 'str'> ] input_value[ 'a' ]
    ValueError: invalid literal for int() with base 10: 'a'
```
