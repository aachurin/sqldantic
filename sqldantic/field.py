# auto-generated module (pydantic = "^2.6.3", sqlalchemy = "^2.0.28")

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, ClassVar, cast

from pydantic.fields import FieldInfo, _Unset
from sqlalchemy.orm import MappedColumn as _MappedColumn
from sqlalchemy.orm import relationship
from sqlalchemy.orm.relationships import Relationship as _Relationship

from .orm import mapped_column
from .typing_extra import _Meta

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Collection, Literal

    from pydantic.fields import JsonDict
    from pydantic.types import Discriminator
    from sqlalchemy.orm._orm_constructors import (
        FetchedValue,
        ORMBackrefArgument,
        Query,
        _AutoIncrementType,
        _InfoType,
        _LazyLoadArgumentType,
        _ORMColCollectionArgument,
        _ORMOrderByArgument,
        _RelationshipArgumentType,
        _RelationshipJoinConditionArgument,
        _RelationshipSecondaryArgument,
        _ServerDefaultArgument,
        _TypeEngineArgument,
    )
    from sqlalchemy.orm.relationships import RelationshipProperty
    from sqlalchemy.sql.base import SchemaEventTarget
    from sqlalchemy.sql.schema import SchemaConst

__all__ = ("Field", "Relationship")


class _Marker(_Meta):
    __slots__ = ()
    attributes: ClassVar[frozenset[str]]
    constructor: ClassVar[Callable]

    @classmethod
    def construct(cls, field: FieldInfo) -> Any:
        kwargs = {k: v for k, v in field._attributes_set.items() if k in cls.attributes}
        extra_kwargs = kwargs.pop("_kwargs", None)
        return cls.constructor(**kwargs, **(extra_kwargs or {}))  # type:ignore

    def __repr__(self) -> str:
        return f"{self.constructor.__name__}"


class __FieldMarker(_Marker):
    __slots__ = ()
    attributes = frozenset(
        (
            "__type_pos",
            "nullable",
            "primary_key",
            "deferred",
            "deferred_group",
            "deferred_raiseload",
            "use_existing_column",
            "name",
            "autoincrement",
            "doc",
            "key",
            "index",
            "unique",
            "info",
            "onupdate",
            "insert_default",
            "server_default",
            "server_onupdate",
            "active_history",
            "quote",
            "system",
            "comment",
            "sort_order",
            "_kwargs",
        )
    )
    constructor = mapped_column


class __RelationshipMarker(_Marker):
    __slots__ = ()
    attributes = frozenset(
        (
            "argument",
            "secondary",
            "uselist",
            "collection_class",
            "primaryjoin",
            "secondaryjoin",
            "back_populates",
            "order_by",
            "backref",
            "overlaps",
            "post_update",
            "cascade",
            "viewonly",
            "lazy",
            "passive_deletes",
            "passive_updates",
            "active_history",
            "enable_typechecks",
            "foreign_keys",
            "remote_side",
            "join_depth",
            "comparator_factory",
            "single_parent",
            "innerjoin",
            "distinct_target_key",
            "load_on_pending",
            "query_class",
            "info",
            "omit_join",
            "sync_backref",
            "_kwargs",
        )
    )
    constructor = relationship


_FieldMarker = __FieldMarker()
_RelationshipMarker = __RelationshipMarker()


def Field(
    __type_pos: _TypeEngineArgument[Any] | SchemaEventTarget | None = _Unset,
    *,
    nullable: bool | Literal[SchemaConst.NULL_UNSPECIFIED] | None = _Unset,
    primary_key: bool | None = _Unset,
    deferred: bool | None = _Unset,
    deferred_group: str | None = _Unset,
    deferred_raiseload: bool | None = _Unset,
    use_existing_column: bool | None = _Unset,
    name: str | None = _Unset,
    autoincrement: _AutoIncrementType | None = _Unset,
    doc: str | None = _Unset,
    key: str | None = _Unset,
    index: bool | None = _Unset,
    unique: bool | None = _Unset,
    info: _InfoType | None = _Unset,
    onupdate: Any | None = _Unset,
    insert_default: Any | None = _Unset,
    server_default: _ServerDefaultArgument | None = _Unset,
    server_onupdate: FetchedValue | None = _Unset,
    active_history: bool | None = _Unset,
    quote: bool | None = _Unset,
    system: bool | None = _Unset,
    comment: str | None = _Unset,
    sort_order: int | None = _Unset,
    default: Any | None = _Unset,
    default_factory: Callable[[], Any] | None = _Unset,
    alias: str | None = _Unset,
    validation_alias: str | None = _Unset,
    serialization_alias: str | None = _Unset,
    title: str | None = _Unset,
    description: str | None = _Unset,
    examples: list[Any] | None = _Unset,
    exclude: bool | None = _Unset,
    discriminator: str | Discriminator | None = _Unset,
    json_schema_extra: JsonDict | Callable[[JsonDict], None] | None = _Unset,
    frozen: bool | None = _Unset,
    validate_default: bool | None = _Unset,
    init: bool | None = _Unset,
    init_var: bool | None = _Unset,
    pattern: str | None = _Unset,
    strict: bool | None = _Unset,
    gt: float | None = _Unset,
    ge: float | None = _Unset,
    lt: float | None = _Unset,
    le: float | None = _Unset,
    multiple_of: float | None = _Unset,
    allow_inf_nan: bool | None = _Unset,
    max_digits: int | None = _Unset,
    decimal_places: int | None = _Unset,
    min_length: int | None = _Unset,
    max_length: int | None = _Unset,
    union_mode: Literal["smart", "left_to_right"] | None = _Unset,
    extra: dict[str, Any] | None = _Unset,
    **_kwargs: Any,
) -> _MappedColumn:
    _kwargs = _kwargs or _Unset  # type:ignore
    _marker = _FieldMarker
    if alias not in (_Unset, None) and not isinstance(alias, str):
        raise TypeError("Invalid `alias` type. it should be `str`")
    if validation_alias not in (_Unset, None) and not isinstance(validation_alias, str):
        raise TypeError("Invalid `validation_alias` type. it should be `str`")
    if serialization_alias not in (_Unset, None) and not isinstance(serialization_alias, str):
        raise TypeError("Invalid `serialization_alias` type. it should be `str`")
    if serialization_alias in (_Unset, None):
        serialization_alias = alias
    if validation_alias in (_Unset, None):
        validation_alias = alias
    __rv = FieldInfo(**locals())
    __rv.metadata.append(_marker)
    return cast(_MappedColumn, __rv)


