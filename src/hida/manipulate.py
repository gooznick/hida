import re
from typing import List, Optional, Union, Dict, Set, Iterable, Tuple, Sequence
from pathlib import PurePath
from collections import defaultdict
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


def filter_by_name_regexes(
    definitions: List[DefinitionBase],
    include: Optional[Union[str, Iterable[str]]] = None,
    exclude: Optional[Union[str, Iterable[str]]] = None,
    *,
    use_fullname: bool = False,
    flags: int = 0,  # e.g., re.IGNORECASE
) -> List[DefinitionBase]:
    """
    Filters definitions based on regexes matching their name.

    - `include`: pattern or list of patterns. If provided, only matching names are kept.
    - `exclude`: pattern or list of patterns. If provided, matching names are removed.
    - `use_fullname`: if True, match against `defn.fullname` when available; otherwise `defn.name`.
    - `flags`: regex flags (e.g., re.IGNORECASE).

    Semantics mirror `filter_by_source_regexes`.
    """

    def _as_list(x: Optional[Union[str, Iterable[str]]]) -> List[str]:
        if x is None:
            return []
        if isinstance(x, str):
            return [x]
        return list(x)

    include_patterns = [re.compile(p, flags) for p in _as_list(include)]
    exclude_patterns = [re.compile(p, flags) for p in _as_list(exclude)]

    def _key(defn: DefinitionBase) -> str:
        # Prefer fullname if requested and present; fall back to name; then empty string.
        if use_fullname and hasattr(defn, "fullname") and defn.fullname is not None:
            return str(defn.fullname)
        return str(getattr(defn, "name", "") or "")

    def should_keep(defn: DefinitionBase) -> bool:
        name = _key(defn)
        if include_patterns:
            return any(p.search(name) for p in include_patterns)
        if exclude_patterns:
            return not any(p.search(name) for p in exclude_patterns)
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



def _flattened_name(ns: Sequence[str], name: str, sep: str = "__") -> str:
    parts = list(ns or ())
    return (sep.join(parts) + sep + name) if parts else name

def _flatten_type(t: TypeBase, sep: str) -> TypeBase:
    """Return a copy of t with namespace folded into name and namespace cleared."""
    return replace(t, name=_flattened_name(t.namespace, t.name, sep), namespace=())

def flatten_namespaces(definitions: List[TypeBase], sep: str = "__") -> List[TypeBase]:
    """
    Walk the list and return new items whose `name` includes the namespace
    (joined by `sep`) and whose `namespace` is cleared.

    Also rewrites any *embedded type references* (fields / typedef / constant)
    by producing flattened copies of those types on the fly.
    No global mapping is used.
    """
    out: List[TypeBase] = []

    for d in definitions:
        # Start with a flattened copy of the definition itself
        nd = replace(d, name=_flattened_name(d.namespace, d.name, sep), namespace=())

        # Fix embedded references per kind
        if isinstance(nd, (ClassDefinition, UnionDefinition)) and d.fields:
            new_fields = tuple(
                replace(f, type=_flatten_type(f.type, sep)) for f in d.fields
            )
            nd = replace(nd, fields=new_fields)

        elif isinstance(nd, TypedefDefinition):
            nd = replace(nd, type=_flatten_type(d.type, sep))

        elif isinstance(nd, ConstantDefinition):
            nd = replace(nd, type=_flatten_type(d.type, sep))

        # EnumDefinition has no embedded type references to adjust

        out.append(nd)

    return out




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
    visited = set()
    stack = list(roots)
    if not any([graph.get(v, None) for v in stack]):
        raise RuntimeError(f"Could not find any known struct in roots {roots}")
    
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(graph.get(current, []))

    return [d for d in definitions if d.fullname in visited]


