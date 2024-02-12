import enum
import ipaddress

from pydantic import BaseModel
from sqlalchemy import JSON, ForeignKey, String, select
from sqlalchemy.orm import Mapped, Session

from sqldantic import Field, Relationship, Typed


def test_mixed_mapping(Base, engine) -> None:
    class Hero(Base, table=True):
        id: Mapped[int] = Field(default=None, primary_key=True)
        name: str
        secret_name: str
        age: int | None = None

    hero_1 = Hero(name="Deadpond", secret_name="Dive Wilson")
    hero_2 = Hero(name="Deadpond", secret_name="Dive Wilson")

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(hero_1)
        session.commit()
        session.refresh(hero_1)

    with Session(engine) as session:
        session.add(hero_2)
        session.commit()
        session.refresh(hero_2)

    with Session(engine) as session:
        heroes = session.execute(select(Hero)).scalars().all()
        assert len(heroes) == 2
        assert heroes[0].name == heroes[1].name


def test_relationship(Base, engine) -> None:

    class Parent(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str]
        children: Mapped[list["Child"]] = Relationship(back_populates="parent")

    class Child(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        name: Mapped[str]
        parent_id: Mapped[int] = Field(ForeignKey("parent.id"))
        parent: Mapped[Parent] = Relationship(back_populates="children")

    # need in function only
    Base.update_incomplete_models()

    parent1 = Parent(name="Parent1")
    child1 = Child(name="Child1", parent=parent1)
    child2 = Child(name="Child2", parent=parent1)

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


def test_typed(Base, engine) -> None:
    class Kind(str, enum.Enum):
        postgres = "postgres"
        oracle = "oracle"
        mysql = "mysql"

    class Info(BaseModel):
        name: str
        kind: Kind
        tags: set[str]

    class Database(Base, table=True):
        id: Mapped[int] = Field(primary_key=True)
        info: Mapped[Info] = Field(Typed())
        address: Mapped[ipaddress.IPv4Address] = Field(Typed(String()))

    info = Info(
        name="mydb",
        kind=Kind.postgres,
        tags={"pg15", "pg16"},
    )

    db1 = Database(
        info=info,
        address="192.168.1.2",
    )

    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(db1)
        session.commit()
        session.refresh(db1)

    assert db1.info is not info
    assert db1.info == info
    assert db1.address == ipaddress.IPv4Address("192.168.1.2")


def test_example(Base, engine) -> None:
    class OS(str, enum.Enum):
        linux = "linux"
        windows = "windows"
        macos = "macos"

    class Info(BaseModel):
        os: OS
        tags: set[str]

    class ClusterBase(Base):
        name: Mapped[str]
        hosts: Mapped[list["Host"]] = Relationship(back_populates="cluster")

    class Cluster(ClusterBase, table=True):
        id: Mapped[int] = Field(primary_key=True)

    class HostBase(Base):
        hostname: Mapped[str] = Field(index=True)
        address: Mapped[ipaddress.IPv4Address] = Field(Typed(String))
        info: Mapped[Info] = Field(Typed(JSON))
        cluster: Mapped[Cluster] = Relationship(back_populates="hosts")

    class Host(HostBase, table=True):
        id: Mapped[int] = Field(primary_key=True)
        cluster_id: Mapped[int] = Field(ForeignKey("cluster.id"))

    # need in function only
    Base.update_incomplete_models()

    Base.metadata.create_all(engine)

    cluster = Cluster(name="demo")
    info1 = Info(os=OS.linux, tags={"ubuntu", "ubuntu23"})
    host1 = Host(hostname="server1", cluster=cluster, address=ipaddress.IPv4Address("192.168.1.2"), info=info1)
    info2 = Info(os=OS.macos, tags={"macosx", "macosx14"})
    host2 = Host(hostname="server2", cluster=cluster, address=ipaddress.IPv4Address("192.168.1.3"), info=info2)

    with Session(engine) as session:
        session.add(host1)
        session.add(host2)
        session.commit()
        hosts = session.execute(select(Host)).scalars().all()
        assert len(hosts) == 2
        assert hosts[0].cluster.name == "demo"
        assert hosts[1].cluster.name == "demo"
        assert hosts[0].address == ipaddress.IPv4Address("192.168.1.2")
        assert hosts[1].address == ipaddress.IPv4Address("192.168.1.3")
        assert hosts[0].info == info1
        assert hosts[1].info == info2
