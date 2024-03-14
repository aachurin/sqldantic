from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any, Callable, cast

from pydantic import BaseModel, ConfigDict
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from sqlalchemy.orm import MappedColumn, declared_attr, instrumentation
from sqlalchemy.orm.base import DEFAULT_STATE_ATTR
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.orm.relationships import Relationship as SQLARelationship

from . import typing_extra
from .field import Field, Relationship, _FieldMarker, _Marker
from .orm import Registry

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm.decl_api import _TypeAnnotationMapType
    from sqlalchemy.types import TypeEngine

__all__ = ("Field", "Relationship", "DeclarativeBase")


# patch ClassManager to use object.__setattr__ instead of setattr
def _state_setter(state_attr: str) -> Callable[[Any, Any], None]:
    _setattr = object.__setattr__

    def _state_setter(obj: Any, value: Any) -> None:
        _setattr(obj, state_attr, value)

    return _state_setter


instrumentation.ClassManager._state_setter = staticmethod(_state_setter(DEFAULT_STATE_ATTR))


class SQLModelMetaclass(ModelMetaclass, DeclarativeMeta):
    def __new__(
        mcs,
        cls_name: str,
        bases: tuple[type[Any], ...],
        namespace: dict[str, Any],
        table: bool = False,
        **kwargs: Any,
    ) -> Any:
        # does not allow to reset parent namespace
        # below we will set it manually
        kwargs["__pydantic_reset_parent_namespace__"] = False

        if bases == (BaseModel,):
            # for DeclarativeBase
            return super().__new__(mcs, cls_name, bases, namespace, **kwargs)

        if bases == (DeclarativeBase,):
            # for any DeclarativeBase
            if table:
                raise TypeError("Could not use `table` with DeclarativeBase.")
            config = {
                "metadata": namespace.pop("metadata", None),
                "type_annotation_map": namespace.pop("type_annotation_map", None),
                "json_type": namespace.pop("json_type", None),
            }
            for key in namespace:
                if key in ("__module__", "__qualname__", "model_config"):
                    continue
                raise TypeError(
                    f"Attribute `{cls_name}.{key}` is not allowed in declarative base class."
                )
            cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)
            _setup_declarative_base(cls, **config)
            return cls

        for b in bases:
            if getattr(b, "__sqldantic_table__", False):
                raise TypeError(f"Subclassing table `{b.__module__}.{b.__name__}` is not supported.")

        _adapt_annotations(cls_name, namespace, parent_depth=1)

        if table:
            # must set DEFAULT_STATE_ATTR slot here
            # otherwise sqlalchemy.inspect returns wrong result
            namespace["__slots__"] = tuple(list(namespace.get("__slots__", [])) + [DEFAULT_STATE_ATTR])

        # initialize __pydantic_parent_namespace__ manually
        namespace["__pydantic_parent_namespace__"] = typing_extra.pydantic_parent_frame_namespace(
            parent_depth=1
        )

        # initialize class for pydantic (sqlalchemy not uses __new__)
        cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)

        if table:
            config = getattr(cls, "model_config")
            config["table"] = True
            config["read_with_orm_mode"] = True
            setattr(cls, "__sqldantic_table__", True)

        return cls

    def __init__(cls, cls_name: Any, bases: Any, namespace: Any, **kw: Any) -> None:
        ModelMetaclass.__init__(cls, cls_name, bases, namespace, **kw)
        if _populate_model_to_parent_namespace(cls, parent_depth=1):
            _update_incomplete_models(cls, parent_depth=1)
        if not getattr(cls, "__pydantic_complete__", False):
            getattr(cls, "__sqldantic_incomplete_models__").add(cls)
        else:
            _complete_model_init(cast(type[DeclarativeBase], cls), parent_depth=1)


def _populate_model_to_parent_namespace(cls: type[Any], *, parent_depth: int) -> bool:
    ns = typing_extra.parent_writable_namespace(parent_depth=parent_depth + 1)
    if ns is not None:
        # works only for module level namespace (aka global)
        # in other namespaces need to call `model_rebuild`
        ns[cls.__name__] = cls
        return True
    return False


def _update_incomplete_models(
    cls: type[Any],
    *,
    raise_errors: bool = False,
    parent_depth: int,
) -> None:
    parent_depth += 1
    if incomplete_models := getattr(cls, "__sqldantic_incomplete_models__", None):
        for cls in list(incomplete_models):
            cls.model_rebuild(raise_errors=raise_errors, _parent_namespace_depth=parent_depth)


