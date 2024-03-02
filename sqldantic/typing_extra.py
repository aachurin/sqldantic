import re
import sys
from typing import Annotated, Any, get_args, get_origin

from pydantic._internal import _model_construction, _typing_extra, _utils
from pydantic._internal._typing_extra import is_annotated  # noqa
from pydantic.fields import FieldInfo
from sqlalchemy.orm.base import Mapped, _MappedAnnotationBase

from .field import _Meta, _Origin


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


def make_annotated(tp: type[Any] | str | None, *metadata: Any) -> type[Any] | str | None:
    if metadata:
        return Annotated[tp, *metadata]  # type:ignore
    return tp


# unwrap_annotated is reversed to make_annotated:
# unwrap_annotated(make_annotated(int, 1, 2)) == [int, 1, 2]
# make_annotated(*unwrap_annotated(Annotated[int, 1, 2])) == Annotated[int, 1, 2]
def unwrap_annotated(ann_type: Any) -> list[Any]:
    if is_annotated(ann_type):
        return list(get_args(ann_type))
    return [ann_type]


def unmapped_annotation(ann: Any, *, parent_depth: int) -> Any:
    if isinstance(ann, str):
        if m := re.match(r"^([a-zA-Z0-9_.\s]*)\[(.*)]$", ann.strip()):
            typename, args = m.groups()
            try:
                origin = eval(typename, *parent_namespaces(parent_depth=parent_depth + 1))
            except NameError:
                pass
            else:
                if _utils.lenient_issubclass(origin, _MappedAnnotationBase):
                    return make_annotated(args, _Origin(origin))
    elif _utils.lenient_issubclass(origin := get_origin(ann), _MappedAnnotationBase):
        return make_annotated(get_args(ann)[0], _Origin(origin))
    return ann


def mapped_from_field(field: FieldInfo) -> Any:
    origin = [meta for meta in field.metadata if isinstance(meta, _Origin)]
    mapped_class = origin[0].origin if origin else Mapped
    return mapped_class[annotation_from_field(field)]


def annotation_from_field(field: FieldInfo) -> Any:
    return make_annotated(
        field.annotation,
        *[meta for meta in field.metadata if not isinstance(meta, _Meta)],
    )
