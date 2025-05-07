from data import *

builtin_types = {
    "int8_t",
    "uint8_t",
    "int16_t",
    "uint16_t",
    "int32_t",
    "uint32_t",
    "int64_t",
    "uint64_t",
    "int128_t",
    "uint128_t",
    "float",
    "double",
    "long double",
    "bool",
    "void*",
}


def find_type_by_name(data_structs, name):
    """
    Finds and returns the first ClassDefinition, UnionDefinition, or EnumDefinition
    with the given name from the data_structs list.
    Returns None if not found.
    """
    for item in data_structs:
        if hasattr(item, "name") and item.name == name:
            return item
    return None


def validate_class_definition(cls: ClassDefinition, types):
    """
    Validates the integrity of a ClassDefinition instance.
    Raises ValueError if any condition is violated.
    """
    if not isinstance(cls.name, str) or not cls.name:
        raise ValueError("ClassDefinition name must be a non-empty string")

    if not isinstance(cls.source, str) or not cls.source:
        raise ValueError(f"Class '{cls.name}': source must be a non-empty string")

    if not isinstance(cls.size, int) or cls.size <= 0:
        raise ValueError(f"Class '{cls.name}': size must be a positive integer")

    if not isinstance(cls.alignment, int) or (cls.alignment < 0):
        raise ValueError(f"Class '{cls.name}': alignment must be non negative integer")

    if not isinstance(cls.fields, list):
        raise ValueError(f"Class '{cls.name}': fields must be a list")

    for field in cls.fields:
        if not isinstance(field.name, str) or not field.name:
            raise ValueError(f"Field in class '{cls.name}' has invalid or empty name")

        if not isinstance(field.c_type, str) or not field.c_type:
            raise ValueError(
                f"Field '{field.name}' in class '{cls.name}' has invalid or empty c_type"
            )

        if types != None and (
            not field.c_type in types and not field.c_type in builtin_types
        ):
            raise ValueError(
                f"Field '{field.name}' in class '{cls.name}' has unknown type '{field.c_type}'"
            )

        if not isinstance(field.bitoffset, int) or field.bitoffset < 0:
            raise ValueError(
                f"Field '{field.name}' in class '{cls.name}' has invalid bitoffset"
            )

        if not isinstance(field.size_in_bits, int) or field.size_in_bits < 0:
            raise ValueError(
                f"Field '{field.name}' in class '{cls.name}' has invalid size_in_bits ({field.size_in_bits})"
            )

        if not isinstance(field.bitfield, bool):
            raise ValueError(
                f"Field '{field.name}' in class '{cls.name}' has invalid bitfield flag"
            )

        if not isinstance(field.elements, list):
            raise ValueError(
                f"Field '{field.name}' in class '{cls.name}' has non-list elements attribute"
            )

        for dim in field.elements:
            if not isinstance(dim, int) or dim < 0:
                raise ValueError(
                    f"Field '{field.name}' in class '{cls.name}' has invalid array dimension: {dim}"
                )
            if dim == 0 and field.elements != [0]:
                raise ValueError(
                    f"Field '{field.name}' in class '{cls.name}' has dimension 0 not as [0] exactly"
                )


def validate_typedef_definition(td: TypedefDefinition, types):
    """
    Validates a TypedefDefinition instance.
    Raises ValueError if any condition is violated.
    """
    if not isinstance(td.name, str) or not td.name:
        raise ValueError("TypedefDefinition name must be a non-empty string")

    if not isinstance(td.source, str) or not td.source:
        raise ValueError(f"Typedef '{td.name}': source must be a non-empty string")

    if not isinstance(td.definition, str) or not td.definition:
        raise ValueError(f"Typedef '{td.name}': definition must be a non-empty string")

    if types != None and (
        not td.definition in types and not td.definition in builtin_types
    ):
        raise ValueError(f"Typedef '{td.name}': unknown type '{td.definition}'")

    if not isinstance(td.elements, list):
        raise ValueError(f"Typedef '{td.name}': elements must be a list")

    for dim in td.elements:
        if not isinstance(dim, int) or dim < 0:
            raise ValueError(f"Typedef '{td.name}': invalid array dimension {dim}")
        if dim == 0 and td.elements != [0]:
            raise ValueError(
                f"Typedef '{td.name}': dimension 0 must appear only as [0]"
            )


