from ipaddress import IPv4Address, IPv4Network

from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session

from sqldantic import Field


def test_ipv4address(engine_and_base) -> None:
    engine, Base = engine_and_base

    class Host(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        addr: Mapped[IPv4Address]
        net: Mapped[IPv4Network]

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        host1 = Host(addr="192.168.1.1", net="192.168.1.0/24")
        host2 = Host(addr=IPv4Address("192.168.2.2"), net=IPv4Network("192.168.2.0/24"))
        session.add(host1)
        session.add(host2)
        session.commit()
        session.refresh(host1)
        session.refresh(host2)
        assert host1.addr == IPv4Address("192.168.1.1")
        assert host1.net == IPv4Network("192.168.1.0/24")
        assert host2.addr == IPv4Address("192.168.2.2")
        assert host2.net == IPv4Network("192.168.2.0/24")

    with Session(engine) as session:
        hosts = session.execute(select(Host)).scalars().all()
        assert len(hosts) == 2

    if engine.url.drivername.startswith("postgresql"):
        with Session(engine) as session:
            hosts = (
                session.execute(
                    select(Host).where(Host.addr.is_contained_within(IPv4Network("192.168.1.0/24")))
                )
                .scalars()
                .all()
            )
            assert len(hosts) == 1
            hosts = (
                session.execute(
                    select(Host).where(
                        Host.addr.is_contained_within_or_equal(IPv4Address("192.168.2.2"))
                    )
                )
                .scalars()
                .all()
            )
            assert len(hosts) == 1
            hosts = (
                session.execute(select(Host).where(Host.net.is_contains(IPv4Address("192.168.1.1"))))
                .scalars()
                .all()
            )
            assert len(hosts) == 1
            hosts = (
                session.execute(
                    select(Host).where(Host.net.is_contains_or_equal(IPv4Network("192.168.2.0/24")))
                )
                .scalars()
                .all()
            )
            assert len(hosts) == 1
            hosts = (
                session.execute(select(Host).where(Host.addr << IPv4Network("192.168.1.0/24")))
                .scalars()
                .all()
            )
            assert len(hosts) == 1
            hosts = (
                session.execute(select(Host).where(Host.net >> IPv4Address("192.168.1.1")))
                .scalars()
                .all()
            )
            assert len(hosts) == 1