def _complete_model_init(cls: type[DeclarativeBase], *, parent_depth: int) -> None:
    incomplete_models = getattr(cls, "__sqldantic_incomplete_models__", None)
    if incomplete_models and cls in incomplete_models:
        incomplete_models.remove(cls)

    for key, field in cls.model_fields.items():
        if field.validation_alias:
            cls.model_config["populate_by_name"] = True
            cls.model_rebuild(force=True, _parent_namespace_depth=parent_depth + 1)
            break

    if getattr(cls, "__sqldantic_table__", False):
        if cls.model_config.get("extra") == "allow":
            cls.__generic_new__ = _declarative_base_table__new__extra
        else:
            cls.__generic_new__ = _declarative_base_table__new__
        cls.__generic_init__ = _declarative_base_table__init__
        if cls.model_config.get("validate_assignment"):
            cls.__generic_setattr__ = _declarative_base_table__setattr__validate
        else:
            cls.__generic_setattr__ = _declarative_base_table__setattr__
        cls.__generic_delattr__ = _declarative_base_table__delattr__
        cls.__init_values__ = _compile_init_values(cls)  # type:ignore

        annotations: dict[str, Any] = {}
        for key, field in cls.model_fields.items():
            annotations[key], default = _mapped_column_from_field(cls, key, field)
            setattr(cls, key, default)
        cls.__annotations__ = annotations
        DeclarativeMeta.__init__(cast(DeclarativeMeta, cls), cls.__name__, cls.__bases__, {})


def _setup_declarative_base(
    cls: type,
    *,
    metadata: Any,
    type_annotation_map: _TypeAnnotationMapType | None,
    json_type: type[TypeEngine[Any]] | TypeEngine[Any] | None = None,
) -> None:

    registry = Registry(
        metadata=metadata,
        type_annotation_map=type_annotation_map,
        json_type=json_type,
    )
    _check_registry_type_annotation_map(cls, registry)

    setattr(cls, "_sa_registry", registry)
    setattr(cls, "metadata", registry.metadata)
    setattr(cls, "__sqldantic_table__", False)
    # we need special incomplete types registry (not threadsafe)
    # to rebuild incomplete pydantic models before creating sqlalchemy models
    setattr(cls, "__sqldantic_incomplete_models__", weakref.WeakSet())


def _check_registry_type_annotation_map(cls: type[Any], registry: Registry) -> None:
    cls_name = cls.__name__
    for key in registry.type_annotation_map:

        # NOTE:
        # the use of annotated_types.* in type_annotation_map is not prohibited,
        # but may not be safe in some situations
        # EXAMPLE:
        # A = Annotated[int, Ge(-32768), Lt(32768)]
        # ...
        # class Base(DeclarativeBase):
        #     type_annotation_map = {
        #         A: SmallInteger(),
        #         ...
        #     }
        #
        # class Foo(Base):
        #     a: Mapped[A]  <-- works well
        #     b: Mapped[A] = Field(lt=100)  <-- will not work, result annotation is
        #                                       Annotated[int, Lt(100), Ge(-32768), Lt(32768)]

        if typing_extra.is_annotated(key):
            unwanted_types = (
                FieldInfo,
                MappedColumn,
                SQLARelationship,
            )
            for meta in key.__metadata__:
                if isinstance(meta, unwanted_types):
                    meta_name = f"{type(meta).__module__}.{type(meta).__name__}"
                    raise TypeError(
                        f"Using `{meta_name}` in Annotated types "
                        f"inside `{cls_name}.type_annotation_map` can lead to unwanted results "
                        f"and should be avoided:\n    {key}"
                    )


def _adapt_annotations(
    cls_name: str,
    namespace: dict[str, Any],
    *,
    parent_depth: int,
) -> None:
    if not (annotations := namespace.get("__annotations__")):  # pragma: no cover
        return None

    parent_depth += 1
    for key, ann_type in annotations.items():
        annotations[key] = typing_extra.unmapped_annotation(ann_type, parent_depth=parent_depth)
        field = namespace.get(key)
        if isinstance(field, MappedColumn):
            raise TypeError(
                f"Type annotation for `{cls_name}.{key}` can't be correctly interpreted:\n"
                f"Use `sqldantic.Field` instead of `sqlalchemy.orm.mapped_column`."
            )
        if isinstance(field, SQLARelationship):
            raise TypeError(
                f"Type annotation for `{cls_name}.{key}` can't be correctly interpreted:\n"
                f"Use `sqldantic.Relationship` instead of `sqlalchemy.orm.relationship`."
            )


