import re
import sys

from pydantic._internal import _model_construction, _typing_extra, _utils
from pydantic.fields import FieldInfo
from sqlalchemy.orm.base import Mapped, _MappedAnnotationBase
from typing_extensions import (
    Annotated,
    Any,
    List,
    NewType,
    TypeAliasType,
    TypeGuard,
    get_args,
    get_origin,
)


class _Meta:
    __slots__ = ()


class _Origin(_Meta):
    __slots__ = ("origin",)

    def __init__(self, origin: Any):
        self.origin = origin

    def __repr__(self) -> str:
        return f"{self.origin.__name__}"


def is_new_type(type_: Any) -> TypeGuard[NewType]:
    return _typing_extra.is_new_type(type_)


def is_type_alias(type_: Any) -> TypeGuard[TypeAliasType]:
    return _typing_extra.origin_is_type_alias_type(type_)


def is_union(type_: Any) -> bool:
    return _typing_extra.origin_is_union(get_origin(type_))


def is_generic_alias(type_: Any) -> bool:
    return _typing_extra.is_generic_alias(type_)


SpecialGenericAlias = type(List)


def is_special_generic_alias(type_: Any) -> bool:
    return isinstance(type_, SpecialGenericAlias)


def is_annotated(type_: Any) -> bool:
    return _typing_extra.is_annotated(type_)


# def is_literal(type_: Any) -> bool:
#     return _typing_extra.is_literal_type(type_)


def pydantic_parent_frame_namespace(*, parent_depth: int) -> dict[str, Any] | None:
    return _model_construction.build_lenient_weakvaluedict(
        _typing_extra.parent_frame_namespace(parent_depth=parent_depth + 2)
    )


def parent_namespaces(*, parent_depth: int) -> tuple[dict[str, Any], dict[str, Any]]:
    frame = sys._getframe(parent_depth + 1)  # type:ignore
    return frame.f_globals, frame.f_locals


def parent_writable_namespace(*, parent_depth: int = 0) -> dict[str, Any] | None:
    frame = sys._getframe(parent_depth + 1)  # type:ignore
    if frame.f_globals is frame.f_locals:
        return frame.f_globals
    return None


def make_annotated(type_: type[Any] | str | None, *metadata: Any) -> type[Any] | str | None:
    if metadata:
        return Annotated.__class_getitem__((type_, *metadata))  # type:ignore
    return type_


# unwrap_annotated is reversed to make_annotated:
# unwrap_annotated(make_annotated(int, 1, 2)) == [int, 1, 2]
# make_annotated(*unwrap_annotated(Annotated[int, 1, 2])) == Annotated[int, 1, 2]
def unwrap_annotated(type_: Any) -> list[Any]:  # pragma: no cover
    if is_annotated(type_):
        return list(get_args(type_))
    return [type_]


def unmapped_annotation(type_: Any, *, parent_depth: int) -> Any:
    if isinstance(type_, str):
        if m := re.match(r"^([a-zA-Z0-9_.\s]*)\[(.*)]$", type_.strip()):
            typename, args = m.groups()
            try:
                origin = eval(typename, *parent_namespaces(parent_depth=parent_depth + 1))
            except NameError:  # pragma: no cover
                pass
            else:
                if _utils.lenient_issubclass(origin, _MappedAnnotationBase):
                    return make_annotated(args, _Origin(origin))
    elif _utils.lenient_issubclass(origin := get_origin(type_), _MappedAnnotationBase):
        return make_annotated(get_args(type_)[0], _Origin(origin))
    return type_


def mapped_from_field(field: FieldInfo) -> Any:
    origin = [meta for meta in field.metadata if isinstance(meta, _Origin)]
    mapped_class = origin[0].origin if origin else Mapped
    return mapped_class[annotation_from_field(field)]


def annotation_from_field(field: FieldInfo) -> Any:
    return make_annotated(
        field.annotation,
        *[meta for meta in field.metadata if not isinstance(meta, _Meta)],
    )


# For future use
# def simplify_annotation(type_: Any) -> Any:
#     if is_literal(type_):
#         return Any
#     if is_type_alias(type_):
#         return simplify_annotation(flatten_type_alias(type_))
#     if is_annotated(type_):
#         return simplify_annotation(get_args(type_)[0])
#     if is_new_type(type_):
#         return simplify_annotation(flatten_new_type(type_))
#     if is_union(type_):
#         args = get_args(type_)
#         simplified_args = [simplify_annotation(arg) for arg in args]
#         if args != simplified_args:
#             return Union.__getitem__(tuple(simplified_args))
#         return type_
#     if is_generic(type_):
#         args = get_args(type_)
#         simplified_args = [simplify_annotation(arg) for arg in args]
#         if args != simplified_args:
#             return get_origin(type_).__class_getitem__(tuple(simplified_args))
#         return type_
#     return type_
