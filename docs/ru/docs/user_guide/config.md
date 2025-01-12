**cwtch** датакласс можно использовать как конфиг с инициализацией значений из переменных окружения.

```python
@dataclass(env_prefix="APP_")
class AppConfig:
    log_level: Annotated[Literal['DEBUG', 'INFO'], ToUpper(mode="before")] = "INFO"
    # значение log_level можно задать через переменную окружения 'APP_LOG_LEVEL'

    non_env_field: str = field(metadata={"env_var": False})
    # значение non_env_field нельзя задать через переменную окружения 'APP_NON_ENV_FIELD'
```

В случае необходимости возможно использование списка префиксов для переменных окружения.

```python
@dataclass(env_prefix=["APP_", "APPLICATION_"])
class AppConfig:
    log_level: Annotated[Literal['DEBUG', 'INFO'], ToUpper(mode="before")] = "INFO"
    ...
```

В таком случае поиск значения для атрибута `log_level` будет осуществляться в порядке указания префиксов, т.е. сначала
`APP_LOG_LEVEL` и если данная переменная не определена, то затем `APPLICATION_LOG_LEVEL`.

### Источник

По умолчанию в качестве источника для переменных оркужения используется `os.environ`.
Данное поведение можно переопределить путем указания параметра `env_source` в виде функции без аргументов.

```python
@dataclass(env_prefix="APP_", env_source=lambda: {"APP_LOG_LEVEL": "debug"})
class AppConfig:
    log_level: Annotated[Literal['DEBUG', 'INFO'], ToUpper(mode="before")] = "INFO"

assert AppConfig().log_level == "DEBUG"
```
