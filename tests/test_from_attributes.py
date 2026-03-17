import cwtch


class ParentObj:
    pass


class ChildObj:
    pass


class TestFromAttributes:
    def test_from_attributes(self):
        @cwtch.dataclass
        class Parent:
            children: list["Child"]

        @cwtch.dataclass
        class Child:
            parent: "Parent"

        Parent.cwtch_update_forward_refs()
        Child.cwtch_update_forward_refs()

        parent_obj = ParentObj()
        child_obj = ChildObj()

        setattr(parent_obj, "children", [child_obj])
        setattr(child_obj, "parent", parent_obj)

        parent = cwtch.from_attributes(Parent, parent_obj)

        assert parent.children
        assert len(parent.children) == 1
        assert isinstance(parent.children[0], Child)
        assert parent.children[0].parent == parent
        assert parent.children[0].parent.children == parent.children

    def test_from_attributes_reset_circular_refs(self):
        @cwtch.dataclass
        class Parent:
            children: list["Child"]

        @cwtch.dataclass
        class Child:
            parent: "Parent"

        Parent.cwtch_update_forward_refs()
        Child.cwtch_update_forward_refs()

        parent_obj = ParentObj()
        child_obj = ChildObj()

        setattr(parent_obj, "children", [child_obj])
        setattr(child_obj, "parent", parent_obj)

        parent = cwtch.from_attributes(Parent, parent_obj, reset_circular_refs=True)

        assert parent.children
        assert len(parent.children) == 1
        assert isinstance(parent.children[0], Child)
        assert parent.children[0].parent == cwtch.UNSET
