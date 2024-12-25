### Введение

Представления или view могут быть полезны когда нужно удалить/добавить поле или поменять его тип
без полного дублирования исходной модели.

```python
from cwtch import dataclass, view

@dataclass
class Model:
    i: int
    s: str
    f: float

@view(Model, 'V1', exclude=['s'])
class ModelV1:
    f: int

@view(Model, 'V2', include=['s'])
class ModelV2:
    pass

model = Model(i=0, s="s", f=1.1)

v1 = model.V1()
assert hasattr(v1, "i")
assert not hasattr(v1, "s")
assert hasattr(v1, "f")
assert v1.i == 0
assert v1.f == 1

v2 = model.V2()
assert not hasattr(v2, "i")
assert hasattr(v2, "s")
assert not hasattr(v2, "f")
assert v2.s == "s"

v1 = Model.V1(i=0, f=1.1)
v2 = Model.V2(s="s")
```


### Рекурсивные модели

При использовании вложенных моделей опция `recursive=True` позволяет автоматичеки выбрать
правильное представление у вложенной модели.

```python
from cwtch import dataclass, view

@dataclass
class A:
    i: int
    s: str

@view(A, 'V', exclude=["s"], recursive=True)
class AV:
    pass

@dataclass
class B:
    a: A

@view(B, 'V')
class BV:
    pass

assert B.V.__dataclass_fields__["a"].type == A.V
```
