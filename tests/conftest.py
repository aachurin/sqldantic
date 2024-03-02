import pytest
from sqlalchemy import create_engine

from sqldantic import DeclarativeBase


@pytest.fixture(scope="function")
def Base():
    class Base(DeclarativeBase):
        pass

    return Base


# psycopg2 can't use ipaddress by default, so psycopg (aka psycopg3) is preferred
@pytest.fixture(scope="function", params=["sqlite://", "postgresql+psycopg:///tests"])
def engine(request, Base):
    engine = create_engine(request.param, echo=True)
    yield engine
    Base.metadata.drop_all(engine)