def validate_enum_definition(enum: EnumDefinition):
    """
    Validates an EnumDefinition instance.
    Raises ValueError if any condition is violated.
    """
    if not isinstance(enum.name, str):
        raise ValueError(
            "EnumDefinition name must be a string (can be empty for anonymous)"
        )

    if not isinstance(enum.source, str) or not enum.source:
        raise ValueError(f"Enum '{enum.name}': source must be a non-empty string")

    if not isinstance(enum.size, int) or enum.size <= 0:
        raise ValueError(f"Enum '{enum.name}': size must be a positive integer")

    if not isinstance(enum.enums, list):
        raise ValueError(f"Enum '{enum.name}': enums must be a list")

    for enum_value in enum.enums:
        if not isinstance(enum_value, EnumName):
            raise ValueError(f"Enum '{enum.name}': enum value must be of type EnumName")
        if not isinstance(enum_value.name, str) or not enum_value.name:
            raise ValueError(
                f"Enum '{enum.name}': enum value has invalid or empty name"
            )
        if not isinstance(enum_value.value, int):
            raise ValueError(
                f"Enum '{enum.name}': enum value '{enum_value.name}' must have an integer value"
            )


def validate_union_definition(u: UnionDefinition, types):
    """
    Validates a UnionDefinition instance.
    Raises ValueError if any condition is violated.
    """
    if not isinstance(u.name, str) or not u.name:
        raise ValueError("UnionDefinition name must be a non-empty string")

    if not isinstance(u.source, str) or not u.source:
        raise ValueError(f"Union '{u.name}': source must be a non-empty string")

    if not isinstance(u.size, int) or u.size <= 0:
        raise ValueError(f"Union '{u.name}': size must be a positive integer")

    if not isinstance(u.alignment, int) or u.alignment < 0:
        raise ValueError(f"Union '{u.name}': alignment must be a non-negative integer")

    if not isinstance(u.fields, list):
        raise ValueError(f"Union '{u.name}': fields must be a list")

    for field in u.fields:
        if not isinstance(field.name, str) or not field.name:
            raise ValueError(f"Union '{u.name}': field has invalid or empty name")
        if not isinstance(field.c_type, str) or not field.c_type:
            raise ValueError(
                f"Union '{u.name}': field '{field.name}' has invalid or empty c_type"
            )
        if types != None and (
            field.c_type not in types and field.c_type not in builtin_types
        ):
            raise ValueError(
                f"Union '{u.name}': field '{field.name}' has unknown type '{field.c_type}'"
            )
        if not isinstance(field.bitoffset, int) or field.bitoffset < 0:
            raise ValueError(
                f"Union '{u.name}': field '{field.name}' has invalid bitoffset"
            )
        if not isinstance(field.size_in_bits, int) or field.size_in_bits <= 0:
            raise ValueError(
                f"Union '{u.name}': field '{field.name}' has invalid size_in_bits ({field.size_in_bits})"
            )
        if not isinstance(field.bitfield, bool):
            raise ValueError(
                f"Union '{u.name}': field '{field.name}' has invalid bitfield flag"
            )
        if not isinstance(field.elements, list):
            raise ValueError(
                f"Union '{u.name}': field '{field.name}' has invalid elements"
            )
        for dim in field.elements:
            if not isinstance(dim, int) or dim < 0:
                raise ValueError(
                    f"Union '{u.name}': field '{field.name}' has invalid array dimension: {dim}"
                )
            if dim == 0 and field.elements != [0]:
                raise ValueError(
                    f"Union '{u.name}': field '{field.name}' has dimension 0 not as [0]"
                )


def validate_constant_definition(cd: ConstantDefinition, types):
    """
    Validates a ConstantDefinition instance.
    Raises ValueError if any condition is violated.
    """
    if not isinstance(cd.name, str) or not cd.name:
        raise ValueError("ConstantDefinition name must be a non-empty string")

    if not isinstance(cd.source, str) or not cd.source:
        raise ValueError(f"Constant '{cd.name}': source must be a non-empty string")

    if not isinstance(cd.c_type, str) or not cd.c_type:
        raise ValueError(f"Constant '{cd.name}': c_type must be a non-empty string")

    if cd.c_type not in types and cd.c_type not in builtin_types:
        raise ValueError(f"Constant '{cd.name}': unknown type '{cd.c_type}'")

    if not isinstance(cd.value, (int, float, str)):
        raise ValueError(f"Constant '{cd.name}': value must be int, float, or str")


