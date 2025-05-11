import sys
import os

here = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(here, os.pardir))

from cast_xml_parse import CastXmlParse, parse
from data import *
from data_helpers import *

import platform

windows = platform.system() == "Windows"

def test_complicated():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'complicated.xml'),
                   use_bool=True, skip_failed_parsing=True, remove_unknown=True)

    assert isinstance(result, list), "Expected list of parsed definitions"
    validate_definitions(result)

    struct = find_type_by_name(result, "Everything")
    assert struct is not None, "Struct 'Everything' not found"
    assert isinstance(struct, ClassDefinition)

    expected_fields = {
        # Basic + fixed-width
        "i": "int32_t",
        "f": "float",
        "b": "bool",
        "i32": "int32_t",
        "u64": "uint64_t",

        # Wide chars
        "wch": ("int32_t", "uint32_t", "int16_t"),

        "ch16": ("int16_t", "uint16_t"),
        "ch32": ("int32_t", "uint32_t"),

        # Arrays
        "a1": ("int32_t", [3]),
        "a2": ("float", [2, 2]),
        "a3": ("double", [2, 2, 2]),
        "a4": ("int8_t", [2, 2, 2, 2]),  # char is int8_t

        # Pointers
        "p_i": "void*",
        "pp_f": "void*",
        "p_cstr": "void*",
        "p_void": "void*",
        "p_str": "void*",

        # Function pointers
        "callback": "void*",
        "handlers": ("void*", [2]),

        # Typedefs
        "my_i": "int32_t",
        "my_ul": "uint32_t" if windows else "uint64_t",
        "fp": "void*",
        "pt": "void*",
        #"pts": ("Point", [5]),

        # Enums
        "e1": "SimpleEnum",
        "e2": "ScopedEnum",

        # Union
        "mix": "MixedUnion",

        # Namespaced
        "ns": "Outer::Inner::Namespaced",

        # Bitfield struct
        "bits": "BitfieldStruct",
    }

    fields_by_name = {f.name: f for f in struct.fields}

    def type_matches(actual, expected_type):
        if isinstance(expected_type, (tuple, list)):
            return actual in expected_type
        return actual == expected_type

    for name, expected in expected_fields.items():
        assert name in fields_by_name, f"Field '{name}' missing from Everything struct"
        field = fields_by_name[name]

        if isinstance(expected, tuple) and isinstance(expected[1], list):
            expected_type, expected_dims = expected
            assert type_matches(field.type, expected_type), f"{name}: expected type {expected_type}, got {field.type}"
            assert field.elements == expected_dims, f"{name}: expected dimensions {expected_dims}, got {field.elements}"
        else:
            assert type_matches(field.type, expected), f"{name}: expected type {expected}, got {field.type}"
            assert field.elements == [], f"{name}: expected scalar, got array {field.elements}"

        assert isinstance(field.size_in_bits, int) and field.size_in_bits > 0, f"{name}: invalid bit size"

    # Optionally, validate enums, typedefs, and unions exist too
    assert find_type_by_name(result, "MixedUnion"), "Union MixedUnion missing"
    assert find_type_by_name(result, "ScopedEnum"), "ScopedEnum missing"
    assert find_type_by_name(result, "SimpleEnum"), "SimpleEnum missing"
    assert find_type_by_name(result, "Point"), "Typedef Point missing"
