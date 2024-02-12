import pytest
from sqlalchemy import create_engine

from sqldantic import DeclarativeBase


@pytest.fixture(scope="function")
def Base():
    class Base(DeclarativeBase):
        pass

    return Base


@pytest.fixture(scope="function", params=["sqlite://"])
def engine(request, Base):
    engine = create_engine(request.param)
    yield engine
    Base.metadata.drop_all(engine)
