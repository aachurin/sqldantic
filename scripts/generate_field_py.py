import builtins
import re
import sys
import textwrap
import types
from types import FunctionType
from typing import Any, Callable, NamedTuple

import pydantic
import sqlalchemy
from pydantic import Field
from sqlalchemy.orm import mapped_column, relationship


class ResolvedType(NamedTuple):
    typename: str
    import_name: str
    module_name: str


class AnnParser:
    special_types_mapping = {
        "Optional": "Optional",
        "Union": "Union",
        "Set": "set",
        "List": "list",
        "Tuple": "tuple",
        "Dict": "dict",
        "Type": "type",
    }

    def __init__(self, module_name: str, import_cache: dict[str, set[str]], ignore: set[str] | None = None) -> None:
        self.module_name = module_name
        self.import_cache = import_cache
        self.ignore = ignore or set()
        self.resolve_cache: dict[str, ResolvedType] = {}

    def parse(self, ann: str) -> str:
        result = self.normalize_ann(self.parse_ann(ann.strip()))
        if "None" not in result:
            result.append("None")
        return " | ".join(result)

    @staticmethod
    def normalize_ann(ann: list[str]) -> list[str]:
        result = []
        for elem in ann:
            if elem not in result:
                result.append(elem)
        if not result or "Any" in result:
            return ["Any"]
        return result

    def parse_ann(self, ann: str, ignored: bool = False) -> list[str]:
        rest = ann
        result = []
        while rest:
            elems, rest = self.parse_item(rest, ignored)
            result += elems
            if rest.startswith("|"):
                rest = rest[1:].strip()
                assert rest, f"Incorrect annotation {ann}"
        return result

    def parse_item(self, ann: str, ignored: bool) -> tuple[list[str], str]:
        typename, rest = re.match(r"^\s*([a-zA-Z0-9_.\s]*)(.*)$", ann).groups()
        typename = ".".join(x.strip() for x in typename.split("."))
        if typename:
            typename, import_name, module_name = self.resolve_typename(typename)
            if typename in self.ignore:
                ignored = True
            if module_name != "builtins" and not ignored:
                self.import_cache.setdefault(module_name, set()).add(import_name)

        rest = rest.strip()
        if rest.startswith("["):
            args = []
            items, rest = self.split_args(rest)
            for ann in items:
                if ann.startswith("'") or ann.startswith('"'):
                    args.append(ann)
                else:
                    args += self.parse_ann(ann, ignored)
        else:
            args = None

        if ignored:
            return [], rest
        assert args is not None or typename, f"Invalid annotation {ann}"
        if typename == "Union":
            return self.normalize_ann(args), rest
        if typename == "Optional":
            return self.normalize_ann(args + ["None"]), rest
        if typename and args:
            return [f"{typename}[{', '.join(args)}]"], rest
        if typename:
            return [typename], rest
        return [f"[{', '.join(args)}]"], rest

    @staticmethod
    def split_args(ann: str) -> tuple[list[str], str]:
        assert ann.startswith("[")
        result = []
        depth = 1
        collected = ""
        rest = ann[1:]
        while rest := rest.strip():
            m = re.match(r'^("(?:[^"\\]|\\.)*")()(.*)', rest)
            if not m:
                m = re.match(r"^('(?:[^'\\]|\\.)*')()(.*)", rest)
            if not m:
                m = re.match(r"^([^\[\],]*)([\[\],]?)(.*)$", rest)
            first, token, rest = m.groups()
            collected += first.strip()
            if token == "[":
                depth += 1
            elif token == "]":
                depth -= 1
                if depth == 0:
                    if collected:
                        result.append(collected)
                    break
            elif token == ",":
                if depth == 1:
                    assert collected, f"Invalid annotation {ann}"
                    result.append(collected)
                    collected = ""
                    continue
                token = ", "
            collected += token
        assert depth == 0, f"Invalid annotation {ann}"
        return result, rest.strip()

    @staticmethod
    def get_module(module_name: str) -> types.ModuleType:
        return sys.modules[module_name]

    def resolve_typename(self, typename: str) -> ResolvedType:
        assert typename
        if typename not in self.resolve_cache:
            self.resolve_cache[typename] = self.resolve_typename_impl(typename)
        return self.resolve_cache[typename]

    def resolve_typename_impl(self, typename: str) -> ResolvedType:
        if typename in builtins.__dict__:
            return ResolvedType(typename, typename, "builtins")
        else:
            module_name = self.module_name
            traversal = typename.split(".")
            for idx, import_name in enumerate(traversal):
                try:
                    obj = getattr(self.get_module(module_name), import_name)
                except AttributeError:
                    # missing object due to TYPE_CHECKING import only
                    resolved_typename = ".".join(traversal[idx:])
                    break
                if isinstance(obj, types.ModuleType):
                    module_name = obj.__name__
                else:
                    resolved_typename = ".".join(traversal[idx:])
                    if obj in self.get_module(obj.__module__).__dict__.values():
                        module_name = obj.__module__
                    break
            else:
                raise TypeError(f"Could not find type {typename!r} - it's module")
        if resolved_typename in self.special_types_mapping:
            return ResolvedType(self.special_types_mapping[resolved_typename], import_name, "builtins")
        return ResolvedType(resolved_typename, import_name, module_name)


