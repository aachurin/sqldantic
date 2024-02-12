from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn, TypeVar

from pydantic import RootModel
from sqlalchemy import TypeDecorator, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction
from sqlalchemy.sql.type_api import to_instance
from sqlalchemy.types import JSON, Boolean, String, TypeEngine

from .typing_extra import make_annotated

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect


_T = TypeVar("_T", bound="Any")


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

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(INET())
        return dialect.type_descriptor(String())

    class Comparator(TypeEngine.Comparator[_T]):
        def is_contained_within(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

        def __rshift__(self, other: Any) -> Any:
            return func._inet__is_contained_within(self, other)

    comparator_factory = Comparator


class PostponedAnnotation:
    def provide_annotation(self, annotation: type[Any], *metadata: Any) -> None:
        raise NotImplementedError()


def raise_no_root_model(*args: Any, **kwargs: Any) -> NoReturn:
    raise TypeError("root_model was not provided")


class Typed(PostponedAnnotation, TypeDecorator):
    cache_ok = True
    root_model: type[RootModel]
    read_root_model: type[RootModel]
    impl: TypeEngine[Any]

    # noinspection PyMissingConstructor
    def __init__(
        self,
        impl: type[TypeEngine[Any]] | TypeEngine[Any] = JSON,
        root_model: type[RootModel] | None = None,
        **kwargs: Any,
    ):
        self.impl = to_instance(impl, **kwargs)
        assert (
            root_model is None or isinstance(root_model, type) and issubclass(root_model, RootModel)
        ), "type[RootModel] expected"
        self.read_root_model = self.root_model = root_model or raise_no_root_model  # type:ignore

    def provide_annotation(self, annotation: type[Any], *metadata: Any) -> None:
        if self.root_model is raise_no_root_model:
            self.root_model = RootModel[make_annotated(annotation, *metadata)]  # type:ignore
            self.read_root_model = RootModel[annotation]  # type:ignore

    def coerce_compared_value(self, op: Any, value: Any) -> TypeEngine[Any]:
        return self.impl.coerce_compared_value(op, value)

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return self.root_model(value).model_dump(mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return self.read_root_model(value).root
