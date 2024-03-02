import pytest
from pydantic import ConfigDict, ValidationError
from sqlalchemy.orm import Mapped

from sqldantic import Field


def test_not_table(Base) -> None:
    class Hero(Base):
        id: Mapped[int] = Field(primary_key=True)

    Hero(id=1)


def test_extra_args(Base) -> None:
    class Hero(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        _private: int

    with pytest.raises(ValidationError, match=r".*Object has no attribute 'name'.*"):
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

    with pytest.raises(ValidationError, match=".*should be a valid string.*"):
        h.name = 42

    h.name = "Darth Vader"

    del h.name


def test_set_attr_no_validate_assignment(Base) -> None:
    class Hero(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str]
        model_config = ConfigDict(validate_assignment=False)

    h = Hero(name="Skywalker")
    h.name = 42
    assert h.name == 42


def test_set_del_attr_non_table(Base) -> None:
    class Hero(Base):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str]

    h = Hero(id=42, name="Skywalker")

    with pytest.raises(ValidationError, match=".*should be a valid string.*"):
        h.name = 42

    h.name = "Darth Vader"

    del h.name


def test_aliases(Base) -> None:
    class Hero(Base):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str] = Field(alias="title")

    # print(Hero.model_validate({"id": 0, "name": "Skywalker"}))
    print(Hero.model_validate({"id": 0, "title": "Skywalker"}))
    # h = Hero(id=42, name="Skywalker")
    # h.name = "asd"
    # print(h.model_dump())
