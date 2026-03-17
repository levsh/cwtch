from typing import Annotated, Generic, Literal, TypeVar

from typing_extensions import Doc

from cwtch import dataclass, make_json_schema, view
from cwtch.metadata import Ge, Gt, JsonLoads, Le, Lt, MaxLen, MinItems, MinLen
from cwtch.types import NonZeroLen, Unset


T = TypeVar("T")
F = TypeVar("F")


class TestJsonSchema:
    def test_int_schema(self):
        schema, definitions = make_json_schema(int)
        assert schema == {"type": "integer"}
        assert definitions == {}

    def test_str_schema(self):
        schema, definitions = make_json_schema(str)
        assert schema == {"type": "string"}
        assert definitions == {}

    def test_float_schema(self):
        schema, definitions = make_json_schema(float)
        assert schema == {"type": "number"}
        assert definitions == {}

    def test_bool_schema(self):
        schema, definitions = make_json_schema(bool)
        assert schema == {"type": "boolean"}
        assert definitions == {}

    def test_list_schema(self):
        schema, definitions = make_json_schema(list)
        assert schema == {"type": "array"}
        assert definitions == {}

    def test_list_int_schema(self):
        schema, definitions = make_json_schema(list[int])
        assert schema == {"type": "array", "items": {"type": "integer"}}
        assert definitions == {}

    def test_list_str_schema(self):
        schema, definitions = make_json_schema(list[str])
        assert schema == {"type": "array", "items": {"type": "string"}}
        assert definitions == {}

    def test_tuple_schema(self):
        schema, definitions = make_json_schema(tuple)
        assert schema == {"type": "array", "items": False}
        assert definitions == {}

    def test_tuple_int_str_schema(self):
        schema, definitions = make_json_schema(tuple[int, str])
        assert schema == {"type": "array", "prefixItems": [{"type": "integer"}, {"type": "string"}], "items": False}
        assert definitions == {}

    def test_set_schema(self):
        schema, definitions = make_json_schema(set)
        assert schema == {"type": "array", "uniqueItems": True}
        assert definitions == {}

    def test_set_int_schema(self):
        schema, definitions = make_json_schema(set[int])
        assert schema == {"type": "array", "items": {"type": "integer"}, "uniqueItems": True}
        assert definitions == {}

    def test_dict_schema(self):
        schema, definitions = make_json_schema(dict)
        assert schema == {"type": "object"}
        assert definitions == {}

    def test_dict_str_int_schema(self):
        schema, definitions = make_json_schema(dict[str, int])
        assert "type" in schema
        assert definitions == {}

    def test_literal_schema(self):
        schema, definitions = make_json_schema(Literal["A", 1])
        assert schema == {"enum": ["A", 1]}
        assert definitions == {}

    def test_ge_le_schema(self):
        schema, definitions = make_json_schema(Annotated[int, Ge(1), Le(10)])
        assert schema == {"type": "integer", "minimum": 1, "maximum": 10}
        assert definitions == {}

    def test_gt_lt_schema(self):
        schema, definitions = make_json_schema(Annotated[int, Gt(1), Lt(10)])
        assert schema == {
            "type": "integer",
            "exclusiveMinimum": True,
            "minimum": 1,
            "exclusiveMaximum": True,
            "maximum": 10,
        }
        assert definitions == {}

    def test_len_schema(self):
        schema, definitions = make_json_schema(Annotated[str, MinLen(1), MaxLen(10)])
        assert schema == {"type": "string", "minLength": 1, "maxLength": 10}
        assert definitions == {}

    def test_union_schema(self):
        schema, definitions = make_json_schema(int | str)
        assert schema == {"anyOf": [{"type": "integer"}, {"type": "string"}]}
        assert definitions == {}

    def test_unset_schema(self):
        schema, definitions = make_json_schema(Unset[str])
        assert schema == {"type": "string"}
        assert definitions == {}

    def test_doc_schema(self):
        schema, definitions = make_json_schema(Annotated[str, Doc("This is doc")])
        assert schema == {"type": "string", "description": "This is doc"}
        assert definitions == {}

        schema, definitions = make_json_schema(Annotated[list[Annotated[str, Doc("This is doc")]], MinItems(1)])
        assert schema == {"type": "array", "items": {"type": "string", "description": "This is doc"}, "minItems": 1}
        assert definitions == {}

        schema, definitions = make_json_schema(Annotated[list[str], Doc("This is doc")])
        assert schema == {"type": "array", "items": {"type": "string"}}
        assert definitions == {}

    def test_model_schema(self):
        @dataclass
        class Model:
            i: Annotated[int, Ge(1), Lt(10)]
            s: str
            l: list
            f: list[float]

        assert make_json_schema(list[Model]) == (
            {"type": "array", "items": {"$ref": "#/$defs/Model"}},
            {
                "Model": {
                    "type": "object",
                    "properties": {
                        "i": {"type": "integer", "minimum": 1, "exclusiveMaximum": True, "maximum": 10},
                        "s": {"type": "string"},
                        "l": {"type": "array"},
                        "f": {"type": "array", "items": {"type": "number"}},
                    },
                    "required": ["i", "s", "l", "f"],
                }
            },
        )

        @view(Model, "V1", include=["i", "s"])
        class ModelV1:
            s: NonZeroLen[str]

        assert make_json_schema(ModelV1) == (
            {"$ref": "#/$defs/ModelV1"},
            {
                "ModelV1": {
                    "type": "object",
                    "properties": {
                        "i": {"type": "integer", "minimum": 1, "maximum": 10, "exclusiveMaximum": True},
                        "s": {"type": "string", "minLength": 1},
                    },
                    "required": ["i", "s"],
                }
            },
        )

    def test_generic_schema(self):
        @dataclass
        class GenericModel(Generic[T, F]):
            a: T
            b: list[F]

        assert make_json_schema(GenericModel[int, str]) == (
            {"$ref": "#/$defs/GenericModel[int, str]"},
            {
                "GenericModel[int, str]": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "array", "items": {"type": "string"}}},
                    "required": ["a", "b"],
                }
            },
        )

    def test_json_value_metadata(self):
        JsonList = Annotated[list, JsonLoads()]
        JsonDict = Annotated[dict, JsonLoads()]

        @dataclass
        class M:
            args: JsonList | None = None
            kwds: JsonDict | None = None

        m = M(args="[]", kwds="{}")
        assert m.args == []
        assert m.kwds == {}
