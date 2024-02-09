from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from pydantic import RootModel
from pydantic._internal import _typing_extra
from sqlalchemy import types
from sqlalchemy.sql.type_api import to_instance

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect


class PostponedAnnotation:
    def provide_annotation(self, annotation: Any) -> None:
        raise NotImplementedError()


def raise_no_root_model(*args: Any, **kwargs: Any) -> NoReturn:
    raise TypeError("root_model was not provided")


class Typed(PostponedAnnotation, types.TypeDecorator):
    cache_ok = True
    root_model: type[RootModel]
    read_root_model: type[RootModel]
    impl: types.TypeEngine[Any]

    # noinspection PyMissingConstructor
    def __init__(
        self,
        impl: type[types.TypeEngine[Any]] | types.TypeEngine[Any] = types.JSON,
        root_model: type[RootModel] | None = None,
        **kwargs: Any,
    ):
        self.impl = to_instance(impl, **kwargs)
        assert (
            root_model is None or isinstance(root_model, type) and issubclass(root_model, RootModel)
        ), "type[RootModel] expected"
        self.read_root_model = self.root_model = root_model or raise_no_root_model  # type:ignore

    def provide_annotation(self, annotation: Any) -> None:
        if self.root_model is raise_no_root_model:
            self.root_model = RootModel[annotation]  # type:ignore
            self.read_root_model = RootModel[  # type:ignore
                annotation.__args__[0] if _typing_extra.is_annotated(annotation) else annotation
            ]

    def coerce_compared_value(self, op: Any, value: Any) -> types.TypeEngine[Any]:
        return self.impl.coerce_compared_value(op, value)

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        return self.root_model(value).model_dump(mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return self.read_root_model(value).root
