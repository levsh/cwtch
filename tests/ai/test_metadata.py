import re

import pytest

from cwtch.core import nop
from cwtch.errors import ValidationError
from cwtch.metadata import *
from cwtch.types import Url


def test_all_exports():
    """Test that all classes in __all__ are importable."""
    expected = [
        "Validator",
        "Ge",
        "Gt",
        "Le",
        "Lt",
        "MinLen",
        "MaxLen",
        "Len",
        "MinItems",
        "MaxItems",
        "Match",
        "UrlConstraints",
        "JsonLoads",
        "ToLower",
        "ToUpper",
        "Strict",
    ]
    assert all(hasattr(__import__("cwtch.metadata", fromlist=[name]), name) for name in expected)


class TestValidator:
    def test_instantiation(self):
        v = Validator()
        assert v.json_schema == {}
        assert v.before == nop
        assert v.after == nop

    def test_custom_json_schema(self):
        v = Validator(json_schema={"type": "string"})
        assert v.json_schema == {"type": "string"}

    def test_before_after_callable(self):
        def dummy(value):
            return value

        v = Validator(before=dummy, after=dummy)
        assert v.before == dummy
        assert v.after == dummy


class TestGe:
    def test_instantiation(self):
        ge = Ge(5)
        assert ge.value == 5

    def test_json_schema(self):
        ge = Ge(10)
        assert ge.json_schema() == {"minimum": 10}

    def test_after_valid(self):
        ge = Ge(5)
        assert ge.after(5) == 5
        assert ge.after(6) == 6

    def test_after_invalid(self):
        ge = Ge(5)
        with pytest.raises(ValueError, match="value should be >= 5"):
            ge.after(4)


class TestGt:
    def test_instantiation(self):
        gt = Gt(5)
        assert gt.value == 5

    def test_json_schema(self):
        gt = Gt(10)
        assert gt.json_schema() == {"minimum": 10, "exclusiveMinimum": True}

    def test_after_valid(self):
        gt = Gt(5)
        assert gt.after(6) == 6

    def test_after_invalid(self):
        gt = Gt(5)
        with pytest.raises(ValueError, match="value should be > 5"):
            gt.after(5)
        with pytest.raises(ValueError, match="value should be > 5"):
            gt.after(4)


class TestLe:
    def test_instantiation(self):
        le = Le(5)
        assert le.value == 5

    def test_json_schema(self):
        le = Le(10)
        assert le.json_schema() == {"maximum": 10}

    def test_after_valid(self):
        le = Le(5)
        assert le.after(5) == 5
        assert le.after(4) == 4

    def test_after_invalid(self):
        le = Le(5)
        with pytest.raises(ValueError, match="value should be <= 5"):
            le.after(6)


class TestLt:
    def test_instantiation(self):
        lt = Lt(5)
        assert lt.value == 5

    def test_json_schema(self):
        lt = Lt(10)
        assert lt.json_schema() == {"maximum": 10, "exclusiveMaximum": True}

    def test_after_valid(self):
        lt = Lt(5)
        assert lt.after(4) == 4

    def test_after_invalid(self):
        lt = Lt(5)
        with pytest.raises(ValueError, match="value should be < 5"):
            lt.after(5)
        with pytest.raises(ValueError, match="value should be < 5"):
            lt.after(6)


class TestMinLen:
    def test_instantiation(self):
        ml = MinLen(3)
        assert ml.value == 3

    def test_json_schema(self):
        ml = MinLen(5)
        assert ml.json_schema() == {"minLength": 5}

    def test_after_valid(self):
        ml = MinLen(3)
        assert ml.after("abc") == "abc"
        assert ml.after("abcd") == "abcd"

    def test_after_invalid(self):
        ml = MinLen(3)
        with pytest.raises(ValueError, match="value length should be >= 3"):
            ml.after("ab")


class TestMaxLen:
    def test_instantiation(self):
        ml = MaxLen(3)
        assert ml.value == 3

    def test_json_schema(self):
        ml = MaxLen(5)
        assert ml.json_schema() == {"maxLength": 5}

    def test_after_valid(self):
        ml = MaxLen(3)
        assert ml.after("abc") == "abc"
        assert ml.after("ab") == "ab"

    def test_after_invalid(self):
        ml = MaxLen(3)
        with pytest.raises(ValueError, match="value length should be <= 3"):
            ml.after("abcd")


class TestLen:
    def test_instantiation(self):
        ln = Len(2, 5)
        assert ln.min_value == 2
        assert ln.max_value == 5

    def test_json_schema(self):
        ln = Len(1, 10)
        assert ln.json_schema() == {"minLength": 1, "maxLength": 10}

    def test_after_valid(self):
        ln = Len(2, 5)
        assert ln.after("abc") == "abc"
        assert ln.after("ab") == "ab"
        assert ln.after("abcde") == "abcde"

    def test_after_invalid_min(self):
        ln = Len(2, 5)
        with pytest.raises(ValueError, match="value length should be >= 2"):
            ln.after("a")

    def test_after_invalid_max(self):
        ln = Len(2, 5)
        with pytest.raises(ValueError, match="value length should be  5"):
            ln.after("abcdef")


class TestMinItems:
    def test_instantiation(self):
        mi = MinItems(2)
        assert mi.value == 2

    def test_json_schema(self):
        mi = MinItems(3)
        assert mi.json_schema() == {"minItems": 3}

    def test_after_valid(self):
        mi = MinItems(2)
        assert mi.after([1, 2]) == [1, 2]
        assert mi.after([1, 2, 3]) == [1, 2, 3]

    def test_after_invalid(self):
        mi = MinItems(2)
        with pytest.raises(ValueError, match="items count should be >= 2"):
            mi.after([1])


