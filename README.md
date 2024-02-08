# sqldantic
SQLalchemy and pyDANTIC integration

Usage example:
```python
from __future__ import annotations

import enum
import ipaddress 

from pydantic import BaseModel
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.dialects.postgresql import JSONB
from sqldantic import DeclarativeBase, Field, Relationship, Typed


class Base(DeclarativeBase):
    # see https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html
    pass


class OS(str, enum.Enum):
    linux = "linux"
    windows = "windows"
    macos = "macos"
    

class Info(BaseModel):
    os: OS
    tags: set[str]
    

class ClusterBase(Base):
    name: Mapped[str]
    hosts: Mapped[list[Host]] = Relationship(back_populates="cluster")


class Cluster(ClusterBase, table=True):
    id: Mapped[int] = Field(primary_key=True)


class HostBase(Base):
    hostname: Mapped[str] = Field(index=True)
    address: Mapped[ipaddress.IPv4Address] = Field(Typed(String()))
    info: Mapped[Info] = Field(Typed(JSONB))
    cluster: Mapped[Cluster] = Relationship(back_populates="hosts")
    
    
class Host(HostBase, table=True):
    id: Mapped[int] = Field(primary_key=True)
    cluster_id: Mapped[int] = Field(ForeignKey("cluster.id"))

```