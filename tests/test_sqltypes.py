from ipaddress import IPv4Address
from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session

from sqldantic import Field, Relationship


def test_ipv4address(Base, engine) -> None:
    class Host(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        addr: IPv4Address

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(child1)
        session.add(child2)
        session.commit()
        session.refresh(child1)
        session.refresh(child2)
        assert child1.parent and child1.parent.name == "Parent1"
        assert child2.parent and child2.parent.name == "Parent1"
        parents = session.execute(select(Parent)).scalars().all()
        assert parents and parents[0].name == "Parent1"
        assert ["Child1", "Child2"] == [x.name for x in parents[0].children]