TEMPLATE = """\
# auto-generated module (pydantic = "^{pydantic_version}", sqlalchemy = "^{sqlalchemy_version}")

from __future__ import annotations

from typing import TYPE_CHECKING, cast, ClassVar, Callable
from pydantic.fields import FieldInfo, _Unset
from sqlalchemy.orm import MappedColumn as _MappedColumn, mapped_column, relationship
from sqlalchemy.orm.relationships import Relationship as _Relationship

if TYPE_CHECKING:
    {type_checking_imports}
    

class _Marker:
    __slots__ = ()


class _MappedTypeMarker(_Marker):
    __slots__ = ("type", )
    
    def __init__(self, type_: Any):
        self.type = type_
        
    def __repr__(self) -> str:
        return f"Marker({{self.type.__name__}})"


class _MappedMetaMarker(_Marker):
    __slots__ = ()
    attributes: ClassVar[frozenset[str]]
    constructor: ClassVar[Callable]
    
    @classmethod
    def construct(cls, field: FieldInfo) -> Any:
        kwargs = {{k: v for k, v in field._attributes_set.items() if k in cls.attributes}}
        extra_kwargs = kwargs.pop("_kwargs", None)
        if kwargs or extra_kwargs:
            return cls.constructor(**kwargs, **(extra_kwargs or {{}}))  # type:ignore
        return None
        
    def __repr__(self) -> str:
        return f"Marker({{self.constructor.__name__}})"
        
        
class __MappedColumnMarker(_MappedMetaMarker):
    __slots__ = ()
    attributes = frozenset((
        {field_info_attrs}
    ))
    constructor = mapped_column
    

class __RelationshipMarker(_MappedMetaMarker):
    __slots__ = ()
    attributes = frozenset((
        {relationship_info_attrs}
    ))
    constructor = relationship


_MappedColumnMarker = __MappedColumnMarker()
_RelationshipMarker = __RelationshipMarker()


def Field(
    {field_args}
) -> _MappedColumn:
    _kwargs = _kwargs or _Unset  # type:ignore
    _marker = _MappedColumnMarker
    __rv = FieldInfo(**locals())
    __rv.metadata.append(_marker)
    return cast(_MappedColumn, __rv)


def Relationship(
    {relationship_args}
) -> _Relationship[Any]:
    _kwargs = _kwargs or _Unset  # type:ignore
    _marker = _RelationshipMarker
    __rv = FieldInfo(**locals())
    __rv.metadata.append(_marker)
    return cast(_Relationship, __rv)
"""


