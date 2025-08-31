import re
from typing import List, Optional, Union, Dict, Set

from dataclasses import replace

from .data import *


def get_system_include_regexes() -> List[str]:
    """
    Returns a list of regex patterns that match system include directories.
    Includes common Windows and Unix/GCC/Clang paths.
    """
    return [
        r"builtin",
        r".*\\Program Files\\.*",  # VS STL, Windows SDK
        r".*\\Microsoft Visual Studio\\.*",
        r".*\\Windows Kits\\.*",
        r".*\\vcpkg\\installed\\.*?\\include\\.*",
        r".*/Program Files/.*",  # VS STL, Windows SDK
        r".*/Microsoft Visual Studio/.*",
        r".*/Windows Kits/.*",
        r".*/vcpkg/installed/.*?/include/.*",  # linux
        r"^<builtin>",
        r"^/usr/include/",
        r"^/usr/local/include/",
        r"^/usr/lib/clang/.*/include/",
        r"/clang/include/",
        r"/x86_64-linux-gnu/",
        r"^/opt/",
    ]


def filter_by_source_regexes(
    definitions: List[DefinitionBase],
    include: Optional[Union[str, List[str]]] = None,
    exclude: Optional[Union[str, List[str]]] = None,
) -> List[DefinitionBase]:
    """
    Filters definitions based on regexes matching their `source` field.

    - `include`: pattern or list of patterns. If provided, only matching sources are kept.
    - `exclude`: pattern or list of patterns. If provided, matching sources are removed.
    """
    if isinstance(include, str):
        include = [include]
    if isinstance(exclude, str):
        exclude = [exclude]

    include_patterns = [re.compile(p) for p in include] if include else []
    exclude_patterns = [re.compile(p) for p in exclude] if exclude else []

    def should_keep(defn: DefinitionBase) -> bool:
        if include_patterns:
            return any(p.search(defn.source) for p in include_patterns)
        if exclude_patterns:
            return not any(p.search(defn.source) for p in exclude_patterns)
        return True

    return [d for d in definitions if should_keep(d)]


def fill_bitfield_holes_with_padding(definitions):
    """
    Returns a new list of definitions where each struct/union has bitfield holes
    filled with synthetic __padN fields.
    """
    pad_counter = 0
    updated = []

    for d in definitions:
        if not isinstance(d, (ClassDefinition, UnionDefinition)):
            updated.append(d)
            continue

        if not d.fields:
            updated.append(d)
            continue

        new_fields = []
        prev_end = 0

        for f in sorted(d.fields, key=lambda f: f.bitoffset):
            if f.bitoffset > prev_end:
                pad_size = f.bitoffset - prev_end
                pad_field = Field(
                    name=f"__pad{pad_counter}",
                    type=TypeBase(name="uint8_t"),
                    elements=(),
                    bitoffset=prev_end,
                    size_in_bits=pad_size,
                    bitfield=True,
                )
                new_fields.append(pad_field)
                pad_counter += 1
            new_fields.append(f)
            prev_end = max(prev_end, f.bitoffset + f.size_in_bits)

        struct_end = d.size * 8
        if prev_end < struct_end:
            pad_size = struct_end - prev_end
            new_fields.append(
                Field(
                    name=f"__pad{pad_counter}",
                    type=TypeBase(name="uint8_t"),
                    elements=(),
                    bitoffset=prev_end,
                    size_in_bits=pad_size,
                    bitfield=True,
                )
            )
            pad_counter += 1

        # Create a new instance with updated fields
        updated.append(replace(d, fields=tuple(new_fields)))

    return updated


def fill_struct_holes_with_padding_bytes(definitions):
    """
    Returns new definitions list with hole-filling padding fields of type 'uint8_t',
    inserted as scalars or arrays depending on size.
    """
    result = []
    pad_counter = 0

    for d in definitions:
        if not isinstance(d, (ClassDefinition, UnionDefinition)):
            result.append(d)
            continue

        if not d.fields:
            result.append(d)
            continue

        new_fields = []
        prev_end = 0

        for field in sorted(d.fields, key=lambda f: f.bitoffset):
            count = 1
            for dim in field.elements:
                count *= dim
            field_size = field.size_in_bits * count
            start = field.bitoffset

            if start > prev_end:
                hole_size = start - prev_end
                byte_count = hole_size // 8
                if hole_size % 8 != 0:
                    raise ValueError(
                        f"Cannot pad non-byte-aligned hole of size {hole_size} bits"
                    )

                pad_field = Field(
                    name=f"__pad{pad_counter}",
                    type=TypeBase(name="uint8_t"),
                    elements=(byte_count,) if byte_count > 1 else (),
                    bitoffset=prev_end,
                    size_in_bits=hole_size,
                    bitfield=False,
                )
                new_fields.append(pad_field)
                pad_counter += 1

            new_fields.append(field)
            prev_end = max(prev_end, start + field_size)

        struct_end = d.size * 8
        if prev_end < struct_end:
            hole_size = struct_end - prev_end
            byte_count = hole_size // 8
            if hole_size % 8 != 0:
                raise ValueError(f"Trailing hole not byte-aligned ({hole_size} bits)")
            pad_field = Field(
                name=f"__pad{pad_counter}",
                type=TypeBase(name="uint8_t"),
                elements=(byte_count,) if byte_count > 1 else (),
                bitoffset=prev_end,
                size_in_bits=hole_size,
                bitfield=False,
            )
            new_fields.append(pad_field)

        result.append(replace(d, fields=tuple(new_fields)))

    return result


