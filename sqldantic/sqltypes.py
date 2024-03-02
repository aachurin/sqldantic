from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn, TypeVar

from pydantic import RootModel
from sqlalchemy import String, TypeDecorator, func
from sqlalchemy.dialects.postgresql import CIDR, INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.sql.type_api import to_instance
from sqlalchemy.types import JSON, Boolean, TypeEngine

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect


_T = TypeVar("_T", bound="Any")


class PostponedAnnotation:
    def provide_annotation(self, ann_type: Any) -> None:
        raise NotImplementedError()


def raise_no_root_model(*_: Any, **__: Any) -> NoReturn:
    raise TypeError("root_model was not provided")


class Typed(PostponedAnnotation, TypeDecorator):
    cache_ok = True
    root_model: type[RootModel]
    impl: TypeEngine[Any]

    # noinspection PyMissingConstructor
    def __init__(
        self,
        impl: type[TypeEngine[Any]] | TypeEngine[Any] = JSON,
        root_model: type[RootModel] | None = None,  # is used for cache
        *,
        ann_type: type[Any] | None = None,
        **kwargs: Any,
    ):
        assert (
            root_model is None or ann_type is None
        ), "`root_model` and `annotation` are mutually exclusive"
        assert (
            root_model is None or isinstance(root_model, type) and issubclass(root_model, RootModel)
        ), "type[RootModel] expected"
        self.impl = to_instance(impl, **kwargs)
        if ann_type is not None:
            self.root_model = RootModel[ann_type]  # type:ignore
        else:
            self.root_model = root_model or raise_no_root_model  # type:ignore

    def provide_annotation(self, ann_type: Any) -> None:
        if self.root_model is raise_no_root_model:
            self.root_model = RootModel[ann_type]  # type:ignore

    def coerce_compared_value(self, op: Any, value: Any) -> TypeEngine[Any]:
        return self.impl.coerce_compared_value(op, value)

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return self.root_model(value).model_dump(mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return self.root_model(value).root


class InetIsContainedWithin(GenericFunction):
    inherit_cache = True
    name = "_inet__is_contained_within"
    type = Boolean()


@compiles(InetIsContainedWithin, "postgresql")
def __(element: Any, compiler: Any, **kw: Any) -> str:
    left, right = element.clauses
    return f"{compiler.process(left, **kw)} <<= {compiler.process(right, **kw)}"


class InetType(TypeDecorator):
    impl = INET
    cache_ok = True

    def __init__(self, type_: Any):
        super().__init__()
        self.type_ = type_

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            # psycopg3 (aka psycopg) can work with ipaddress types from the box
            return dialect.type_descriptor(INET())
        return dialect.type_descriptor(Typed(String(), ann_type=self.type_))

    class Comparator(TypeEngine.Comparator[_T]):
        def is_contained_within(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

        def __rshift__(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

    comparator_factory = Comparator


class CidrContains(GenericFunction):
    inherit_cache = True
    name = "_cidr__contains"
    type = Boolean()


@compiles(CidrContains, "postgresql")  # type: ignore[no-redef]
def __(element: Any, compiler: Any, **kw: Any) -> str:
    left, right = element.clauses
    return f"{compiler.process(left, **kw)} >>= {compiler.process(right, **kw)}"


class CidrType(TypeDecorator):
    impl = CIDR
    cache_ok = True

    def __init__(self, type_: Any):
        super().__init__()
        self.type_ = type_

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(CIDR())
        return dialect.type_descriptor(Typed(String(), ann_type=self.type_))

    class Comparator(TypeEngine.Comparator[_T]):
        def is_contained_within(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

        def __rshift__(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

        def contains(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

        def __lshift__(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

    comparator_factory = Comparator
