from ipaddress import IPv4Address, IPv4Network
from typing import Annotated

from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session

from sqldantic import Field

X = Annotated[int, 123]


def test_ipv4address(Base, engine) -> None:
    class Host(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        addr: IPv4Address

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        host1 = Host(addr="192.168.1.1")
        host2 = Host(addr=IPv4Address("192.168.1.2"))
        session.add(host1)
        session.add(host2)
        session.commit()
        session.refresh(host1)
        session.refresh(host2)
        assert host1.addr == IPv4Address("192.168.1.1")
        assert host2.addr == IPv4Address("192.168.1.2")

    with Session(engine) as session:
        hosts = session.execute(select(Host)).scalars().all()
        print(hosts)
