### Basic

View is a modified representation of a root model. 

```python
from cwtch import dataclass, view

@dataclass
class D:
    i: int
    s: str
    f: float

    @view(exclude={'s'})
    class V1:
        f: int

    @view(include={'s'})
    class V2:
        pass

d = D(i=0, s="s", f=1.1)

v1 = d.V1()
assert hasattr(v1, "i")
assert not hasattr(v1, "s")
assert hasattr(v1, "j")
assert v1.i == 0
assert v1.f == 1

v2 = d.V2()
assert not hasattr(v2, "i")
assert hasattr(v2, "s")
assert not hasattr(v2, "j")
assert v2.s == "s"
```


### Recursive

```python
from cwtch import dataclass, view

@dataclass
class A:
    i: int
    s: str

    @view(exclude={"s"})
    class V:
        pass

@dataclass
class B:
    a: A

    @view
    class V:
        pass

assert B.V.__annotations__ == {"a": A.V}
assert B.V.__dataclass_fields__["a"].type == A.V
```
