from __future__ import annotations

from typing import Annotated

import pytest
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sqldantic import Field, Relationship


def test_mixed_annotation(Base) -> None:
    T = Annotated[str, Field(nullable=True)]
    with pytest.raises(
        TypeError, match=r".*Don't mix `sqldantic.Field` and `sqldantic.Relationship`.*"
    ):

        class Hero(Base, table=True):
            name: Mapped[T] = Relationship()


def test_unsupported_annotation(Base) -> None:
    T1 = Annotated[str, mapped_column()]
    with pytest.raises(
        TypeError, match=r".*Use `sqldantic.Field` instead of `sqlalchemy.orm.mapped_column`.*"
    ):

        class Hero1(Base, table=True):
            name: Mapped[T1]

    with pytest.raises(
        TypeError, match=r".*Use `sqldantic.Relationship` instead of `sqlalchemy.orm.relationship`.*"
    ):

        class Some(Base, table=True):
            id: Mapped[int] = Field(primary_key=True)

        T2 = Annotated[Some, relationship(back_populates="hosts")]

        class Hero2(Base, table=True):
            cluster: Mapped[T2]


def test_unsupported_default(Base) -> None:
    with pytest.raises(
        TypeError, match=r".*Use `sqldantic.Field` instead of `sqlalchemy.orm.mapped_column`.*"
    ):

        class Hero(Base, table=True):
            name: Mapped[int] = mapped_column()

    with pytest.raises(
        TypeError, match=r".*Use `sqldantic.Relationship` instead of `sqlalchemy.orm.relationship`.*"
    ):

        class Hero(Base, table=True):
            name: Mapped[int] = relationship()
