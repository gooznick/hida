from data import *


from dataclasses import replace

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
            new_fields.append(Field(
                name=f"__pad{pad_counter}",
                type=TypeBase(name="uint8_t"),
                elements=(),
                bitoffset=prev_end,
                size_in_bits=pad_size,
                bitfield=True,
            ))
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
                    raise ValueError(f"Cannot pad non-byte-aligned hole of size {hole_size} bits")

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
