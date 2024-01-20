from __future__ import annotations

import enum
import sys
from collections.abc import Collection
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    ClassVar,
    Literal,
    cast,
    dataclass_transform,
    get_args,
    get_origin,
)

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo as PydanticFieldInfo
from pydantic.fields import ModelPrivateAttr, PydanticUndefined, _Unset
from sqlalchemy.orm import Mapped, MappedColumn, declared_attr, instrumentation, mapped_column
from sqlalchemy.orm import registry as Registry
from sqlalchemy.orm import relationship
from sqlalchemy.orm.base import DEFAULT_STATE_ATTR, _MappedAnnotationBase
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.orm.relationships import Relationship as SqlalchemyRelationship
from sqlalchemy.sql.base import _NoArg
from sqlalchemy.sql.schema import SchemaConst

if TYPE_CHECKING:
    from sqlalchemy.orm.query import Query
    from sqlalchemy.orm.relationships import (
        ORMBackrefArgument,
        RelationshipProperty,
        _LazyLoadArgumentType,
        _ORMColCollectionArgument,
        _ORMOrderByArgument,
        _RelationshipArgumentType,
        _RelationshipJoinConditionArgument,
        _RelationshipSecondaryArgument,
    )
    from sqlalchemy.sql._typing import _AutoIncrementType, _InfoType, _TypeEngineArgument
    from sqlalchemy.sql.base import SchemaEventTarget
    from sqlalchemy.sql.schema import FetchedValue, _ServerDefaultArgument


__all__ = ("Field", "Relationship", "DeclarativeBase")


class _Args:
    __slots__ = ("args", "kwargs")
    _empty: ClassVar[_Args]

    def __new__(cls, args: tuple[Any, ...], kwargs: dict[str, Any]) -> _Args:
        if not args and not kwargs:
            return cls._empty
        return super().__new__(cls)

    def __init__(self, args: tuple[Any, ...], kwargs: dict[str, Any]):
        self.args = args
        self.kwargs = kwargs

    def __bool__(self) -> bool:
        return bool(self.args or self.kwargs)


_Args._empty = object.__new__(_Args)
_Args._empty.args = ()
_Args._empty.kwargs = {}


class _FieldInfo:
    __slots__ = ("sqla_args", "pydantic_args")

    _empty: ClassVar[_FieldInfo]
    sqlalchemy_meta: ClassVar[Callable] = staticmethod(mapped_column)
    pydantic_meta: ClassVar[Callable] = staticmethod(PydanticField)

    def __new__(cls, sqla_args: _Args, pydantic_args: _Args) -> _FieldInfo:
        if not sqla_args and not pydantic_args:
            return cls._empty
        return super().__new__(cls)

    def __init__(self, sqla_args: _Args, pydantic_args: _Args):
        self.sqla_args = sqla_args
        self.pydantic_args = pydantic_args

    def get_sqlalchemy_meta(self) -> Any:
        return self.sqlalchemy_meta(*self.sqla_args.args, **self.sqla_args.kwargs)

    def get_pydantic_meta(self) -> Any:
        return self.pydantic_meta(*self.pydantic_args.args, **self.pydantic_args.kwargs)

    def merged(self, info: _FieldInfo) -> _FieldInfo:
        new_sqla_args = _Args(
            args=info.sqla_args.args or self.sqla_args.args,
            kwargs={**self.sqla_args.kwargs, **info.sqla_args.kwargs},
        )
        new_pydantic_args = _Args(
            args=info.pydantic_args.args or self.pydantic_args.args,
            kwargs={**self.pydantic_args.kwargs, **info.pydantic_args.kwargs},
        )
        return self.__class__(new_sqla_args, new_pydantic_args)


_FieldInfo._empty = object.__new__(_FieldInfo)
_FieldInfo._empty.sqla_args = _Args._empty
_FieldInfo._empty.pydantic_args = _Args._empty


