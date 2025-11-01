from typing import Annotated, ClassVar, Generic, TypeVar

import pytest

from cwtch import Field, dataclass, field, is_cwtch_model, is_cwtch_view, view
from cwtch.core import _MISSING, UNSET
from cwtch.cwtch import _is_classvar


T = TypeVar("T")


class TestIsClassvar:
    def test_classvar_basic(self):
        assert _is_classvar(ClassVar[int]) is True
        assert _is_classvar(ClassVar[str]) is True
        assert _is_classvar(ClassVar) is True

    def test_not_classvar(self):
        assert _is_classvar(int) is False
        assert _is_classvar(str) is False
        assert _is_classvar(list) is False

    def test_classvar_with_annotated(self):
        assert _is_classvar(ClassVar[Annotated[int, "meta"]]) is True
        assert _is_classvar(ClassVar[Annotated[str, "desc", "more"]]) is True

    def test_annotated_with_classvar(self):
        assert _is_classvar(Annotated[ClassVar[int], "meta"]) is False
        assert _is_classvar(Annotated[ClassVar[str], "desc"]) is False


class TestIsCwtch:
    def test_is_cwtch_model(self):

        class RegularClass:
            pass

        assert not is_cwtch_model(RegularClass)

        @dataclass
        class Model:
            i: int

        assert is_cwtch_model(Model)

        @view(Model)
        class View:
            pass

        assert not is_cwtch_model(View)

        # Test inheritance
        @dataclass
        class Derived(Model):
            s: str

        assert is_cwtch_model(Derived)

        # Test generic
        @dataclass
        class GenericModel(Generic[T]):
            x: T

        assert is_cwtch_model(GenericModel)
        assert is_cwtch_model(GenericModel[int])

    def test_is_cwtch_view(self):

        @dataclass
        class Model:
            i: int

        assert not is_cwtch_view(Model)

        @view(Model)
        class View:
            pass

        assert is_cwtch_view(View)

        # Test view from view
        @view(View)
        class View2:
            pass

        assert is_cwtch_view(View2)


class TestField:
    def test_field_init(self):
        # Test default init
        f = Field()
        assert f.default is _MISSING
        assert f.default_factory is _MISSING
        assert f.init is True
        assert f.init_alias is UNSET
        assert f.asdict_alias is UNSET
        assert f.repr is UNSET
        assert f.compare is UNSET
        assert f.property is UNSET
        assert f.validate is UNSET
        assert f.metadata == {}
        assert f.kw_only is UNSET
        assert f.name is None
        assert f.type is None
        assert f._field_type is None

        # Test with parameters
        f = Field(
            default=42,
            init=False,
            repr=False,
            compare=True,
            metadata={"key": "value"},
            kw_only=True,
        )
        assert f.default == 42
        assert f.init is False
        assert f.repr is False
        assert f.compare is True
        assert f.metadata == {"key": "value"}
        assert f.kw_only is True

        # Test default_factory
        def factory():
            return 42

        f = Field(default_factory=factory)
        assert f.default_factory is factory

    def test_field_init_error(self):
        with pytest.raises(ValueError, match="cannot specify both default and default_factory"):
            Field(default=1, default_factory=lambda: 2)

    def test_field_eq(self):
        f1 = Field(default=1, init=False)
        f2 = Field(default=1, init=False)
        f3 = Field(default=2, init=False)

        assert f1 == f2
        assert f1 != f3
        assert f1 != "not a field"

        # Set name and type to test full eq
        f1.name = "test"
        f1.type = int
        f2.name = "test"
        f2.type = int
        f3.name = "other"
        f3.type = int

        assert f1 == f2
        assert f1 != f3

    def test_field_rich_repr(self):
        f = Field(default=1, init=False, metadata={"key": "value"})
        repr_items = list(f.__rich_repr__())
        expected = [
            ("name", None),
            ("type", None),
            ("default", 1),
            ("default_factory", _MISSING),
            ("init", False),
            ("init_alias", UNSET),
            ("asdict_alias", UNSET),
            ("repr", UNSET),
            ("compare", UNSET),
            ("property", UNSET),
            ("validate", UNSET),
            ("metadata", {"key": "value"}),
            ("kw_only", UNSET),
        ]
        assert repr_items == expected

    def test_field_with_dataclass(self):

        @dataclass
        class M:
            x: int = field(default=1, metadata={"desc": "test"})

        f = M.__dataclass_fields__["x"]
        assert f.name == "x"
        assert f.type == int
        assert f.default == 1
        assert f.metadata == {"desc": "test"}
