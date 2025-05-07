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
        "void*"
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

    if not isinstance(cls.alignment, int) or (cls.alignment != 0 and (cls.alignment & (cls.alignment - 1)) != 0):
        raise ValueError(f"Class '{cls.name}': alignment must be 0 or a power of two")

    if not isinstance(cls.fields, list):
        raise ValueError(f"Class '{cls.name}': fields must be a list")

    for field in cls.fields:
        if not isinstance(field.name, str) or not field.name:
            raise ValueError(f"Field in class '{cls.name}' has invalid or empty name")

        if not isinstance(field.c_type, str) or not field.c_type:
            raise ValueError(f"Field '{field.name}' in class '{cls.name}' has invalid or empty c_type")

        if not field.c_type in types and not field.c_type in builtin_types:
            raise ValueError(f"Field '{field.name}' in class '{cls.name}' has unknown type '{field.c_type}'")
                 
        if not isinstance(field.bitoffset, int) or field.bitoffset < 0:
            raise ValueError(f"Field '{field.name}' in class '{cls.name}' has invalid bitoffset")

        if not isinstance(field.size_in_bits, int) or field.size_in_bits < 0:
            raise ValueError(f"Field '{field.name}' in class '{cls.name}' has invalid size_in_bits")

        if not isinstance(field.bitfield, bool):
            raise ValueError(f"Field '{field.name}' in class '{cls.name}' has invalid bitfield flag")

        if not isinstance(field.elements, list):
            raise ValueError(f"Field '{field.name}' in class '{cls.name}' has non-list elements attribute")

        for dim in field.elements:
            if not isinstance(dim, int) or dim < 0:
                raise ValueError(f"Field '{field.name}' in class '{cls.name}' has invalid array dimension: {dim}")
            if dim == 0 and field.elements != [0]:
                raise ValueError(f"Field '{field.name}' in class '{cls.name}' has dimension 0 not as [0] exactly")

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

    if not td.definition in types and not td.definition in builtin_types:
        raise ValueError(f"Typedef '{td.name}': unknown type '{td.definition}'")
           
    if not isinstance(td.elements, list):
        raise ValueError(f"Typedef '{td.name}': elements must be a list")

    for dim in td.elements:
        if not isinstance(dim, int) or dim < 0:
            raise ValueError(f"Typedef '{td.name}': invalid array dimension {dim}")
        if dim == 0 and td.elements != [0]:
            raise ValueError(f"Typedef '{td.name}': dimension 0 must appear only as [0]")


def validate_definitions(definitions):
    """
    Validates that 'definitions' is a list of known definition dataclasses,
    and performs per-type validation where applicable.
    """
    if not isinstance(definitions, list):
        raise ValueError("Definitions must be a list")

    allowed_types = (ClassDefinition, UnionDefinition, EnumDefinition, TypedefDefinition, ConstantDefinition)

    types = {defn.name for defn in definitions}

    for defn in definitions:
        if not isinstance(defn, allowed_types):
            raise ValueError(f"Invalid definition type: {type(defn).__name__}")

        if isinstance(defn, ClassDefinition):
            validate_class_definition(defn, types)
        if isinstance(defn, TypedefDefinition):
            validate_typedef_definition(defn, types)