class _RelationshipInfo(_FieldInfo):
    sqlalchemy_meta: ClassVar[Callable] = staticmethod(relationship)


_RelationshipInfo._empty = object.__new__(_RelationshipInfo)
_RelationshipInfo._empty.sqla_args = _Args._empty
_RelationshipInfo._empty.pydantic_args = _Args._empty


class _Kind(enum.Enum):
    SQLALCHEMY = "sqlalchemy"
    PYDANTIC = "pydantic"
    UNSUPPORTED = "unsupported"


def _is_default(value: Any, default: Any) -> bool:
    if isinstance(default, (int, str, bool, float)):
        return value == default
    else:
        return value is default


def Field(
    # Column args
    __name_pos: str | _TypeEngineArgument[Any] | SchemaEventTarget | None = None,
    __type_pos: _TypeEngineArgument[Any] | SchemaEventTarget | None = None,
    *args: SchemaEventTarget,
    # Unsupported dataclass args
    init: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,
    repr: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,  # noqa: A002
    compare: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,
    kw_only: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,
    # MappedColumn args
    deferred: Annotated[_NoArg | bool, _Kind.SQLALCHEMY] = _NoArg.NO_ARG,
    deferred_group: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    deferred_raiseload: Annotated[bool | None, _Kind.SQLALCHEMY] = None,
    use_existing_column: Annotated[bool, _Kind.SQLALCHEMY] = False,
    insert_default: Annotated[Any, _Kind.SQLALCHEMY] = _NoArg.NO_ARG,
    active_history: Annotated[bool, _Kind.SQLALCHEMY] = False,
    sort_order: Annotated[_NoArg | int, _Kind.SQLALCHEMY] = _NoArg.NO_ARG,
    # Column args
    name: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    type_: Annotated[_TypeEngineArgument[Any] | None, _Kind.SQLALCHEMY] = None,
    autoincrement: Annotated[_AutoIncrementType, _Kind.SQLALCHEMY] = "auto",
    doc: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    key: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    index: Annotated[bool | None, _Kind.SQLALCHEMY] = None,
    unique: Annotated[bool | None, _Kind.SQLALCHEMY] = None,
    info: Annotated[_InfoType | None, _Kind.SQLALCHEMY] = None,
    nullable: Annotated[
        bool | Literal[SchemaConst.NULL_UNSPECIFIED] | None, _Kind.SQLALCHEMY
    ] = SchemaConst.NULL_UNSPECIFIED,
    onupdate: Annotated[Any, _Kind.SQLALCHEMY] = None,
    primary_key: Annotated[bool | None, _Kind.SQLALCHEMY] = False,
    server_default: Annotated[_ServerDefaultArgument | None, _Kind.SQLALCHEMY] = None,
    server_onupdate: Annotated[FetchedValue | None, _Kind.SQLALCHEMY] = None,
    quote: Annotated[bool | None, _Kind.SQLALCHEMY] = None,
    system: Annotated[bool, _Kind.SQLALCHEMY] = False,
    comment: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    # Pydantic args
    default: Annotated[Any, _Kind.PYDANTIC] = PydanticUndefined,
    default_factory: Annotated[Callable[[], Any] | None, _Kind.PYDANTIC] = _Unset,
    alias: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    # Unsupported alias args
    alias_priority: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    # End
    validation_alias: Annotated[Any, _Kind.PYDANTIC] = _Unset,
    serialization_alias: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    # End
    title: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    description: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    examples: Annotated[list[Any] | None, _Kind.PYDANTIC] = _Unset,
    exclude: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    discriminator: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    json_schema_extra: Annotated[dict[str, Any] | Callable[[dict[str, Any]], None] | None, _Kind.PYDANTIC] = _Unset,
    frozen: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    validate_default: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    # Unsupported arg
    init_var: Annotated[bool | None, _Kind.UNSUPPORTED] = _Unset,
    # End
    pattern: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    strict: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    gt: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    ge: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    lt: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    le: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    multiple_of: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    allow_inf_nan: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    max_digits: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    decimal_places: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    min_length: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    max_length: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    union_mode: Annotated[Literal["smart", "left_to_right"], _Kind.PYDANTIC] = _Unset,
    # Column dialect kw
    **kw: Any,
) -> MappedColumn:
    # return MappedColumn for mypy, real type is Composite
    locals_ = locals()
    unsupported_args = []
    if init is not _NoArg.NO_ARG:
        unsupported_args.append("init")
    if repr is not _NoArg.NO_ARG:
        unsupported_args.append("repr")
    if compare is not _NoArg.NO_ARG:
        unsupported_args.append("compare")
    if kw_only is not _NoArg.NO_ARG:
        unsupported_args.append("kw_only")
    if init_var is not _Unset:
        unsupported_args.append("init_var")
    if unsupported_args:
        raise TypeError(
            f"Field includes dataclasses argument(s): {', '.join(unsupported_args)}\n"
            "Maybe you want use dataclasses instead of Pydantic models.\n"
            "See https://docs.sqlalchemy.org/en/20/orm/dataclasses.html for more info."
        )
    unsupported_args = []
    # if alias is not _Unset:
    #     unsupported_args.append("alias")
    if alias_priority is not _Unset:
        unsupported_args.append("alias_priority")
    # if validation_alias is not _Unset:
    #     unsupported_args.append("validation_alias")
    # if serialization_alias is not _Unset:
    #     unsupported_args.append("serialization_alias")
    if unsupported_args:
        raise TypeError(
            f"Field includes alias argument(s): {', '.join(unsupported_args)}\n"
            "I can't mix ORM fields with aliased fields."
        )
    if args:
        sqla_args = (__name_pos, __type_pos) + args
    elif __type_pos is not None:
        sqla_args = (__name_pos, __type_pos)
    elif __name_pos is not None:
        sqla_args = (__name_pos,)
    else:
        sqla_args = ()
    sqla_info = _Args(
        args=sqla_args,
        kwargs={
            **kw,
            **{k: locals_[k] for k, default in _sqlalchemy_field_args.items() if not _is_default(locals_[k], default)},
        },
    )
    pydantic_info = _Args(
        args=(),
        kwargs={k: locals_[k] for k, default in _pydantic_field_args.items() if not _is_default(locals_[k], default)},
    )
    return cast(MappedColumn, _FieldInfo(sqla_info, pydantic_info))