def generate_field_py() -> None:
    imports = {}
    sqlalchemy_field_args = get_function_args(
        mapped_column,
        ignored={"_NoArg"},
        excluded=[
            "__name_pos",  # must use name instead
            "type_",  # XXX: most likely we don’t need type_
            "args",  # unused in sqlalchemy
            "default",  # used by pydantic
            "default_factory",  # used by pydantic
            "kw",  # dataclasses is not supported
            "init",  # dataclasses is not supported
            "repr",  # dataclasses is not supported
            "compare",  # dataclasses is not supported
            "kw_only",  # dataclasses is not supported
        ],
        imports=imports,
    )
    sqlalchemy_relationship_args = get_function_args(
        relationship,
        ignored={"_NoArg"},
        excluded=[
            "default",  # used by pydantic
            "default_factory",  # used by pydantic
            "kw",  # dataclasses is not supported
            "init",  # dataclasses is not supported
            "repr",  # dataclasses is not supported
            "compare",  # dataclasses is not supported
            "kw_only",  # dataclasses is not supported
        ],
        imports=imports,
    )
    pydantic_field_args = get_function_args(
        Field,
        excluded=[
            "repr",  # dataclasses is not supported
            "kw_only",  # dataclasses is not supported
            "validation_alias",  # too much aliases
            "serialization_alias",  # too much aliases
        ],
        overrides={
            "extra": "dict[str, Any]",
        },
        imports=imports,
    )

    for k, v in pydantic_field_args.items():
        assert k not in sqlalchemy_field_args, f"Duplicate {k} in {pydantic_field_args}"
    for k, v in pydantic_field_args.items():
        assert k not in sqlalchemy_relationship_args, f"Duplicate {k} in {pydantic_field_args}"

    field_info_attrs = list(sqlalchemy_field_args.keys()) + ["_kwargs"]
    field_info_attrs = [f"{attr!r}," for attr in field_info_attrs]
    sqlalchemy_field_args.update(pydantic_field_args)
    sqlalchemy_field_args["**_kwargs"] = "Any"
    field_args = [
        f"__type_pos: {sqlalchemy_field_args.pop('__type_pos')},",
        "*,",
    ] + [f"{x}: {y}," for x, y in sqlalchemy_field_args.items()]

    relationship_info_attrs = list(sqlalchemy_relationship_args.keys()) + ["_kwargs"]
    relationship_info_attrs = [f"{attr!r}," for attr in relationship_info_attrs]
    sqlalchemy_relationship_args.update(pydantic_field_args)
    sqlalchemy_relationship_args["**_kwargs"] = "Any"
    relationship_args = [
        f"argument: {sqlalchemy_relationship_args.pop('argument')},",
        f"secondary: {sqlalchemy_relationship_args.pop('secondary')},",
        "*,",
    ] + [f"{x}: {y}," for x, y in sqlalchemy_relationship_args.items()]

    if "typing" in imports:
        if "Callable" in imports["typing"]:
            imports["typing"].remove("Callable")

    type_checking_imports = [f"from {imp} import {name}" for imp, names in imports.items() for name in names]

    def indent(lines: list[str], spaces: int) -> str:
        return textwrap.indent("\n".join(lines), " " * spaces).strip()

    print(
        TEMPLATE.format(
            pydantic_version=pydantic.VERSION,
            sqlalchemy_version=sqlalchemy.__version__,
            field_args=indent(field_args, 4),
            field_info_attrs=indent(field_info_attrs, 8),
            relationship_args=indent(relationship_args, 4),
            relationship_info_attrs=indent(relationship_info_attrs, 8),
            type_checking_imports=indent(type_checking_imports, 4),
        ).strip()
    )


def get_function_args(
    func: Any,
    *,
    imports: dict[str, set[str]],
    excluded: list[str] | None = None,
    overrides: dict[str, Callable[[str], str] | str] | None = None,
    ignored: set[str] | None = None,
) -> dict[str, Any]:
    result = {}
    annotations = {**func.__annotations__}
    excluded = excluded or []
    excluded.append("return")
    for arg in excluded:
        del annotations[arg]
    if overrides:
        for key, callback in overrides.items():
            if key in annotations:
                annotations[key] = callback(annotations[key]) if callable(callback) else callback
    parser = AnnParser(func.__module__, imports, ignored)
    for arg, ann in annotations.items():
        ann = parser.parse(ann)
        result[arg] = f"{ann} = _Unset"
    return result


if __name__ == "__main__":
    generate_field_py()
