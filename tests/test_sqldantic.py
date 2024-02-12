from typing import Annotated

from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped

from sqldantic import Field, Relationship
from sqldantic.field import _MappedColumnMarker, _RelationshipMarker


def test_pydantic_meta_tricks() -> None:
    X = Annotated[int, 1, Relationship(back_populates="foo"), Field(primary_key=True), Field(index=True)]

    class Model(BaseModel):
        a: X = Field(comment="foo")  # type:ignore

    field = Model.model_fields["a"]
    assert _MappedColumnMarker in field.metadata
    assert _RelationshipMarker in field.metadata
    assert 1 in field.metadata
    assert field._attributes_set == {
        "back_populates": "foo",
        "primary_key": True,
        "index": True,
        "comment": "foo",
        "annotation": int,
        "_marker": _MappedColumnMarker,
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