_pydantic_field_args = {k: Field.__kwdefaults__[k] for k, v in Field.__annotations__.items() if "_Kind.PYDANTIC" in v}
_sqlalchemy_field_args = {
    k: Field.__kwdefaults__[k] for k, v in Field.__annotations__.items() if "_Kind.SQLALCHEMY" in v
}


def Relationship(
    # Relationship args
    argument: _RelationshipArgumentType[Any] | None = None,
    secondary: _RelationshipSecondaryArgument | None = None,
    *,
    uselist: Annotated[bool | None, _Kind.SQLALCHEMY] = None,
    collection_class: Annotated[type[Collection[Any]] | Callable[[], Collection[Any]] | None, _Kind.SQLALCHEMY] = None,
    primaryjoin: Annotated[_RelationshipJoinConditionArgument | None, _Kind.SQLALCHEMY] = None,
    secondaryjoin: Annotated[_RelationshipJoinConditionArgument | None, _Kind.SQLALCHEMY] = None,
    back_populates: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    order_by: Annotated[_ORMOrderByArgument, _Kind.SQLALCHEMY] = False,
    backref: Annotated[ORMBackrefArgument | None, _Kind.SQLALCHEMY] = None,
    overlaps: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    post_update: Annotated[bool, _Kind.SQLALCHEMY] = False,
    cascade: Annotated[str, _Kind.SQLALCHEMY] = "save-update, merge",
    viewonly: Annotated[bool, _Kind.SQLALCHEMY] = False,
    # Unsupported dataclass args
    init: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,
    repr: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,  # noqa: A002
    # default: _NoArg | _T = _NoArg.NO_ARG,
    # default_factory: _NoArg  Callable[[], _T]] = _NoArg.NO_ARG,
    compare: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,
    kw_only: Annotated[_NoArg | bool, _Kind.UNSUPPORTED] = _NoArg.NO_ARG,
    # Relationship args
    lazy: Annotated[_LazyLoadArgumentType, _Kind.SQLALCHEMY] = "select",
    passive_deletes: Annotated[Literal["all"] | bool, _Kind.SQLALCHEMY] = False,
    passive_updates: Annotated[bool, _Kind.SQLALCHEMY] = True,
    active_history: Annotated[bool, _Kind.SQLALCHEMY] = False,
    enable_typechecks: Annotated[bool, _Kind.SQLALCHEMY] = True,
    foreign_keys: Annotated[_ORMColCollectionArgument | None, _Kind.SQLALCHEMY] = None,
    remote_side: Annotated[_ORMColCollectionArgument | None, _Kind.SQLALCHEMY] = None,
    join_depth: Annotated[int | None, _Kind.SQLALCHEMY] = None,
    comparator_factory: Annotated[type[RelationshipProperty.Comparator[Any]] | None, _Kind.SQLALCHEMY] = None,
    single_parent: Annotated[bool, _Kind.SQLALCHEMY] = False,
    innerjoin: Annotated[bool, _Kind.SQLALCHEMY] = False,
    distinct_target_key: Annotated[bool | None, _Kind.SQLALCHEMY] = None,
    load_on_pending: Annotated[bool, _Kind.SQLALCHEMY] = False,
    query_class: Annotated[type[Query[Any]] | None, _Kind.SQLALCHEMY] = None,
    info: Annotated[_InfoType | None, _Kind.SQLALCHEMY] = None,
    omit_join: Annotated[Literal[None, False], _Kind.SQLALCHEMY] = None,
    sync_backref: Annotated[bool | None, _Kind.SQLALCHEMY] = None,
    doc: Annotated[str | None, _Kind.SQLALCHEMY] = None,
    # Pydantic args
    default: Annotated[Any, _Kind.PYDANTIC] = PydanticUndefined,
    default_factory: Annotated[Callable[[], Any] | None, _Kind.PYDANTIC] = _Unset,
    # Unsupported alias args
    alias: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    alias_priority: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    validation_alias: Annotated[Any, _Kind.PYDANTIC] = _Unset,
    serialization_alias: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    # End
    title: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    description: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    examples: Annotated[list[Any] | None, _Kind.PYDANTIC] = _Unset,
    exclude: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    discriminator: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    json_schema_extra: Annotated[dict[str, Any] | Callable[[dict[str, Any]], None] | None, _Kind.PYDANTIC] = _Unset,
    frozen: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    validate_default: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    # Unsupported arg
    init_var: Annotated[bool | None, _Kind.UNSUPPORTED] = _Unset,
    # End
    pattern: Annotated[str | None, _Kind.PYDANTIC] = _Unset,
    strict: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    gt: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    ge: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    lt: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    le: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    multiple_of: Annotated[float | None, _Kind.PYDANTIC] = _Unset,
    allow_inf_nan: Annotated[bool | None, _Kind.PYDANTIC] = _Unset,
    max_digits: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    decimal_places: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    min_length: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    max_length: Annotated[int | None, _Kind.PYDANTIC] = _Unset,
    union_mode: Annotated[Literal["smart", "left_to_right"], _Kind.PYDANTIC] = _Unset,
) -> SqlalchemyRelationship[Any]:
    locals_ = locals()
    unsupported_args = []
    if init is not _NoArg.NO_ARG:
        unsupported_args.append("init")
    if repr is not _NoArg.NO_ARG:
        unsupported_args.append("repr")
    if compare is not _NoArg.NO_ARG:
        unsupported_args.append("compare")
    if kw_only is not _NoArg.NO_ARG:
        unsupported_args.append("kw_only")
    if unsupported_args:
        raise TypeError(
            f"Relationship includes dataclasses argument(s): {', '.join(unsupported_args)}\n"
            "Maybe you want use dataclasses instead of Pydantic models.\n"
            "See https://docs.sqlalchemy.org/en/20/orm/dataclasses.html for more info."
        )
    unsupported_args = []
    if alias is not _Unset:
        unsupported_args.append("alias")
    if alias_priority is not _Unset:
        unsupported_args.append("alias_priority")
    if validation_alias is not _Unset:
        unsupported_args.append("validation_alias")
    if serialization_alias is not _Unset:
        unsupported_args.append("serialization_alias")
    if unsupported_args:
        raise TypeError(
            f"Relationship includes alias argument(s): {', '.join(unsupported_args)}\n"
            "I can't mix ORM fields with aliased fields."
        )
    if secondary is not None:
        sqla_args: tuple[Any, ...] = (argument, secondary)
    elif argument is not None:
        sqla_args = (argument,)
    else:
        sqla_args = ()
    sqla_info = _Args(
        args=sqla_args,
        kwargs={k: locals_[k] for k, default in _sqlalchemy_rel_args.items() if not _is_default(locals_[k], default)},
    )
    pydantic_info = _Args(
        args=(),
        kwargs={k: locals_[k] for k, default in _pydantic_rel_args.items() if not _is_default(locals_[k], default)},
    )
    return cast(SqlalchemyRelationship, _RelationshipInfo(sqla_info, pydantic_info))