class TestMaxItems:
    def test_instantiation(self):
        mi = MaxItems(2)
        assert mi.value == 2

    def test_json_schema(self):
        mi = MaxItems(3)
        assert mi.json_schema() == {"maxItems": 3}

    def test_after_valid(self):
        mi = MaxItems(2)
        assert mi.after([1, 2]) == [1, 2]
        assert mi.after([1]) == [1]

    def test_after_invalid(self):
        mi = MaxItems(2)
        with pytest.raises(ValueError, match="items count should be <= 2"):
            mi.after([1, 2, 3])


class TestMatch:
    def test_instantiation(self):
        pattern = re.compile(r"\d+")
        m = Match(pattern)
        assert m.pattern == pattern

    def test_json_schema(self):
        pattern = re.compile(r"\w+")
        m = Match(pattern)
        assert m.json_schema() == {"pattern": r"\w+"}

    def test_after_valid(self):
        pattern = re.compile(r"\d+")
        m = Match(pattern)
        assert m.after("123") == "123"

    def test_after_invalid(self):
        pattern = re.compile(r"\d+")
        m = Match(pattern)
        with pytest.raises(ValueError, match="value doesn't match pattern"):
            m.after("abc")


class TestUrlConstraints:
    def test_instantiation(self):
        uc = UrlConstraints()
        assert uc.schemes is None
        assert uc.ports is None

        uc2 = UrlConstraints(schemes=["http", "https"], ports=[80, 443])
        assert uc2.schemes == ["http", "https"]
        assert uc2.ports == [80, 443]

    def test_after_valid_schemes(self):
        uc = UrlConstraints(schemes=["http", "https"])
        url = Url("http://example.com")
        assert uc.after(url) == url

    def test_after_invalid_schemes(self):
        uc = UrlConstraints(schemes=["http", "https"])
        url = Url("ftp://example.com")
        with pytest.raises(ValueError, match="URL scheme should be one of"):
            uc.after(url)

    def test_after_valid_ports(self):
        uc = UrlConstraints(ports=[80, 443])
        url = Url("http://example.com:80")
        assert uc.after(url) == url

    def test_after_invalid_ports(self):
        uc = UrlConstraints(ports=[80, 443])
        url = Url("http://example.com:8080")
        with pytest.raises(ValueError, match="port number should be one of"):
            uc.after(url)

    def test_after_no_port(self):
        uc = UrlConstraints(ports=[80, 443])
        url = Url("http://example.com")
        assert uc.after(url) == url  # No port, so valid

    def test_hash(self):
        uc1 = UrlConstraints(schemes=["http"], ports=[80])
        uc2 = UrlConstraints(schemes=["http"], ports=[80])
        uc3 = UrlConstraints(schemes=["https"], ports=[80])
        assert hash(uc1) == hash(uc2)
        assert hash(uc1) != hash(uc3)


class TestJsonLoads:
    def test_instantiation(self):
        jl = JsonLoads()
        assert jl is not None

    def test_before_valid_json(self):
        jl = JsonLoads()
        result = jl.before('{"key": "value"}')
        assert result == {"key": "value"}

    def test_before_invalid_json(self):
        jl = JsonLoads()
        result = jl.before("not json")
        assert result == "not json"


class TestToLower:
    def test_instantiation(self):
        tl = ToLower()
        assert tl.mode == "after"

        tl2 = ToLower(mode="before")
        assert tl2.mode == "before"

    def test_before_mode_before(self):
        tl = ToLower(mode="before")
        assert tl.before("ABC") == "abc"
        assert tl.after("ABC") == "ABC"

    def test_after_mode_after(self):
        tl = ToLower(mode="after")
        assert tl.before("ABC") == "ABC"
        assert tl.after("ABC") == "abc"


class TestToUpper:
    def test_instantiation(self):
        tu = ToUpper()
        assert tu.mode == "after"

        tu2 = ToUpper(mode="before")
        assert tu2.mode == "before"

    def test_before_mode_before(self):
        tu = ToUpper(mode="before")
        assert tu.before("abc") == "ABC"
        assert tu.after("abc") == "abc"

    def test_after_mode_after(self):
        tu = ToUpper(mode="after")
        assert tu.before("abc") == "abc"
        assert tu.after("abc") == "ABC"


class TestStrict:
    def test_instantiation_int(self):
        s = Strict(int)
        assert s.type == [int]

    def test_instantiation_str(self):
        s = Strict(str)
        assert s.type == [str]

    def test_instantiation_unsupported(self):
        with pytest.raises(ValidationError):
            Strict(list[int])

    def test_hash(self):
        s1 = Strict(int)
        s2 = Strict(int)
        s3 = Strict(str)
        assert hash(s1) == hash(s2)
        assert hash(s1) != hash(s3)

    def test_before_valid(self):
        s = Strict(int)
        assert s.before(5) == 5

    def test_before_invalid(self):
        s = Strict(int)
        with pytest.raises(ValueError, match=r"invalid value for .*int.*"):
            s.before("5")


@pytest.mark.skipif(not hasattr(__import__("cwtch.metadata"), "EmailValidator"), reason="emval not available")
class TestEmailValidator:
    def test_instantiation(self):
        ev = EmailValidator()
        assert ev.validator is not None

    def test_json_schema(self):
        ev = EmailValidator()
        assert ev.json_schema() == {"format": "email"}

    def test_after_valid(self):
        ev = EmailValidator()
        result = ev.after("test@example.com")
        assert result == "test@example.com"  # Assuming it returns the value

    def test_after_invalid(self):
        ev = EmailValidator()
        with pytest.raises(Exception):  # emval raises specific exception
            ev.after("invalid-email")