def flatten_structs(
    definitions: List[TypeBase],
    targets: Union[str, List[str]],
    *,
    separator: str = "__",
    flatten_arrays: bool = False,
) -> List[TypeBase]:
    """
    For each target struct/union, inline fields of nested struct/union members into
    the parent so the result is 'flat'. Names are prefixed with the containing field
    name and `separator`.

    Arrays of nested structs/unions are:
      - kept intact by default
      - unrolled at ANY depth if `flatten_arrays=True`

    Example: parent.field (struct S) with S.a, S.b  ->  parent.field__a, parent.field__b
    For arrays (when flatten_arrays=True): parent.arr[2] (struct S) -> parent.arr_0___a, parent.arr_1___a, ...
    """
    if isinstance(targets, str):
        targets = [targets]

    # Resolve fullnames and quick lookup
    defs_by_fullname: Dict[str, TypeBase] = {d.fullname: d for d in definitions}
    names = set(targets)
    targets_full: Set[str] = {
        d.fullname
        for d in definitions
        if isinstance(d, (ClassDefinition, UnionDefinition))
        and (d.name in names or d.fullname in names)
    }

    def is_composite(fullname: str) -> bool:
        d = defs_by_fullname.get(fullname)
        return isinstance(d, (ClassDefinition, UnionDefinition))

    def flatten_fields(parent_base_bits: int, prefix: str, f: Field) -> Iterable[Field]:
        """
        Yield flattened fields for a single (possibly composite/array) field `f`, using
        `parent_base_bits` as the bit base and `prefix` as the full name prefix that
        must be preserved across recursion.
        """
        ref = defs_by_fullname.get(f.type.fullname)
        if not isinstance(ref, (ClassDefinition, UnionDefinition)):
            # Leaf (non-composite): keep, but apply prefix and adjusted offsets.
            new_name = prefix or f.name
            yield replace(f, name=new_name, bitoffset=parent_base_bits + f.bitoffset)
            return

        # Helper to emit subfields of the composite `ref` for a specific element base
        def emit_subfields(name_prefix: str, elem_bit_base: int):
            base_name = name_prefix  # the accumulated name prefix
            base_off = parent_base_bits + f.bitoffset + elem_bit_base
            for sf in sorted(ref.fields, key=lambda x: x.bitoffset):
                sf_ref = defs_by_fullname.get(sf.type.fullname)
                sf_is_comp = isinstance(sf_ref, (ClassDefinition, UnionDefinition))

                if sf_is_comp:
                    if sf.elements:
                        # Inner array of composites
                        if not flatten_arrays:
                            # Keep the array as-is
                            yield replace(
                                sf,
                                name=f"{base_name}{separator}{sf.name}",
                                bitoffset=base_off + sf.bitoffset,
                            )
                        else:
                            # Unroll inner composite array
                            from itertools import product

                            dims: List[int] = list(sf.elements)
                            elem_stride_bits2 = sf_ref.size * 8

                            def linear_index(idxs: Tuple[int, ...], dims: List[int]) -> int:
                                stride = 1
                                idx = 0
                                for i, d in zip(reversed(idxs), reversed(dims)):
                                    idx += i * stride
                                    stride *= d
                                return idx

                            for idxs in product(*[range(d) for d in dims]):
                                lin = linear_index(idxs, dims)
                                elem_base2 = lin * elem_stride_bits2
                                idx_suffix = "".join(f"_{i}_" for i in idxs)
                                # Recurse into the composite element
                                yield from flatten_fields(
                                    base_off + sf.bitoffset + elem_base2,
                                    f"{base_name}{separator}{sf.name}{idx_suffix}",
                                    replace(sf, elements=()),  # same type, but treat as single element
                                )
                    else:
                        # Simple composite field: recurse
                        yield from flatten_fields(
                            base_off,
                            f"{base_name}{separator}{sf.name}",
                            sf,
                        )
                else:
                    # Primitive (or typedef to primitive); keep (we do NOT unroll scalar arrays)
                    yield replace(
                        sf,
                        name=f"{base_name}{separator}{sf.name}",
                        bitoffset=base_off + sf.bitoffset,
                    )

        # Top-level handling for `f` (which is composite here)
        base_name = prefix or f.name
        if not f.elements:
            # Single composite
            yield from emit_subfields(base_name, 0)
        else:
            # Array of composites at this level
            if not flatten_arrays:
                yield replace(f, name=base_name, bitoffset=parent_base_bits + f.bitoffset)
            else:
                from itertools import product

                dims: List[int] = list(f.elements)
                elem_stride_bits = ref.size * 8

                def linear_index(idxs: Tuple[int, ...], dims: List[int]) -> int:
                    stride = 1
                    idx = 0
                    for i, d in zip(reversed(idxs), reversed(dims)):
                        idx += i * stride
                        stride *= d
                    return idx

                for idxs in product(*[range(d) for d in dims]):
                    lin = linear_index(idxs, dims)
                    elem_base = lin * elem_stride_bits
                    idx_suffix = "".join(f"_{i}_" for i in idxs)
                    yield from emit_subfields(f"{base_name}{idx_suffix}", elem_base)

    new_defs: List[TypeBase] = []
    no_change = True

    for d in definitions:
        if (
            not isinstance(d, (ClassDefinition, UnionDefinition))
            or d.fullname not in targets_full
        ):
            new_defs.append(d)
            continue

        no_change = False
        flat_fields: List[Field] = []
        for f in sorted(d.fields, key=lambda x: x.bitoffset):
            ref = defs_by_fullname.get(f.type.fullname)
            if isinstance(ref, (ClassDefinition, UnionDefinition)):
                flat_fields.extend(list(flatten_fields(0, "", f)))
            else:
                flat_fields.append(f)

        flat_fields.sort(key=lambda x: x.bitoffset)
        new_defs.append(replace(d, fields=tuple(flat_fields)))

    if no_change:
        raise RuntimeError(f"Could not find any known struct in targets {targets}")
    return new_defs



