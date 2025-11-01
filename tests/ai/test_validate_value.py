import pytest

from cwtch import cwtch
from cwtch.cwtch import dataclass
from cwtch.types import SecretBytes, SecretStr, SecretUrl, Url


def test_validate_value_int():
    assert cwtch.validate_value(123, int) == 123


def test_validate_value_str():
    assert cwtch.validate_value("abc", str) == "abc"


def test_validate_value_invalid():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value([], int)


def test_validate_value_float():
    assert cwtch.validate_value(1.23, float) == 1.23


def test_validate_value_bool():
    assert cwtch.validate_value(True, bool) is True
    assert cwtch.validate_value(False, bool) is False


def test_validate_value_bytes():
    assert cwtch.validate_value(b"abc", bytes) == b"abc"


def test_validate_value_list():
    assert cwtch.validate_value([1, 2, 3], list) == [1, 2, 3]


def test_validate_value_tuple():
    assert cwtch.validate_value((1, 2), tuple) == (1, 2)


def test_validate_value_set():
    assert cwtch.validate_value({1, 2}, set) == {1, 2}


def test_validate_value_dict():
    assert cwtch.validate_value({"a": 1}, dict) == {"a": 1}


def test_validate_value_none():
    assert cwtch.validate_value(None, type(None)) is None


def test_validate_value_secret_bytes():
    val = SecretBytes(b"secret")
    assert cwtch.validate_value(val, SecretBytes) == val


def test_validate_value_secret_str():
    val = SecretStr("secret")
    assert cwtch.validate_value(val, SecretStr) == val


def test_validate_value_url():
    val = Url("https://user:pass@host:1234/path?query=1#frag")
    assert cwtch.validate_value(val, Url) == val


def test_validate_value_secret_url():
    val = SecretUrl("https://user:pass@host:1234/path?query=1#frag")
    assert cwtch.validate_value(val, SecretUrl) == val


def test_validate_value_dataclass():
    @dataclass
    class User:
        id: int
        name: str

    u = User(id=1, name="test")
    assert cwtch.validate_value(u, User) == u


def test_validate_value_nested_dataclass():
    @dataclass
    class Address:
        city: str

    @dataclass
    class User:
        id: int
        address: Address

    u = User(id=1, address=Address(city="Moscow"))
    assert cwtch.validate_value(u, User) == u


def test_validate_value_annotated():
    from typing import Annotated

    T = Annotated[int, "meta"]
    assert cwtch.validate_value(5, T) == 5


def test_validate_value_generic():
    from typing import Generic, TypeVar

    T = TypeVar("T")

    class Box(Generic[T]):
        def __init__(self, value: T):
            self.value = value

        def __eq__(self, other):
            return isinstance(other, Box) and self.value == other.value

    b = Box(123)
    assert cwtch.validate_value(b, Box) == b


def test_validate_value_union():
    from typing import Union

    assert cwtch.validate_value(1, Union[int, str]) == 1
    assert cwtch.validate_value("a", Union[int, str]) == "a"


def test_validate_value_int_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, int)


def test_validate_value_str_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, str)


def test_validate_value_float_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, float)


def test_validate_value_bool_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value("not bool", bool)


def test_validate_value_bytes_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, bytes)


def test_validate_value_list_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, list)


def test_validate_value_tuple_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, tuple)


def test_validate_value_set_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, set)


def test_validate_value_dict_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, dict)


def test_validate_value_none_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(0, type(None))


def test_validate_value_secret_bytes_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, SecretBytes)


def test_validate_value_secret_str_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, SecretStr)


def test_validate_value_url_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, Url)


def test_validate_value_secret_url_negative():
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, SecretUrl)


def test_validate_value_annotated_negative():
    from typing import Annotated

    T = Annotated[int, "meta"]
    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, T)


def test_validate_value_generic_negative():
    from typing import Generic, TypeVar

    T = TypeVar("T")

    class Box(Generic[T]):
        def __init__(self, value: T):
            self.value = value

        def __eq__(self, other):
            return isinstance(other, Box) and self.value == other.value

    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(123, Box[bool])


def test_validate_value_union_negative():
    from typing import Union

    with pytest.raises(cwtch.ValidationError):
        cwtch.validate_value(None, Union[int, str])
