from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any, Callable, cast

import annotated_types
from pydantic import BaseModel, ConfigDict
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from sqlalchemy import inspect
from sqlalchemy.orm import MappedColumn, declared_attr, instrumentation
from sqlalchemy.orm import registry as Registry
from sqlalchemy.orm.base import DEFAULT_STATE_ATTR
from sqlalchemy.orm.decl_api import DeclarativeMeta
from sqlalchemy.orm.relationships import Relationship as SQLARelationship

from . import typing_extra
from .field import Field, Relationship, _MappedMetaMarker
from .sqltypes import PostponedAnnotation

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
        kwargs["__pydantic_reset_parent_namespace__"] = False

        if bases == (BaseModel,):
            return super().__new__(mcs, cls_name, bases, namespace, **kwargs)

        if bases == (DeclarativeBase,):
            if table:
                raise TypeError("Could not use `table` with DeclarativeBase.")
            config = {
                "metadata": namespace.pop("metadata", None),
                "type_annotation_map": namespace.pop("type_annotation_map", None),
            }
            for key in namespace:
                if key in ("__module__", "__qualname__", "model_config"):
                    continue
                raise TypeError(f"Attribute `{cls_name}.{key}` is not allowed in declarative base class.")
            cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)
            _setup_declarative_base(cls, **config)
            return cls

        for b in bases:
            if getattr(b, "__sqldantic_table__", False):
                raise TypeError(f"Subclassing {b.__name__} is not supported.")

        _adapt_annotations(cls_name, namespace)

        if table:
            # must set DEFAULT_STATE_ATTR slot here
            # otherwise sqlalchemy.inspect returns wrong result
            namespace["__slots__"] = tuple(list(namespace.get("__slots__", [])) + [DEFAULT_STATE_ATTR])

        # need manual initialization of __pydantic_parent_namespace__
        # otherwise it will be incorrectly initialized from the current frame
        namespace["__pydantic_parent_namespace__"] = typing_extra.pydantic_parent_frame_namespace()

        # initialize class for pydantic (sqlalchemy not uses __new__)
        cls = super().__new__(mcs, cls_name, bases, namespace, **kwargs)

        if table:
            cls._init_values = _compile_init_values(cls)  # type:ignore
            config = getattr(cls, "model_config")
            config["table"] = True
            config["read_with_orm_mode"] = True
            setattr(cls, "__sqldantic_table__", True)

        return cls

    def __init__(cls, cls_name: Any, bases: Any, namespace: Any, **kw: Any) -> None:
        ModelMetaclass.__init__(cls, cls_name, bases, namespace, **kw)
        if _populate_model_to_parent_namespace(cls):
            _update_incomplete_models(cls)
        if not getattr(cls, "__pydantic_complete__", False):
            getattr(cls, "__sqldantic_incomplete_models__").add(cls)
        else:
            _complete_model_init(cls)


def _populate_model_to_parent_namespace(cls: type[Any], *, parent_depth: int = 1) -> bool:
    ns = typing_extra.parent_writable_namespace(parent_depth=parent_depth + 1)
    if ns is not None:
        ns[cls.__name__] = cls
        return True
    return False


def _update_incomplete_models(
    cls: type[Any],
    *,
    raise_errors: bool = False,
    parent_depth: int = 1,
) -> None:
    if incomplete_models := getattr(cls, "__sqldantic_incomplete_models__", None):
        for cls in list(incomplete_models):
            cls.model_rebuild(raise_errors=raise_errors, _parent_namespace_depth=parent_depth + 1)


def _complete_model_init(cls: type[Any]) -> None:
    incomplete_models = getattr(cls, "__sqldantic_incomplete_models__", None)
    if incomplete_models and cls in incomplete_models:
        incomplete_models.remove(cls)

    if getattr(cls, "__sqldantic_table__", False):
        annotations: dict[str, Any] = {}
        models_fields = getattr(cls, "model_fields")
        for key, field in models_fields.items():
            ann, default = _mapped_column_from_field(cls.__name__, key, field)
            annotations[key] = ann
            if default is not None:
                setattr(cls, key, default)
        cls.__annotations__ = annotations
        DeclarativeMeta.__init__(cast(DeclarativeMeta, cls), cls.__name__, cls.__bases__, {})
        for column in inspect(cls).columns:
            if isinstance(column.type, PostponedAnnotation):
                column.type.provide_annotation(*typing_extra.annotation_from_field(models_fields[column.key]))