def remove_enums(
    definitions: List[TypeBase],
    *,
    default_int_type: str = "int",
) -> List[TypeBase]:
    """
    Replace all uses of EnumDefinition with an integer type and drop the enum definitions.
    Tries `enum.underlying_type` (if present), otherwise uses `default_int_type`.
    """
    # Build enum -> replacement type map
    enum_map: Dict[str, TypeBase] = {}
    for d in definitions:
        if isinstance(d, EnumDefinition):
            # Try to discover an underlying type; adapt to your datamodel
            underlying = getattr(d, "underlying_type", None) or getattr(d, "type", None)
            if isinstance(underlying, TypeBase):
                enum_map[d.fullname] = underlying
            elif isinstance(underlying, str):
                enum_map[d.fullname] = TypeBase(name=underlying)
            else:
                enum_map[d.fullname] = TypeBase(name=default_int_type)

    def subst_type(t: TypeBase) -> TypeBase:
        # Replace if this type is an enum (match by fullname or by name as fallback)
        if t.fullname in enum_map:
            return enum_map[t.fullname]
        # Some IRs might not have fullname filled on TypeBase; match by name
        if (
            t.name in {defs_by_name[k].name for k in enum_map.keys()}
            if (
                defs_by_name := {
                    d.fullname: d for d in definitions if isinstance(d, EnumDefinition)
                }
            )
            else set()
        ):
            # find the first matching by name; if multiple enums share a short name in different namespaces,
            # prefer not to guess—keep original type in that rare case.
            candidates = [
                enum_map[k]
                for k, ed in defs_by_name.items()
                if ed.name == t.name and k in enum_map
            ]
            if len(candidates) == 1:
                return candidates[0]
        return t

    out: List[TypeBase] = []
    for d in definitions:
        if isinstance(d, EnumDefinition):
            # drop enum definitions
            continue
        elif isinstance(d, (ClassDefinition, UnionDefinition)):
            new_fields = tuple(replace(f, type=subst_type(f.type)) for f in d.fields)
            out.append(replace(d, fields=new_fields))
        elif isinstance(d, TypedefDefinition):
            out.append(replace(d, type=subst_type(d.type)))
        elif isinstance(d, ConstantDefinition):
            out.append(replace(d, type=subst_type(d.type)))
        else:
            out.append(d)
    return out


def remove_source(
    definitions: List[DefinitionBase], *, header_only: bool = False
) -> List[DefinitionBase]:
    """
    Rewrite `source` for all definitions:
      - header_only = False (default): set source to empty string "".
      - header_only = True: keep only the header's basename (no directories).
        Angle-bracket pseudo-paths (e.g., "<built-in>") are preserved as-is.

    Returns a NEW list with updated instances.
    """
    out = []
    for d in definitions:
        s = d.source or ""
        if not header_only:
            new_s = ""
        else:
            s_stripped = s.strip().strip('"').strip("'")
            if s_stripped.startswith("<") and s_stripped.endswith(">"):
                new_s = s_stripped  # keep pseudo-sources like <built-in>
            elif s_stripped:
                # PurePath is OS-agnostic; handles both "/" and "\".
                new_s = PurePath(s_stripped).name
            else:
                new_s = ""
        out.append(replace(d, source=new_s))
    return out
