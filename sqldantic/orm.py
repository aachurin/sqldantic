from __future__ import annotations

import collections
import datetime
import decimal
import functools
import ipaddress
import pathlib
import re
import typing
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, cast, get_args, get_origin

import pydantic
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Interval,
    LargeBinary,
    Numeric,
    String,
    Time,
    Uuid,
)
from sqlalchemy.orm import MappedColumn as _MappedColumn
from sqlalchemy.orm import mapped_column as _mapped_column
from sqlalchemy.orm import registry as _Registry
from sqlalchemy.sql.type_api import TypeEngine, to_instance

from . import typing_extra
from .sqltypes import CidrType, InetType, _SpecialTyped

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm.decl_api import MetaData, _MatchedOnType, _TypeAnnotationMapType
    from sqlalchemy.util.typing import _AnnotationScanType


class MappedColumn(_MappedColumn):
    __slots__ = ()

    def _init_column_for_annotation(
        self,
        cls: type[Any],
        registry: _Registry,
        argument: _AnnotationScanType,
        originating_module: str | None,
    ) -> None:
        with _provide_annotation(argument):
            super()._init_column_for_annotation(cls, registry, argument, originating_module)
        type_ = self.column.type
        if isinstance(type_, _SpecialTyped):
            if type_.annotation is None:
                type_.set_annotation(argument)


def mapped_column(*args: Any, **kwargs: Any) -> _MappedColumn:
    rv = _mapped_column(*args, **kwargs)
    rv.__class__ = MappedColumn
    return rv


_original_annotation: ContextVar[Any] = ContextVar("_original_annotation")


@contextmanager
def _provide_annotation(annotation: Any) -> Iterator[None]:
    token = _original_annotation.set(annotation)
    try:
        yield
    finally:
        _original_annotation.reset(token)


def get_original_annotation() -> Any:
    return _original_annotation.get()


class TypeLookupError(TypeError):
    pass


class Registry(_Registry):

    json_type: type[TypeEngine[Any]] | TypeEngine[Any] = JSON

    def __init__(
        self,
        *,
        metadata: MetaData | None = None,
        type_annotation_map: _TypeAnnotationMapType | None = None,
        json_type: type[TypeEngine[Any]] | TypeEngine[Any] | None = None,
    ):
        super().__init__(
            metadata=metadata, type_annotation_map=cast("_TypeAnnotationMapType", DEFAULT_TYPE_MAP)
        )
        if type_annotation_map:
            self.update_type_annotation_map(type_annotation_map)
        if json_type:
            self.json_type = json_type

    def _resolve_union(self, python_type: Any, seen_types: set[Any]) -> TypeEngine[Any] | None:
        special_typed = False
        union_types: set[Any] = set()
        for arg in get_args(python_type):
            with _provide_annotation(arg):
                resolved = self._resolve_cascade(arg, seen_types)
            if resolved is None:
                # ignore recursive types
                continue
            if isinstance(resolved, _SpecialTyped):
                special_typed = True
                union_types.add(type(resolved.impl))
            else:
                union_types.add(type(resolved))
        if not union_types:
            raise TypeLookupError("Empty union type")
        union_types_list = list(union_types)
        if special_typed:
            if len(union_types_list) > 1 or type(None) in union_types_list:
                return _SpecialTyped()
            return _SpecialTyped(union_types_list[0])
        elif len(union_types_list) == 1:
            return to_instance(union_types_list[0])
        else:
            return _SpecialTyped()

    def _resolve_cascade(self, python_type: Any, seen_types: set[Any]) -> TypeEngine[Any] | None:
        if python_type in seen_types:
            # already see this type, but it was not resolved to any sqlalchemy type
            return None

        if typing_extra.is_union(python_type):
            return self._resolve_union(python_type, seen_types)

        if typing_extra.is_special_generic_alias(python_type):
            python_type = get_origin(python_type)

        if (resolved := super()._resolve_type(python_type)) is not None:
            return resolved

        # avoid circular references
        seen_types.add(python_type)

        # default _resolve_type could only find concrete annotations
        # new implementation can deconstruct annotation

        if typing_extra.is_type_alias(python_type):
            return self._resolve_cascade(python_type.__value__, seen_types)

        if typing_extra.is_annotated(python_type):
            return self._resolve_cascade(get_args(python_type)[0], seen_types)

        if typing_extra.is_new_type(python_type):
            return self._resolve_cascade(python_type.__supertype__, seen_types)

        if typing_extra.is_generic_alias(python_type):
            return self._resolve_cascade(get_origin(python_type), seen_types)

        raise TypeLookupError("Unknown type")

    def _resolve_type(self, python_type: _MatchedOnType) -> TypeEngine[Any] | None:
        try:
            resolved = self._resolve_cascade(python_type, set())
        except TypeLookupError:
            return None
        if isinstance(resolved, _SpecialTyped) and resolved.impl is None:
            resolved.set_impl(self.json_type)
        return resolved


_String = String()
_Uuid = Uuid()
_Binary = LargeBinary()
_Numeric = Numeric()


def _decimal_type() -> TypeEngine[Any]:
    precision: int | None = None
    scale: int | None = None
    type_ = get_original_annotation()
    if typing_extra.is_annotated(type_):
        for metadata in type_.__metadata__:
            if hasattr(metadata, "max_digits"):
                precision = metadata.max_digits
            if hasattr(metadata, "decimal_places"):
                scale = metadata.decimal_places
    if precision is not None or scale is not None:
        return Numeric(
            precision=precision,
            scale=scale,
        )
    return _Numeric


def _special_typed(impl: TypeEngine[Any] | Callable[[], TypeEngine[Any]]) -> TypeEngine[Any]:
    return cast(TypeEngine[Any], functools.partial(_SpecialTyped, impl))


DEFAULT_TYPE_MAP = {
    # Standard types:
    int: _special_typed(Integer()),
    float: _special_typed(Float()),
    bool: _special_typed(Boolean()),
    uuid.UUID: _special_typed(Uuid()),
    datetime.date: _special_typed(Date()),
    datetime.datetime: _special_typed(DateTime()),
    datetime.time: _special_typed(Time()),
    datetime.timedelta: _special_typed(Interval()),
    bytes: _special_typed(LargeBinary()),
    str: _special_typed(_String),
    decimal.Decimal: _special_typed(_decimal_type),
    ipaddress.IPv4Address: InetType(ipaddress.IPv4Address),
    ipaddress.IPv6Address: InetType(ipaddress.IPv6Address),
    ipaddress.IPv4Network: CidrType(ipaddress.IPv4Network),
    ipaddress.IPv6Network: CidrType(ipaddress.IPv6Network),
    # Container types and Any is always JSON
    list: _SpecialTyped,
    tuple: _SpecialTyped,
    set: _SpecialTyped,
    frozenset: _SpecialTyped,
    dict: _SpecialTyped,
    collections.deque: _SpecialTyped,
    typing.Any: _SpecialTyped,
    collections.abc.MutableSet: _SpecialTyped,
    collections.abc.Mapping: _SpecialTyped,
    collections.abc.MutableMapping: _SpecialTyped,
    collections.abc.Sequence: _SpecialTyped,
    collections.abc.MutableSequence: _SpecialTyped,
    pydantic.BaseModel: _SpecialTyped,
    pathlib.Path: _special_typed(_String),
    re.Pattern: _special_typed(_String),
}
