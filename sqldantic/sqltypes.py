from __future__ import annotations

import datetime
import decimal
import uuid
from ipaddress import IPv4Address, IPv4Interface, IPv4Network, IPv6Address, IPv6Interface, IPv6Network
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from pydantic import RootModel
from sqlalchemy import Boolean, String, TypeDecorator, func
from sqlalchemy.dialects.postgresql import CIDR, INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.sql.sqltypes import NullType
from sqlalchemy.sql.type_api import to_instance
from sqlalchemy.types import TypeEngine

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.engine.interfaces import Dialect
    from sqlalchemy.sql.type_api import _MatchedOnType


BUILTIN_TYPES = (
    int,
    float,
    bool,
    uuid.UUID,
    datetime.date,
    datetime.datetime,
    datetime.time,
    datetime.timedelta,
    bytes,
    str,
    decimal.Decimal,
)


_Untyped = NullType()


class _SpecialTyped(TypeDecorator):
    cache_ok = True
    impl: TypeEngine[Any] | type[TypeEngine[Any]]
    annotation: type[RootModel]

    def __init__(
        self,
        impl: type[TypeEngine[Any]] | TypeEngine[Any] | None = None,
        annotation: Any | None = None,
        **kwargs: Any,
    ):
        if impl:
            self.set_impl(impl, **kwargs)
        else:
            self.impl = cast(TypeEngine, impl)
        if annotation is not None:
            self.set_annotation(annotation)
        else:
            self.annotation = None  # type:ignore

    def set_impl(self, impl: TypeEngine[Any] | type[TypeEngine[Any]], **kwargs: Any) -> None:
        self.impl = to_instance(impl, **kwargs)

    def set_annotation(self, type_: Any) -> None:
        self.annotation = RootModel[type_]  # type:ignore

    def _resolve_for_python_type(
        self,
        python_type: type[Any],
        matched_on: _MatchedOnType,
        matched_on_flattened: type[Any],
    ) -> Self | None:
        if (
            python_type is matched_on_flattened
            and python_type in BUILTIN_TYPES
            and self.impl is not None
        ):
            return self.impl  # type:ignore
        return self

    def coerce_compared_value(self, op: Any, value: Any) -> TypeEngine[Any]:  # pragma: no cover
        return self.impl.coerce_compared_value(op, value)  # type:ignore[call-arg]

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return self.annotation(value).model_dump(mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        # XXX: want load in "safe-error" mode
        # the problem in BaseModel types, need to safety reconstruct them
        return self.annotation(value).root


def Typed(impl: type[TypeEngine[Any]] | TypeEngine[Any] | None = None) -> TypeEngine[Any]:
    assert impl is None or not isinstance(impl, NullType)
    if impl is not None:
        return _SpecialTyped(impl)
    else:
        return _Untyped


_Boolean = Boolean()


class InetIsContainedWithin(GenericFunction):
    inherit_cache = True
    name = "_inet__is_contained_within"
    type = _Boolean


@compiles(InetIsContainedWithin, "postgresql")
def __(element: Any, compiler: Any, **kw: Any) -> str:
    left, right = element.clauses
    return f"{compiler.process(left, **kw)} << {compiler.process(right, **kw)}"


class InetIsContainedWithinOrEqual(GenericFunction):
    inherit_cache = True
    name = "_inet__is_contained_within_or_equal"
    type = _Boolean


@compiles(InetIsContainedWithinOrEqual, "postgresql")  # type:ignore[no-redef]
def __(element: Any, compiler: Any, **kw: Any) -> str:
    left, right = element.clauses
    return f"{compiler.process(left, **kw)} <<= {compiler.process(right, **kw)}"


class InetIsContains(GenericFunction):
    inherit_cache = True
    name = "_inet__is_contains"
    type = _Boolean


@compiles(InetIsContains, "postgresql")  # type:ignore[no-redef]
def __(element: Any, compiler: Any, **kw: Any) -> str:
    left, right = element.clauses
    return f"{compiler.process(left, **kw)} >> {compiler.process(right, **kw)}"


class InetIsContainsOrEqual(GenericFunction):
    inherit_cache = True
    name = "_inet__is_contains_or_equal"
    type = _Boolean


@compiles(InetIsContainsOrEqual, "postgresql")  # type:ignore[no-redef]
def __(element: Any, compiler: Any, **kw: Any) -> str:
    left, right = element.clauses
    return f"{compiler.process(left, **kw)} >>= {compiler.process(right, **kw)}"


_T = TypeVar("_T", bound="Any")
_String = String()
_Inet = INET()
_Cidr = CIDR()


class InetType(TypeDecorator):
    impl: TypeEngine[Any] | type[TypeEngine[Any]] = _Inet
    cache_ok = True
    type_: type[Any]

    def __init__(self, type_: type[IPv4Address | IPv4Interface | IPv6Address | IPv6Interface]):
        self.type_ = type_

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            # psycopg3 (aka psycopg) can work with ipaddress types from the box
            return dialect.type_descriptor(self.impl_instance)
        return dialect.type_descriptor(_SpecialTyped(_String, self.type_))

    class Comparator(TypeEngine.Comparator[_T]):
        def is_contained_within(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

        def is_contained_within_or_equal(self, other: Any) -> Any:
            return func._inet__is_contained_within_or_equal(self, other)

        def is_contains(self, other: Any) -> Any:
            return func._inet__is_contains(self, other)

        def is_contains_or_equal(self, other: Any) -> Any:
            return func._inet__is_contains_or_equal(self, other)

        def __lshift__(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

        def __rshift__(self, other: Any) -> Any:
            return func._inet__is_contains(self, other)

    comparator_factory = Comparator


class CidrType(InetType):
    cache_ok = True
    impl = _Cidr

    def __init__(self, type_: type[IPv4Network | IPv6Network]):
        self.type_ = type_