def _compile_init_values(cls: BaseModel) -> Any:
    from sqlalchemy.orm.attributes import set_attribute

    globals_ = {"set_attribute": set_attribute}
    code = [
        "def __init_values__(self, values):",
        "  va = self.__pydantic_validator__.validate_assignment",
        "  sa = set_attribute",
        "  mf = self.model_fields",
        "  dd = {}",
        "  rd = {}",
    ]
    for name, field in cls.model_fields.items():
        if field.validation_alias:
            code += [
                f"  if {field.validation_alias!r} in values:",
                # set new dict for speedup (validate_assignment always create new __dict__)
                r"    self.__dict__ = dd",
                f"    va(self, {name!r}, values.pop({field.validation_alias!r}))",
                f"    rd[{name!r}] = self.__dict__[{name!r}]",
            ]
        code += [
            f"  {'elif' if field.validation_alias else 'if'} {name!r} in values:",
            r"    self.__dict__ = dd",
            f"    va(self, {name!r}, values.pop({name!r}))",
            f"    rd[{name!r}] = self.__dict__[{name!r}]",
        ]
        if not field.is_required():
            code += [
                r"  else:",
                f"    rd[{name!r}] = mf[{name!r}].get_default(call_default_factory=True)",
            ]
    code += [
        "  self.__dict__ = dd",
        "  for key, value in rd.items():",
        "    sa(self, key, value)",
    ]
    exec("\n".join(code), globals_, globals_)
    return globals_["__init_values__"]


def _get_declarative_base_table_methods() -> (
    tuple[Callable, Callable, Callable, Callable, Callable, Callable]
):
    from sqlalchemy.orm.attributes import del_attribute, set_attribute

    basemodel_setattr = BaseModel.__setattr__
    basemodel_delattr = BaseModel.__delattr__
    object_setattr = object.__setattr__
    object_new = object.__new__

    def table__new__(cls: type[DeclarativeBase], *_args: Any, **_kwargs: Any) -> Any:
        self = object_new(cls)
        # sqlalchemy not uses __init__
        # so, need initialize pydantic state here
        object_setattr(self, "__pydantic_extra__", None)
        object_setattr(self, "__pydantic_fields_set__", set())
        if cls.__pydantic_post_init__:
            self.model_post_init(None)
        else:
            # Note: if there are any private attributes, cls.__pydantic_post_init__ would exist
            # Since it doesn't, that means that `__pydantic_private__` should be set to None
            object_setattr(self, "__pydantic_private__", None)
        return self

    def table__new__extra(cls: type[DeclarativeBase], *_args: Any, **_kwargs: Any) -> Any:
        self = object_new(cls)
        # sqlalchemy not uses __init__
        # so, need initialize pydantic state here
        object_setattr(self, "__pydantic_extra__", {})
        object_setattr(self, "__pydantic_fields_set__", set())
        if cls.__pydantic_post_init__:
            self.model_post_init(None)
        else:
            # Note: if there are any private attributes, cls.__pydantic_post_init__ would exist
            # Since it doesn't, that means that `__pydantic_private__` should be set to None
            object_setattr(self, "__pydantic_private__", None)
        return self

    def table__init__(self: DeclarativeBase, **values: dict[str, Any]) -> None:
        self.__init_values__(values)
        if values:
            if private_attributes := self.__private_attributes__:
                # private attributes is already initialized in `table_new`
                for k, v in values.items():
                    if k not in private_attributes:
                        basemodel_setattr(self, k, v)
            else:  # pragma: no cover
                for k, v in values.items():
                    basemodel_setattr(self, k, v)

    def table__setattr__(self: DeclarativeBase, name: str, value: Any) -> None:
        if name in self.model_fields:
            # Set in Pydantic model to trigger possible validation changes
            self.__pydantic_fields_set__.add(name)
            # Set in Sqlalchemy model to trigger events and updates
            set_attribute(self, name, value)
        else:
            basemodel_setattr(self, name, value)

    def table__setattr__validate(self: DeclarativeBase, name: str, value: Any) -> None:
        if name in self.model_fields:
            # Set in Pydantic model to trigger possible validation changes
            current_dict = self.__dict__
            self.__dict__ = {}
            self.__pydantic_validator__.validate_assignment(self, name, value)
            value = self.__dict__[name]
            self.__dict__ = current_dict
            # Set in Sqlalchemy model to trigger events and updates
            set_attribute(self, name, value)
        else:
            basemodel_setattr(self, name, value)

    def table__delattr__(self: DeclarativeBase, name: str) -> None:
        if name in self.model_fields:
            del_attribute(self, name)
        else:
            basemodel_delattr(self, name)

    return (
        table__new__,
        table__new__extra,
        table__init__,
        table__setattr__,
        table__setattr__validate,
        table__delattr__,
    )