_pydantic_rel_args = {
    k: Relationship.__kwdefaults__[k] for k, v in Relationship.__annotations__.items() if "_Kind.PYDANTIC" in v
}
_sqlalchemy_rel_args = {
    k: Relationship.__kwdefaults__[k] for k, v in Relationship.__annotations__.items() if "_Kind.SQLALCHEMY" in v
}


# patch ClassManager to use object.__setattr__ instead of setattr
def _state_setter(state_attr: str) -> Callable[[Any, Any], None]:
    _setattr = object.__setattr__

    def _state_setter(obj: Any, value: Any) -> None:
        _setattr(obj, state_attr, value)

    return _state_setter


instrumentation.ClassManager._state_setter = staticmethod(_state_setter(DEFAULT_STATE_ATTR))


@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class SQLModelMetaclass(ModelMetaclass, DeclarativeMeta):
    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        table: bool = False,
        **kwargs: Any,
    ) -> Any:
        if bases == (BaseModel,):
            return super().__new__(mcs, cls_name, bases, namespace, **kwargs)

        if bases == (DeclarativeBase,):
            if table:
                raise TypeError("Could not use `table` with DeclarativeBase.")
            config = {
                "metadata": namespace.pop("metadata", None),
                "type_annotation_map": namespace.pop("type_annotation_map", None),
                "registry": namespace.pop("registry", None),
            }
            cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)
            _setup_declarative_base(cls, **config)
            return cls

        _check_namespace(cls_name, namespace)
        base_is_table = any(getattr(b, "__sqldantic_table__", False) for b in bases)
        sqla_annotations, sqla_namespace = _setup_annotations(cls_name, namespace)
        if table and not base_is_table:
            # add _sa_instance_state as a slot
            namespace["__slots__"] = tuple(list(namespace.get("__slots__", [])) + [DEFAULT_STATE_ATTR])

        # initialize class for pydantic (sqlalchemy not uses __new__)
        cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)
        if table:
            cls._init_values = _compile_init_values(cls)  # type:ignore
        # set annotations and namespace for sqlalchemy (sqlalchemy uses __init__)
        cls.__annotations__ = sqla_annotations
        for key, value in sqla_namespace.items():
            setattr(cls, key, value)

        # some special configurations
        if table and not base_is_table:
            config = getattr(cls, "model_config")
            config["table"] = True
            config["read_with_orm_mode"] = True

        if table:
            setattr(cls, "__sqldantic_table__", True)

        return cls

    def __init__(cls, cls_name: Any, bases: Any, namespace: Any, **kw: Any) -> None:
        if cls.__sqldantic_table__:  # type:ignore
            DeclarativeMeta.__init__(cls, cls_name, bases, namespace, **kw)
        else:
            ModelMetaclass.__init__(cls, cls_name, bases, namespace, **kw)


