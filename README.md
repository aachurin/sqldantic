# sqldantic
SQLalchemy + pyDANTIC

### Example:
```python
from __future__ import annotations

import enum
import ipaddress 

from pydantic import BaseModel
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqldantic import DeclarativeBase, Field, Relationship


class Base(DeclarativeBase):
    """
    allowed options are:
        metadata
        type_annotation_map
        json_type
        model_config
    
    see https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html
    for more information on `metadata` and `type_annotation_map`
    see https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict
    for more information on `model_config`
    
    `json_type` is JSON by default, but you can change it to JSONB 
    """


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
    address: Mapped[ipaddress.IPv4Address]
    info: Mapped[Info]
    cluster: Mapped[Cluster] = Relationship(back_populates="hosts")
    
    
class Host(HostBase, table=True):
    id: Mapped[int] = Field(primary_key=True)
    cluster_id: Mapped[int] = Field(ForeignKey("cluster.id"))

```

### Description
Any subclass of `DeclarativeBase` is Pydantic Model.

Any subclass of `DeclarativeBase` with `table=True` is Sqlalchemy Model.

Both `Mapped[...]` and "unmapped" formats are supported, but Sqlalchemy needs `Mapped` for mypy type checking, 
so `Mapped` is preferred. 

