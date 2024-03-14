import decimal
import pathlib
import sys
import typing
from typing import Annotated, NewType

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import Integer, Numeric, String, inspect
from sqlalchemy.orm import Mapped

from sqldantic import DeclarativeBase, Field, Relationship, Typed
from sqldantic.field import _FieldMarker, _RelationshipMarker
from sqldantic.orm import Registry
from sqldantic.sqltypes import _SpecialTyped


def test_pydantic_meta_tricks() -> None:
    X = Annotated[
        int, 1, Relationship(back_populates="foo"), Field(primary_key=True), Field(index=True)
    ]

    class Model(BaseModel):
        a: X = Field(comment="foo")  # type:ignore

    field = Model.model_fields["a"]
    assert _FieldMarker in field.metadata
    assert _RelationshipMarker in field.metadata
    assert 1 in field.metadata
    assert field._attributes_set == {
        "back_populates": "foo",
        "primary_key": True,
        "index": True,
        "comment": "foo",
        "annotation": int,
        "_marker": _FieldMarker,
    }


def test_pydantic_namespace(Base) -> None:
    LOCAL_VAR = "LOCAL_VAR"  # noqa

    class Model1(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        model2: "Mapped[Model2]" = Field(String())

    class Model2(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        model1: "Mapped[Model1]" = Field(String())

    assert "LOCAL_VAR" in Model1.__pydantic_parent_namespace__  # type:ignore
    assert Model1 in Base.__sqldantic_incomplete_models__  # type:ignore

    Base.update_incomplete_models()

    assert len(Base.__sqldantic_incomplete_models__) == 0  # type:ignore


def test_module_level_models() -> None:
    from .models import Base

    assert len(Base.__sqldantic_incomplete_models__) == 0  # type:ignore


def test_generic_types(Base):
    # class NewInt(int):
    #     pass

    print()

    class Table(Base, table=True):
        id: int = Field(primary_key=True)
        int_: int
        # newint_: NewInt

    columns = inspect(Table).columns
    for k, v in columns.items():
        print(k, v.type)

    # assert type(columns["x"].type) == Numeric
    # assert (
    #         type(columns["y"].type) == Numeric
    #         and columns["y"].type.precision == 4
    #         and columns["y"].type.scale == 2
    # )
    # assert (
    #         type(columns["z"].type) == Numeric
    #         and columns["y"].type.precision == 4
    #         and columns["y"].type.scale == 2
    # )


def test_validate_assignment() -> None:
    class Base(DeclarativeBase):
        model_config = {"validate_assignment": True}

    class Foo(BaseModel):
        a: int
        b: int

    class Model(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        foo: Foo

    x = Model()
    x.foo = {"a": 1, "b": 2}
    assert isinstance(x.foo, Foo)
    with pytest.raises(
        ValidationError, match=r".*Input should be a valid dictionary or instance of Foo.*"
    ):
        x.foo = 42


def test_allow_extra() -> None:
    class Base(DeclarativeBase):
        model_config = {"extra": "allow"}

    class Model(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)

    x = Model(extra=42)
    assert "extra" in x.__pydantic_extra__
    x.foo = 1
    assert "foo" in x.__pydantic_extra__
    del x.extra
    del x.foo
    assert x.__pydantic_extra__ == {}

    class Model2(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        _private: int = 2

    assert Model2()._private == 2


def test_not_table(Base) -> None:
    class Hero(Base):
        id: Mapped[int] = Field(primary_key=True)

    Hero(id=1)


def test_private_attributes(Base) -> None:
    class Hero(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        _private: int

    with pytest.raises(ValueError, match=r".* has no field .*"):
        Hero(name="Skywalker")

    h = Hero(_private=123)
    with pytest.raises(AttributeError):
        h._private

    h._private = 222
    assert h.model_dump() == {}


def test_set_del_attr(Base) -> None:
    class Hero(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str]

    h = Hero(name="Skywalker")

    h.name = "Darth Vader"
    del h.name


def test_set_del_attr_non_table(Base) -> None:
    class Hero(Base):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str]

    h = Hero(id=42, name="Skywalker")
    h.name = "Darth Vader"
    del h.name


def test_aliases(Base) -> None:
    class Hero(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str] = Field(alias="title")

    Hero(id=1, title="asd")


def test_field_aliases() -> None:
    with pytest.raises(TypeError, match=r".* should be `str`.*"):
        Field(alias=1)
    with pytest.raises(TypeError, match=r".* should be `str`.*"):
        Field(validation_alias=1)
    with pytest.raises(TypeError, match=r".* should be `str`.*"):
        Field(serialization_alias=1)
    with pytest.raises(TypeError, match=r".* should be `str`.*"):
        Relationship(alias=1)
    with pytest.raises(TypeError, match=r".* should be `str`.*"):
        Relationship(validation_alias=1)
    with pytest.raises(TypeError, match=r".* should be `str`.*"):
        Relationship(serialization_alias=1)


def test_registry_resolver() -> None:
    registry = Registry()
    assert registry._resolve_type(object) is None
    assert type(registry._resolve_type(int)) == Integer
    assert type(registry._resolve_type(Annotated[int, 1])) == Integer
    assert type(registry._resolve_type(NewType("int", int))) == Integer
    assert type(registry._resolve_type(list[str])) == _SpecialTyped
    assert type(registry._resolve_type(Annotated[str, 1] | Annotated[str, 2])) == String
    assert type(registry._resolve_type(str | int)) == _SpecialTyped
    assert type(registry._resolve_type(str | dict[str, int])) == _SpecialTyped
    assert type(registry._resolve_type(typing.List)) == _SpecialTyped
    assert type(registry._resolve_type(typing.List[str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.Tuple)) == _SpecialTyped
    assert type(registry._resolve_type(typing.Tuple[str, ...])) == _SpecialTyped
    assert type(registry._resolve_type(typing.Deque)) == _SpecialTyped
    assert type(registry._resolve_type(typing.Deque[str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.Set)) == _SpecialTyped
    assert type(registry._resolve_type(typing.Set[str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.FrozenSet)) == _SpecialTyped
    assert type(registry._resolve_type(typing.FrozenSet[str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.Dict)) == _SpecialTyped
    assert type(registry._resolve_type(typing.Dict[str, str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.Any)) == _SpecialTyped
    assert type(registry._resolve_type(typing.MutableSet)) == _SpecialTyped
    assert type(registry._resolve_type(typing.MutableSet[str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.Mapping)) == _SpecialTyped
    assert type(registry._resolve_type(typing.Mapping[str, str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.MutableMapping)) == _SpecialTyped
    assert type(registry._resolve_type(typing.MutableMapping[str, str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.Sequence)) == _SpecialTyped
    assert type(registry._resolve_type(typing.Sequence[str])) == _SpecialTyped
    assert type(registry._resolve_type(typing.MutableSequence)) == _SpecialTyped
    assert type(registry._resolve_type(typing.MutableSequence[str])) == _SpecialTyped
    assert (
        type(r := registry._resolve_type(pathlib.Path | typing.Pattern)) == _SpecialTyped
        and type(r.impl) == String
    )

    class NT(typing.NamedTuple):
        x: int
        y: int

    assert type(registry._resolve_type(NT)) == _SpecialTyped

    class TD(typing.TypedDict):
        x: int
        y: int

    assert type(registry._resolve_type(TD)) == _SpecialTyped

    if sys.version_info >= (3, 12):
        globalns = {}
        exec(
            "type N = N\n"
            "type NN = N | NN\n"
            "type X = int | X\n"
            "type Y = int | Z\n"
            "type Z = int | Y\n"
            "type ZZ = Z\n",
            globalns,
        )
        N, NN, X, Y, Z, ZZ = (
            globalns["N"],
            globalns["NN"],
            globalns["X"],
            globalns["Y"],
            globalns["Z"],
            globalns["ZZ"],
        )
        assert registry._resolve_type(N) is None
        assert registry._resolve_type(NN) is None
        assert type(registry._resolve_type(X)) == Integer
        assert type(registry._resolve_type(Y)) == Integer
        assert type(registry._resolve_type(Z)) == Integer
        assert type(registry._resolve_type(ZZ)) == Integer


def test_decimal_type(Base):
    class Table(Base, table=True):
        id: int = Field(primary_key=True)
        x: decimal.Decimal
        y: decimal.Decimal = Field(max_digits=4, decimal_places=2)
        z: Annotated[decimal.Decimal, Field(max_digits=4, decimal_places=2)]

    columns = inspect(Table).columns
    assert type(columns["x"].type) == Numeric
    assert (
        type(columns["y"].type) == Numeric
        and columns["y"].type.precision == 4
        and columns["y"].type.scale == 2
    )
    assert (
        type(columns["z"].type) == Numeric
        and columns["y"].type.precision == 4
        and columns["y"].type.scale == 2
    )