def _setup_declarative_base(
    cls: type,
    *,
    metadata: Any,
    type_annotation_map: Any,
    registry: Any,
) -> None:
    if registry is not None:
        if not isinstance(registry, Registry):
            raise TypeError(
                "Declarative base class has a 'registry' attribute that is "
                "not an instance of sqlalchemy.orm.registry()"
            )
        if type_annotation_map is not None:
            raise TypeError(
                "Declarative base class has both a 'registry' attribute and a "
                "type_annotation_map entry. Please apply the type_annotation_map "
                "to this registry directly."
            )
        if metadata is not None:
            raise TypeError(
                "Declarative base class has both a 'registry' attribute and a "
                "metadata entry. Please apply the metadata "
                "to this registry directly."
            )
    else:
        registry = Registry(metadata=metadata, type_annotation_map=type_annotation_map)
    setattr(cls, "_sa_registry", registry)
    setattr(cls, "metadata", registry.metadata)


def _check_namespace(cls_name: str, namespace: dict[str, Any]) -> None:
    if "metadata" in namespace:
        raise TypeError(f"Attribute {cls_name}.metadata is not allowed in declarative base subclasses.")

    if "registry" in namespace:
        raise TypeError(f"Attribute {cls_name}.registry is not allowed in declarative base subclasses.")

    if "type_annotation_map" in namespace:
        raise TypeError(f"Attribute {cls_name}.type_annotation_map is not allowed in declarative base subclasses.")


