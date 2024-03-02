from __future__ import annotations

from typing import Annotated

import pytest
from annotated_types import Ge, Lt
from sqlalchemy import Integer, SmallInteger
from sqlalchemy.orm import Mapped

from sqldantic import DeclarativeBase, Field


def test_decl_base_config1() -> None:
    with pytest.raises(TypeError, match=r".*Could not use `table` with DeclarativeBase.*"):

        class Base(DeclarativeBase, table=True):
            pass


def test_decl_base_config2() -> None:
    with pytest.raises(TypeError, match=r".*`Base.something_else` is not allowed.*"):

        class Base(DeclarativeBase):
            something_else = 1


def test_decl_base_type_annotation_map(engine) -> None:
    A = Annotated[int, Ge(-32768), Lt(32768)]

    class Base(DeclarativeBase):
        type_annotation_map = {
            A: SmallInteger(),
        }

    class Foo(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        a: Mapped[A]  # <-- works well
        b: Mapped[A] = Field(lt=100)  # <-- will not work "as expected", result annotation is
        # Annotated[int, Lt(100), Ge(-32768), Lt(32768)]

    assert isinstance(Base.metadata.tables["foo"].columns["a"].type, SmallInteger)
    # not an error, but not "as expected"
    assert isinstance(Base.metadata.tables["foo"].columns["b"].type, Integer)


def test_decl_base_bad_type_annotation_map() -> None:
    A = Annotated[int, Field(lt=32768)]

    with pytest.raises(TypeError, match=r".* can lead to unwanted results and should be avoided.*"):

        class Base(DeclarativeBase):
            type_annotation_map = {
                A: SmallInteger(),
            }


def test_error_subclassing_table() -> None:
    class Base(DeclarativeBase):
        pass

    class Table(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)

    with pytest.raises(
        TypeError, match=r"Subclassing table `tests.test_declarative_base.Table` is not supported."
    ):

        class Table2(Table):
            pass
