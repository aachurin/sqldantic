from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import RootModel
from sqlalchemy import types
from sqlalchemy.sql.type_api import to_instance

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect


class PostponedAnnotation:
    __annotated: bool = False

    def provide_annotation(self, annotation: Any) -> None:
        if not self.__annotated:
            self.__annotated = True
            self.setup_annotation(annotation)

    def setup_annotation(self, annotation: Any) -> None:
        pass


class Typed(PostponedAnnotation, types.TypeDecorator):
    cache_ok = True
    root_model: type[RootModel]
    impl: types.TypeEngine[Any]

    # noinspection PyMissingConstructor
    def __init__(self, type_: type[types.TypeEngine[Any]] | types.TypeEngine[Any] = types.JSON, **kwargs: Any):
        self.impl = to_instance(type_, **kwargs)

    def setup_annotation(self, annotation: Any) -> None:
        self.root_model = RootModel[annotation]  # type:ignore

    def coerce_compared_value(self, op: Any, value: Any) -> types.TypeEngine[Any]:
        return self.impl.coerce_compared_value(op, value)

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return self.root_model(value).model_dump(mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return self.root_model(value).root
