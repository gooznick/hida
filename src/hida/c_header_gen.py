from typing import List
from .data import *


def write_c_header_from_definitions(definitions):
    """
    Generate a C-compatible header file (as string) from a list of definitions.
    Namespaces are flattened using '__'. Scoped enums and classes are adapted.
    """
    lines = [
        "#pragma once",
        "#include <stdint.h>",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
    ]

    def flat_name(t):
        return t.fullname.replace("::", "__")

    for d in definitions:
        if isinstance(d, ClassDefinition):
            lines.append(f"typedef struct {flat_name(d)} {{")
            for f in d.fields:
                typename = f.type.fullname.replace("::", "__")
                arr = (
                    ""
                    if not f.elements
                    else "[" + "][".join(map(str, f.elements)) + "]"
                )
                lines.append(f"    {typename} {f.name}{arr};")
            lines.append(f"}} {flat_name(d)};")
            lines.append("")

        elif isinstance(d, UnionDefinition):
            lines.append(f"typedef union {flat_name(d)} {{")
            for f in d.fields:
                typename = f.type.fullname.replace("::", "__")
                arr = (
                    ""
                    if not f.elements
                    else "[" + "][".join(map(str, f.elements)) + "]"
                )
                lines.append(f"    {typename} {f.name}{arr};")
            lines.append(f"}} {flat_name(d)};")
            lines.append("")

        elif isinstance(d, EnumDefinition):
            lines.append(f"typedef enum {flat_name(d)} {{")
            for e in d.enums:
                lines.append(f"    {flat_name(d)}_{e.name} = {e.value},")
            lines.append(f"}} {flat_name(d)};")
            lines.append("")

        elif isinstance(d, TypedefDefinition):
            target = d.type.fullname.replace("::", "__")
            arr = "" if not d.elements else "[" + "][".join(map(str, d.elements)) + "]"
            lines.append(f"typedef {target} {flat_name(d)}{arr};")
            lines.append("")

        elif isinstance(d, ConstantDefinition):
            val = d.value
            if isinstance(val, str):
                val = val.encode("unicode_escape").decode("ascii")
                val = f"'{val}'" if len(val) == 1 else f'"{val}"'
            lines.append(f"#define {d.name} {val}")

    lines += ["", "#ifdef __cplusplus", '} // extern "C"', "#endif"]
    return "\n".join(lines)
