# sqldantic
SQLalchemy + pyDANTIC

### Example:
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

### Descripion
Any subclass of `DeclarativeBase` is Pydantic Model.

Any subclass of `DeclarativeBase` with `table=True` is Sqlalchemy Model.

Both `Mapped[...]` and "unmapped" formats are supported, but Sqlalchemy needs `Mapped` for mypy type checking, 
so `Mapped` is preferred. 

Sometimes it's impossible to use generic Sqlalchemy types:

```python
class Foo(Base, table=True):
    ...
    address: Mapped[ipaddress.IPv4Address]
    info: Mapped[Info]
    ...
```

Both `address` and `info` are not supported by Sqlalchemy. 

In such case, you can use special `Typed` type, which can handle any pydantic-supported types:

```python
class Foo(Base, table=True):
    ...
    address: Mapped[ipaddress.IPv4Address] = Field(Typed(String))
    # means validate value as an IPv4Address object, but store it as a String
    info: Mapped[Info] = Field(Typed(JSONB))
    # means validate value as an Info object, but store it as a JSONB
    ...
```