(
    _declarative_base_table__new__,
    _declarative_base_table__new__extra,
    _declarative_base_table__init__,
    _declarative_base_table__setattr__,
    _declarative_base_table__setattr__validate,
    _declarative_base_table__delattr__,
) = _get_declarative_base_table_methods()


def _mapped_column_from_field(
    cls: type[DeclarativeBase],
    key: str,
    field: FieldInfo,
) -> tuple[Any, MappedColumn | SQLARelationship | None]:
    marker = field._attributes_set.get("_marker") or _FieldMarker
    assert isinstance(marker, _Marker)

    for meta in field.metadata:
        if isinstance(meta, MappedColumn):
            raise TypeError(
                f"Type annotation for `{cls.__name__}.{key}` can't be correctly interpreted:\n"
                f"Use `sqldantic.Field` instead of `sqlalchemy.orm.mapped_column` "
                "inside Annotated types."
            )
        if isinstance(meta, SQLARelationship):
            raise TypeError(
                f"Type annotation for `{cls.__name__}.{key}` can't be correctly interpreted:\n"
                f"Use `sqldantic.Relationship` instead of `sqlalchemy.orm.relationship` "
                "inside Annotated types."
            )
        if isinstance(meta, _Marker) and meta is not marker:
            raise TypeError(
                f"Type annotation for `{cls.__name__}.{key}` can't be correctly interpreted:\n"
                f"Don't mix `sqldantic.Field` and `sqldantic.Relationship` "
            )

    return (
        typing_extra.mapped_from_field(field),
        marker.construct(field),
    )


class DeclarativeBase(BaseModel, metaclass=SQLModelMetaclass):
    __slots__ = ("__weakref__",)

    __pydantic_parent_namespace__ = None

    model_config = ConfigDict(validate_assignment=False, extra="forbid")

    if TYPE_CHECKING:  # pragma: no cover
        _sa_registry: Registry

        def __init_values__(self, values: dict[str, Any]) -> None: ...

    __generic_new__ = object.__new__
    __generic_init__ = BaseModel.__init__
    __generic_setattr__ = BaseModel.__setattr__
    __generic_delattr__ = BaseModel.__delattr__

    def __new__(cls: type[DeclarativeBase], *_args: Any, **_kwargs: Any) -> Any:
        return cls.__generic_new__(cls)

    def __init__(self: DeclarativeBase, **values: dict[str, Any]) -> None:
        self.__generic_init__(**values)

    def __setattr__(self: DeclarativeBase, name: str, value: Any) -> None:
        self.__generic_setattr__(name, value)

    def __delattr__(self: DeclarativeBase, name: str) -> None:
        self.__generic_delattr__(name)

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    @classmethod
    def update_incomplete_models(cls, *, _parent_namespace_depth: int = 0) -> None:
        _update_incomplete_models(
            cls,
            raise_errors=True,
            parent_depth=_parent_namespace_depth + 1,
        )

    @classmethod
    def model_rebuild(
        cls,
        *,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 0,
        _types_namespace: dict[str, Any] | None = None,
    ) -> bool | None:
        complete = cls.__pydantic_complete__
        result = super().model_rebuild(
            force=force,
            raise_errors=raise_errors,
            # +1 current frame, +1 super().model_rebuild frame, +1 _typing_extra.parent_frame_namespace
            _parent_namespace_depth=_parent_namespace_depth + 3,
            _types_namespace=_types_namespace,
        )
        if result and not complete:
            _complete_model_init(cls, parent_depth=_parent_namespace_depth + 1)
        return result