def _setup_annotations(cls_name: str, namespace: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    sqla_annotations = {}
    sqla_namespace = {}
    if annotations := namespace.get("__annotations__"):
        # split annotations
        globalns = _get_module_globals(namespace["__module__"])
        for key, raw_ann in annotations.items():
            # hassle-free annotation evaluation
            ann = _eval_annotation(raw_ann, globalns, namespace)
            origin = get_origin(ann)

            if origin is ClassVar:
                sqla_annotations[key] = raw_ann
                continue

            if key.startswith("_") or key in namespace and isinstance(namespace[key], ModelPrivateAttr):
                # ignore for sqlalchemy
                continue

            if origin and isinstance(origin, type) and issubclass(origin, _MappedAnnotationBase):
                # unwrap annotation for pydantic
                (annotations[key],) = get_args(ann)
                sqla_annotations[key] = raw_ann
            else:
                # and wrap for sqlalchemy
                sqla_annotations[key] = Mapped[raw_ann]  # type:ignore

            meta = namespace.get(key)
            if isinstance(meta, _FieldInfo):
                namespace[key] = meta.get_pydantic_meta()
                sqla_namespace[key] = meta.get_sqlalchemy_meta()
            elif isinstance(meta, PydanticFieldInfo):
                pass

    return sqla_annotations, sqla_namespace


def _get_module_globals(module_name: str) -> dict[str, Any]:
    try:
        return sys.modules[module_name].__dict__
    except KeyError as ke:
        raise NameError(
            f"Module {module_name} isn't present in sys.modules",
        ) from ke


def _eval_annotation(ann: Any, globalns: dict[str, Any], localns: dict[str, Any]) -> Any:
    if isinstance(ann, str):
        return eval(ann, globalns, localns)
    return ann


def _compile_init_values(cls: BaseModel) -> Any:
    from sqlalchemy.orm.attributes import set_attribute

    globals_ = {"set_attribute": set_attribute}
    code = [
        "def _init_values(self, values):",
        "  va = self.__pydantic_validator__.validate_assignment",
        "  sa = set_attribute",
        "  mf = self.model_fields",
        "  rs = {}",
    ]
    for name, field in cls.model_fields.items():
        if field.validation_alias:
            alias = field.validation_alias
        elif field.alias:
            alias = field.alias
        else:
            alias = name
        code += [
            f"  if '{alias}' in values:",
            r"    self.__dict__ = {}",
            f"    va(self, '{name}', values.pop('{alias}'))",
            f"    rs['{name}'] = self.__dict__['{name}']",
        ]
        if not field.is_required():
            code += [
                r"  else:",
                f"    rs['{name}'] = mf['{name}'].get_default(call_default_factory=True)",
            ]
    code += [
        "  self.__dict__ = {}",
        "  for key, value in rs.items():",
        "    sa(self, key, value)",
    ]
    exec("\n".join(code), globals_, globals_)
    return globals_["_init_values"]


def _install_declarative_base_methods() -> dict[str, Any]:
    from sqlalchemy.orm.attributes import del_attribute, set_attribute

    basemodel_init = BaseModel.__init__
    basemodel_setattr = BaseModel.__setattr__
    basemodel_delattr = BaseModel.__delattr__
    object_setattr = object.__setattr__

    def __new__(cls: type[DeclarativeBase], *_args: Any, **_kwargs: Any) -> Any:
        self = object.__new__(cls)  # type:ignore
        if cls.__sqldantic_table__:
            # sqlalchemy not uses __init__
            # so, need initialize pydantic state here
            extra: dict[str, Any] | None = {} if self.model_config.get("extra") == "allow" else None
            object_setattr(self, "__pydantic_extra__", extra)
            object_setattr(self, "__pydantic_fields_set__", set())
            if cls.__pydantic_post_init__:
                self.model_post_init(None)
            else:
                # Note: if there are any private attributes, cls.__pydantic_post_init__ would exist
                # Since it doesn't, that means that `__pydantic_private__` should be set to None
                object_setattr(self, "__pydantic_private__", None)
        return self

    def __init__(self: DeclarativeBase, **values: dict[str, Any]) -> None:
        if self.__sqldantic_table__:  # type:ignore
            self._init_values(values)
            if private_attributes := self.__private_attributes__:
                # private attributes is already initialized in __new__
                for k, v in values.items():
                    if k not in private_attributes:
                        basemodel_setattr(self, k, v)
            else:
                for k, v in values.items():
                    basemodel_setattr(self, k, v)
        else:
            basemodel_init(self, **values)

    def __setattr__(self: DeclarativeBase, name: str, value: Any) -> None:
        if self.__sqldantic_table__ and name in self.model_fields:
            # Set in Pydantic model to trigger possible validation changes
            if self.model_config.get("validate_assignment", False):
                current_dict = self.__dict__
                self.__dict__ = {}
                self.__pydantic_validator__.validate_assignment(self, name, value)
                value = self.__dict__[name]
                self.__dict__ = current_dict
            else:
                self.__pydantic_fields_set__.add(name)
            # Set in Sqlalchemy model to trigger events and updates
            set_attribute(self, name, value)
        else:
            basemodel_setattr(self, name, value)

    def __delattr__(self: DeclarativeBase, name: str) -> None:
        if self.__sqldantic_table__ and name in self.model_fields:
            del_attribute(self, name)
        else:
            basemodel_delattr(self, name)

    return dict(
        __new__=__new__,
        __init__=__init__,
        __setattr__=__setattr__,
        __delattr__=__delattr__,
    )


class DeclarativeBase(BaseModel, metaclass=SQLModelMetaclass):
    __slots__ = ("__weakref__",)

    __sqldantic_table__: ClassVar[bool] = False

    model_config = ConfigDict(validate_assignment=True)

    if TYPE_CHECKING:

        def _init_values(self, values: dict[str, Any]) -> None:
            ...

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    locals().update(_install_declarative_base_methods())