from collections import defaultdict
from dataclasses import replace
from dataclasses import replace
from typing import List


def flatten_namespaces(definitions: List[TypeBase]) -> List[TypeBase]:
    """
    Returns a new list of definitions with flattened names (namespace removed),
    and the namespace path added to the name using '__' separator.
    """
    flattened = []

    for d in definitions:
        if hasattr(d, "namespace") and d.namespace:
            prefix = "__".join(d.namespace)
            new_name = f"{prefix}__{d.name}"
        else:
            new_name = d.name
        flattened.append(replace(d, name=new_name, namespace=()))

    return flattened


def resolve_typedefs(definitions):
    """
    Returns a new list of definitions where all TypedefDefinitions are removed,
    and all references to them are replaced with their underlying types.

    Supports nested typedefs and typedefs of arrays.
    """
    typedef_map = {
        td.name: td for td in definitions if isinstance(td, TypedefDefinition)
    }

    def resolve_type(
        typ: TypeBase, elements: Tuple[int] = ()
    ) -> Tuple[TypeBase, Tuple[int]]:
        seen = set()
        while typ.name in typedef_map:
            if typ.name in seen:
                raise ValueError(f"Recursive typedef detected: {typ.name}")
            seen.add(typ.name)
            td = typedef_map[typ.name]
            typ = td.type
            elements = td.elements + elements  # prepend typedef array dims
        return typ, elements

    def update_field(field: Field) -> Field:
        new_type, new_elements = resolve_type(field.type, field.elements)
        return replace(field, type=new_type, elements=new_elements)

    updated = []
    for d in definitions:
        if isinstance(d, TypedefDefinition):
            continue  # remove it
        elif isinstance(d, (ClassDefinition, UnionDefinition)):
            new_fields = tuple(update_field(f) for f in d.fields)
            updated.append(replace(d, fields=new_fields))
        elif isinstance(d, ConstantDefinition):
            new_type, _ = resolve_type(d.type)
            updated.append(replace(d, type=new_type))
        else:
            updated.append(d)

    return updated


def build_type_dependency_graph(definitions: List[TypeBase]) -> Dict[str, Set[str]]:
    """
    Builds a graph where each node is a type name, and edges point to types it depends on.
    """
    graph = defaultdict(set)

    for d in definitions:
        dname = d.fullname
        if isinstance(d, (ClassDefinition, UnionDefinition)):
            for field in d.fields:
                graph[dname].add(field.type.fullname)
        elif isinstance(d, TypedefDefinition):
            graph[dname].add(d.type.fullname)
        elif isinstance(d, ConstantDefinition):
            graph[dname].add(d.type.fullname)

        # ensure all nodes exist in the graph even if they have no dependencies
        if dname not in graph:
            graph[dname] = set()

    return graph


def sort_definitions_topologically(definitions: List[TypeBase]) -> List[TypeBase]:
    """
    Reorders the definitions so all dependencies are defined before use.
    """
    graph = build_type_dependency_graph(definitions)
    name_to_def = {d.fullname: d for d in definitions}
    visited = {}
    result = []

    def visit(node):
        if visited.get(node) == "visiting":
            raise ValueError(f"Cyclic dependency detected at {node}")
        if visited.get(node) == "visited":
            return

        visited[node] = "visiting"
        for dep in graph[node]:
            if dep in graph:  # ignore built-in types
                visit(dep)
        visited[node] = "visited"
        if node in name_to_def:
            result.append(name_to_def[node])

    for name in graph:
        visit(name)

    return result


def filter_connected_definitions(
    definitions: List[TypeBase], roots: Union[str, List[str]]
) -> List[TypeBase]:
    """
    Filters the definitions list to include only those reachable from the given root type(s),
    based on field, typedef, or constant dependencies.
    """
    if isinstance(roots, str):
        roots = [roots]

    graph = build_type_dependency_graph(definitions)
    name_to_def = {d.fullname: d for d in definitions}
    visited = set()
    stack = list(roots)

    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(graph.get(current, []))

    return [d for d in definitions if d.fullname in visited]