def verify_size(definitions):
    """
    Verifies memory layout of structs and unions:
    - For structs: fields must not overlap, size must be enough
    - For unions: all fields start at 0, and total size must cover largest field
    """
    for d in definitions:
        if isinstance(d, ClassDefinition):
            prev_end = 0
            for field in d.fields:
                count = 1
                for dim in field.elements:
                    count *= dim
                total_bits = field.size_in_bits * count

                if field.bitoffset < prev_end:
                    raise ValueError(f"{d.name}: Field '{field.name}' overlaps previous field at bit offset {field.bitoffset}")
                prev_end = field.bitoffset + total_bits

            if d.size * 8 < prev_end:
                raise ValueError(f"{d.name}: Struct size too small ({d.size} bytes) for last field ending at bit {prev_end}")

        elif isinstance(d, UnionDefinition):
            max_bits = 0
            for field in d.fields:
                if field.bitoffset != 0:
                    raise ValueError(f"{d.name}: Union field '{field.name}' must start at bit offset 0")

                count = 1
                for dim in field.elements:
                    count *= dim
                total_bits = field.size_in_bits * count

                if total_bits > max_bits:
                    max_bits = total_bits

            if d.size * 8 < max_bits:
                raise ValueError(f"{d.name}: Union size too small ({d.size} bytes) for largest field ({max_bits} bits)")

def find_struct_holes(definitions):
    """
    For each struct, return a list of (start_bit, size_in_bits, after_field_name) tuples
    representing padding holes between fields or at the end.
    """
    result = {}

    for d in definitions:
        if not isinstance(d, ClassDefinition):
            continue

        holes = []
        regions = []

        for field in d.fields:
            count = 1
            for dim in field.elements:
                count *= dim
            size = field.size_in_bits * count
            start = field.bitoffset
            end = start + size
            regions.append((start, end, field.name))

        regions.sort()

        prev_end = 0
        prev_name = None
        for start, end, name in regions:
            if start > prev_end:
                if prev_name is not None:
                    holes.append((prev_end, start - prev_end, prev_name))
            prev_end = max(prev_end, end)
            prev_name = name

        struct_end = d.size * 8
        if prev_name is not None and prev_end < struct_end:
            holes.append((prev_end, struct_end - prev_end, prev_name))

        if holes:
            result[d.name] = holes

    return result


def add_padding_fields(definitions):
    """
    Return a new list of definitions where holes in structs/unions
    are filled with padding fields named pad0, pad1, etc.
    """
    padded_defs = []
    
    for d in definitions:
        if not isinstance(d, (ClassDefinition)):
            padded_defs.append(d)
            continue

        holes = find_struct_holes([d]).get(d.name, [])
        new_fields = list(d.fields)  # copy original fields
        pad_index = 0

        for start_bit, size_bits, _ in holes:
            pad_field = Field(
                name=f"pad{pad_index}",
                c_type="uint8_t",  # dummy type
                elements=[],
                bitoffset=start_bit,
                size_in_bits=size_bits,
                bitfield=True
            )
            new_fields.append(pad_field)
            pad_index += 1

        # sort fields by bitoffset again
        new_fields.sort(key=lambda f: f.bitoffset)

        if isinstance(d, ClassDefinition):
            new_def = ClassDefinition(
                name=d.name,
                source=d.source,
                alignment=d.alignment,
                size=d.size,
                fields=new_fields
            )


        padded_defs.append(new_def)

    return padded_defs

def remove_typedefs(definitions):
    """
    Replaces all typedef usage with their original type name
    and removes TypedefDefinition objects from the definitions list.
    """
    # 1. Build typedef mapping: typedef_name → actual_type
    typedef_map = {
        td.name: td.definition
        for td in definitions
        if isinstance(td, TypedefDefinition)
    }

    # 2. Replace typedefs in fields
    for d in definitions:
        if isinstance(d, (ClassDefinition, UnionDefinition)):
            for field in d.fields:
                while field.c_type in typedef_map:
                    field.c_type = typedef_map[field.c_type]

    # 3. Remove TypedefDefinition instances
    return [d for d in definitions if not isinstance(d, TypedefDefinition)]

def validate_definitions(definitions):
    """
    Validates that 'definitions' is a list of known definition dataclasses,
    and performs per-type validation where applicable.
    """
    if not isinstance(definitions, list):
        raise ValueError("Definitions must be a list")

    allowed_types = (
        ClassDefinition,
        UnionDefinition,
        EnumDefinition,
        TypedefDefinition,
        ConstantDefinition,
    )

    types = {defn.name for defn in definitions}

    for defn in definitions:
        if not isinstance(defn, allowed_types):
            raise ValueError(f"Invalid definition type: {type(defn).__name__}")

        if isinstance(defn, ClassDefinition):
            validate_class_definition(defn, types)
        if isinstance(defn, TypedefDefinition):
            validate_typedef_definition(defn, types)
        if isinstance(defn, EnumDefinition):
            validate_enum_definition(defn)
        if isinstance(defn, UnionDefinition):
            validate_union_definition(defn, types)
        if isinstance(defn, ConstantDefinition):
            validate_constant_definition(defn, types)
    verify_size(definitions)
    

