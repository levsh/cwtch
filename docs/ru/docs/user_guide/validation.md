### Настройка

Валидацией полей можно управлять как на уровне всего класса, так и отдельно для каждого поля.

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


### Валидация булевых типов

Значения из списка:

```python
[True, 1, "1", "true", "t", "y", "yes", "True", "TRUE", "Y", "Yes", "YES"]
```

трактуются как `True`.

Значения из списка:

```python
[False, 0, "0", "false", "f", "n", "no", "False", "FALSE", "N", "No", "NO"]
```

трактуются как `False`.


### Пост валидация

Для валидации модели после создания можно использовать `__post_validate__` метод.

!!! note
    **cwtch** перхватывает `ValueError` и `TypeError` исключения и оборачивает их в `ValidationError`.

```python
@dataclass
class D:
    i: int
    j: int

    def __post_validate__(self):
        if self.i + self.j < 10:
            raise ValueError("sum of i and j should be >= 10")
```


### Валидация на основе метадаты

Для валидации поля перед или после **cwtch** можно использовать валидаторы на основе `cwtch.metadata.TypeMetadata`.

```python
from cwtch.metadata import TypeMetadata

class CustomValidator(TypeMetadata):
    def before(self, value, /):
        """
        Валидация значения перед валидацией на основании аннотации типа
        """
        print("Before")
        return value

    def after(self, value, /):
        """
        Валидация значения после валидации на основании аннотации типа
        """
        print("After")
        return value

@dataclass
class D:
    i: Annotated[int, CustomValidator()]
```


### Встроенные валидаторы

```  python
from cwtch import dataclass
from cwtch.metadata import Validator
from typing import Annotated

@dataclass
class D:
    i: Annotated[int, Validator(after=lambda v: v / 2)]

>>> D(i='2')
D(i=1.0)
```

```python
from typing import Annotated
from cwtch import dataclass
from cwtch.metadata import Ge, Gt, Le, Lt, MaxItems, MaxLen, MinItems, MinLen
from cwtch.types import Positive, Strict

@dataclass
class D:
    i: Annotated[Strict[Positive[int]], Ge(1)]
    items: Annotated[list[int], MinItems(1)]
```

```python
>>> D(i=0, items=[0])
...
ValidationError: type[ <class '__main__.D'> ] path[ 'i' ]
  type[ Annotated[int, Ge(value=1)] ] input_type[ <class 'int'> ] input_value[ 0 ]
    ValueError: value should be >= 1
```

```python
>>> D(i=1, items=[])
...
ValidationError: type[ <class '__main__.D'> ] path[ 'items' ]
  type[ Annotated[list[int], MinItems(value=1)] ] input_type[ <class 'list'> ] input_value[ [] ]
    ValueError: items count should be >= 1
```
