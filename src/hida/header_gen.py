from typing import List

from hida import TypeBase, TypedefDefinition, ConstantDefinition, ClassDefinition, UnionDefinition, EnumDefinition

def to_c_type(t: TypeBase) -> str:
    name = t.name
    ns = list(t.namespace)

    # Replace int32_t → std::int32_t (etc.) if it looks like a fixed-width type
    fixed_types = {
        "int8_t", "int16_t", "int32_t", "int64_t",
        "uint8_t", "uint16_t", "uint32_t", "uint64_t"
    }
    if name in fixed_types and not ns:
        ns = ["std"]

    return "::".join(ns + [name]) if ns else name

def write_header_from_definitions(definitions: List[TypeBase]) -> str:
    lines = ["#pragma once", ""]

    fixed_width_names = {
        "int8_t", "int16_t", "int32_t", "int64_t",
        "uint8_t", "uint16_t", "uint32_t", "uint64_t"
    }

    def uses_fixed_width_types(defn):
        if isinstance(defn, (TypedefDefinition, ConstantDefinition)):
            return defn.type.name in fixed_width_names
        if isinstance(defn, (ClassDefinition, UnionDefinition)):
            return any(f.type.name in fixed_width_names for f in defn.fields)
        return False

    needs_cstdint = any(uses_fixed_width_types(d) for d in definitions)


    if needs_cstdint:
        lines.append("#include <cstdint>")
        lines.append("")

    for d in definitions:
        if isinstance(d, ClassDefinition):
            ns_open = [f"namespace {ns} {{" for ns in d.namespace]
            ns_close = ["}" for _ in d.namespace]

            if d.alignment:
                lines.append(f"#pragma pack(push, {d.alignment})")
            lines.extend(ns_open)

            lines.append(f"struct {d.name} {{")
            for f in d.fields:
                base = to_c_type(f.type)
                decl = ""
                for dim in f.elements:
                    decl += f"[{dim}]"
                if f.bitfield:
                    decl += f" : {f.size_in_bits}"
                lines.append(f"    {base} {f.name} {decl};")
            lines.append("};")

            lines.extend(ns_close)
            if d.alignment:
                lines.append("#pragma pack(pop)")
            lines.append("")

        elif isinstance(d, UnionDefinition):
            ns_open = [f"namespace {ns} {{" for ns in d.namespace]
            ns_close = ["}" for _ in d.namespace]

            if d.alignment:
                lines.append(f"#pragma pack(push, {d.alignment})")
            lines.extend(ns_open)

            lines.append(f"union {d.name} {{")
            for f in d.fields:
                base = to_c_type(f.type)
                decl = ""
                for dim in f.elements:
                    decl += f"[{dim}]"
                if f.bitfield:
                    decl += f" : {f.size_in_bits}"
                lines.append(f"    {base} {f.name} {decl};")
            lines.append("};")

            lines.extend(ns_close)
            if d.alignment:
                lines.append("#pragma pack(pop)")
            lines.append("")

        elif isinstance(d, EnumDefinition):
            ns_open = [f"namespace {ns} {{" for ns in d.namespace]
            ns_close = ["}" for _ in d.namespace]

            lines.extend(ns_open)
            lines.append(f"enum {d.name} {{")
            for e in d.enums:
                lines.append(f"    {e.name} = {e.value},")
            lines.append("};")
            lines.extend(ns_close)
            lines.append("")

        elif isinstance(d, TypedefDefinition):
            base = to_c_type(d.type)
            array = ""
            for dim in d.elements:
                array += f"[{dim}]"
            lines.append(f"typedef {base} {d.name}{array};")

        elif isinstance(d, ConstantDefinition):
            typename = to_c_type(d.type)
            value = d.value
            if isinstance(value, str):
                if len(value) == 1:
                    escaped = value.encode("unicode_escape").decode("ascii")
                    value = f"'{escaped}'"
                else:
                    escaped = value.encode("unicode_escape").decode("ascii")
                    value = f'"{escaped}"'
            lines.append(f"static const {typename} {d.name} = {value};")

        else:
            raise RuntimeError(f"Unknown definition: {d}")

    print(lines)
    return "\n".join(lines)
