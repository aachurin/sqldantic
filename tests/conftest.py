import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB

from sqldantic import DeclarativeBase


@pytest.fixture(scope="function")
def Base():
    class Base(DeclarativeBase):
        pass

    return Base


# psycopg2 can't use ipaddress by default, so psycopg (aka psycopg3) is preferred
@pytest.fixture(scope="function", params=["sqlite://", "postgresql+psycopg:///tests"])
def engine_and_base(request):
    engine = create_engine(request.param, echo=True)

    class Base(DeclarativeBase):
        json_type = JSONB if request.param.startswith("postgresql") else JSON

    yield engine, Base

    Base.metadata.drop_all(engine)
