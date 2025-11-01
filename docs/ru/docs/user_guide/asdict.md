Функция `asdict` предназначена для преобразования объекта в словарь.

```python
from cwtch import asdict, dataclass

@dataclass
class M:
    i: int

d = M(1)
assert asdict(d) == {"i": 1}
```

В случае необходимости можно изменить поведение, определив метод `__cwtch_asdict__`

```python
@dataclass
class M:
    i: int

    def __cwtch_asdict__(self, handler: Callable, kwds: AsDictKwds):
        return handler()
```

!!! note

    ```python
    AsDictKwds = namedtuple("AsDictKwds", ("include", "exclude", "exclude_none", "exclude_unset", "context"))
    ```

Пример для `Secret` типа:

```python
class SecretType:
    def get_scret_value(self): ...

    def __cwtch_asdict__(self, handler, kwds: AsDictKwds):
        if (kwds.context or {}).get("show_secrets"):
            return self.get_secret_value()
        return self
```