def _setup_declarative_base(
    cls: type,
    *,
    metadata: Any,
    type_annotation_map: Any,
) -> None:
    registry = Registry(metadata=metadata, type_annotation_map=type_annotation_map)
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
        if typing_extra.is_annotated(key):
            for meta in key.__metadata__:
                if isinstance(meta, FieldInfo):
                    raise TypeError(
                        "Using `sqldantic.Field`, `sqldantic.Relationship` and `pydantic.Field` in Annotated types "
                        f"inside `{cls_name}.type_annotation_map` can lead to unwanted results "
                        f"and should be avoided:\n    {key}"
                    )
                if isinstance(meta, MappedColumn):
                    raise TypeError(
                        "Using `sqlalchemy.orm.mapped_column` in Annotated types "
                        f"inside `{cls_name}.type_annotation_map` can lead to unwanted results"
                        f"and should be avoided:\n    {key}"
                    )
                if isinstance(meta, SQLARelationship):
                    raise TypeError(
                        "Using `sqlalchemy.orm.relationship` in Annotated types "
                        f"inside `{cls_name}.type_annotation_map` can lead to unwanted results"
                        f"and should be avoided:\n    {key}"
                    )
                if isinstance(meta, annotated_types.BaseMetadata):
                    raise TypeError(
                        f"Using `{type(meta).__module__}.{type(meta).__name__}` in Annotated types "
                        f"inside `{cls_name}.type_annotation_map` can lead to unwanted results"
                        f"and should be avoided:\n    {key}"
                    )


def _adapt_annotations(cls_name: str, namespace: dict[str, Any], *, parent_depth: int = 1) -> None:
    if not (annotations := namespace.get("__annotations__")):
        return

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
        "def _init_values(self, values):",
        "  va = self.__pydantic_validator__.validate_assignment",
        "  sa = set_attribute",
        "  mf = self.model_fields",
        "  rd = {}",
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
            f"    rd['{name}'] = self.__dict__['{name}']",
        ]
        if not field.is_required():
            code += [
                r"  else:",
                f"    rd['{name}'] = mf['{name}'].get_default(call_default_factory=True)",
            ]
    code += [
        "  self.__dict__ = {}",
        "  for key, value in rd.items():",
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
        if cls.__sqldantic_table__:  # type:ignore
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
        if self.__sqldantic_table__ and name in self.model_fields:  # type:ignore
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
        if self.__sqldantic_table__ and name in self.model_fields:  # type:ignore
            del_attribute(self, name)
        else:
            basemodel_delattr(self, name)

    return dict(
        __new__=__new__,
        __init__=__init__,
        __setattr__=__setattr__,
        __delattr__=__delattr__,
    )


def _mapped_column_from_field(
    cls_name: str,
    key: str,
    field: FieldInfo,
) -> tuple[Any, MappedColumn | SQLARelationship | None]:
    marker = field._attributes_set.get("_marker")
    assert marker is None or isinstance(marker, _MappedMetaMarker)

    for meta in field.metadata:
        if isinstance(meta, MappedColumn):
            raise TypeError(
                f"Type annotation for `{cls_name}.{key}` can't be correctly interpreted:\n"
                f"Use `sqldantic.Field` instead of `sqlalchemy.orm.mapped_column` inside Annotated types."
            )
        if isinstance(meta, SQLARelationship):
            raise TypeError(
                f"Type annotation for `{cls_name}.{key}` can't be correctly interpreted:\n"
                f"Use `sqldantic.Relationship` instead of `sqlalchemy.orm.relationship` inside Annotated types."
            )
        if isinstance(meta, _MappedMetaMarker) and meta is not marker:
            raise TypeError(
                f"Type annotation for `{cls_name}.{key}` can't be correctly interpreted:\n"
                f"Don't mix `sqldantic.Field` and `sqldantic.Relationship` "
            )

    return (
        typing_extra.mapped_from_field(field),
        marker.construct(field) if marker else None,
    )


class DeclarativeBase(BaseModel, metaclass=SQLModelMetaclass):
    __slots__ = ("__weakref__",)

    __pydantic_parent_namespace__ = None

    model_config = ConfigDict(validate_assignment=True)

    if TYPE_CHECKING:

        def _init_values(self, values: dict[str, Any]) -> None: ...

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    locals().update(_install_declarative_base_methods())

    @classmethod
    def update_incomplete_models(cls, *, parent_depth: int = 0) -> None:
        _update_incomplete_models(
            cls,
            raise_errors=True,
            parent_depth=parent_depth + 1,
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
        assert not force, "model_rebuild(force=True) is not supported"
        result = super().model_rebuild(
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth + 3,
            # +1 current frame
            # +1 super().model_rebuild frame
            # +1 _typing_extra.parent_frame_namespace
            _types_namespace=_types_namespace,
        )
        if result:
            _complete_model_init(cls)
        return result
