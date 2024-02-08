from __future__ import annotations

from typing import Annotated

import pytest
from sqlalchemy.orm import Mapped, mapped_column

from sqldantic import DeclarativeBase, Field, Relationship


def test_mixed_annotation() -> None:
    class Base(DeclarativeBase):
        pass

    T = Annotated[str, Field(nullable=True)]

    with pytest.raises(TypeError, match=r".*Don't mix `sqldantic.Field` and `sqldantic.Relationship`.*"):

        class Hero(Base, table=True):
            name: Mapped[T] = Relationship()


def test_unsupported_annotation() -> None:
    class Base(DeclarativeBase):
        pass

    T = Annotated[str, mapped_column()]

    with pytest.raises(TypeError, match=r".*Use `sqldantic.Field` instead of `sqlalchemy.orm.mapped_column`.*"):

        class Hero(Base, table=True):
            name: Mapped[T]


def test_unsupported_default() -> None:
    class Base(DeclarativeBase):
        pass

    with pytest.raises(TypeError, match=r".*Use `sqldantic.Field` instead of `sqlalchemy.orm.mapped_column`.*"):

        class Hero(Base, table=True):
            name: Mapped[int] = mapped_column()
