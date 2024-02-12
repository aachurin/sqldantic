from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped

from sqldantic import DeclarativeBase, Field


class Base(DeclarativeBase):
    pass


class Model1(Base, table=True):
    id: Mapped[int] = Field(primary_key=True)
    model2: Mapped[Model2] = Field(String())


class Model2(Base, table=True):
    id: Mapped[int] = Field(primary_key=True)
    model1: Mapped[Model1] = Field(String())