def Relationship(
    argument: _RelationshipArgumentType[Any] | None = _Unset,
    secondary: _RelationshipSecondaryArgument | None = _Unset,
    *,
    uselist: bool | None = _Unset,
    collection_class: type[Collection[Any]] | Callable[[], Collection[Any]] | None = _Unset,
    primaryjoin: _RelationshipJoinConditionArgument | None = _Unset,
    secondaryjoin: _RelationshipJoinConditionArgument | None = _Unset,
    back_populates: str | None = _Unset,
    order_by: _ORMOrderByArgument | None = _Unset,
    backref: ORMBackrefArgument | None = _Unset,
    overlaps: str | None = _Unset,
    post_update: bool | None = _Unset,
    cascade: str | None = _Unset,
    viewonly: bool | None = _Unset,
    lazy: _LazyLoadArgumentType | None = _Unset,
    passive_deletes: Literal["all"] | bool | None = _Unset,
    passive_updates: bool | None = _Unset,
    active_history: bool | None = _Unset,
    enable_typechecks: bool | None = _Unset,
    foreign_keys: _ORMColCollectionArgument | None = _Unset,
    remote_side: _ORMColCollectionArgument | None = _Unset,
    join_depth: int | None = _Unset,
    comparator_factory: type[RelationshipProperty.Comparator[Any]] | None = _Unset,
    single_parent: bool | None = _Unset,
    innerjoin: bool | None = _Unset,
    distinct_target_key: bool | None = _Unset,
    load_on_pending: bool | None = _Unset,
    query_class: type[Query[Any]] | None = _Unset,
    info: _InfoType | None = _Unset,
    omit_join: Literal[None, False] | None = _Unset,
    sync_backref: bool | None = _Unset,
    default: Any | None = _Unset,
    default_factory: Callable[[], Any] | None = _Unset,
    alias: str | None = _Unset,
    validation_alias: str | None = _Unset,
    serialization_alias: str | None = _Unset,
    title: str | None = _Unset,
    description: str | None = _Unset,
    examples: list[Any] | None = _Unset,
    exclude: bool | None = _Unset,
    discriminator: str | Discriminator | None = _Unset,
    json_schema_extra: JsonDict | Callable[[JsonDict], None] | None = _Unset,
    frozen: bool | None = _Unset,
    validate_default: bool | None = _Unset,
    init: bool | None = _Unset,
    init_var: bool | None = _Unset,
    pattern: str | None = _Unset,
    strict: bool | None = _Unset,
    gt: float | None = _Unset,
    ge: float | None = _Unset,
    lt: float | None = _Unset,
    le: float | None = _Unset,
    multiple_of: float | None = _Unset,
    allow_inf_nan: bool | None = _Unset,
    max_digits: int | None = _Unset,
    decimal_places: int | None = _Unset,
    min_length: int | None = _Unset,
    max_length: int | None = _Unset,
    union_mode: Literal["smart", "left_to_right"] | None = _Unset,
    extra: dict[str, Any] | None = _Unset,
    **_kwargs: Any,
) -> _Relationship[Any]:
    _kwargs = _kwargs or _Unset  # type:ignore
    _marker = _RelationshipMarker
    if alias not in (_Unset, None) and not isinstance(alias, str):
        raise TypeError("Invalid `alias` type. it should be `str`")
    if validation_alias not in (_Unset, None) and not isinstance(validation_alias, str):
        raise TypeError("Invalid `validation_alias` type. it should be `str`")
    if serialization_alias not in (_Unset, None) and not isinstance(serialization_alias, str):
        raise TypeError("Invalid `serialization_alias` type. it should be `str`")
    if serialization_alias in (_Unset, None):
        serialization_alias = alias
    if validation_alias in (_Unset, None):
        validation_alias = alias
    __rv = FieldInfo(**locals())
    __rv.metadata.append(_marker)
    return cast(_Relationship, __rv)
