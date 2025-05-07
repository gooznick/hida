import sys
import os

here = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(here, os.pardir))

from cast_xml_parse import (CastXmlParse, parse)
from data import *
from data_helpers import *

def test_basic():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'basic.xml'))

    assert isinstance(result, list), "Expected list of class definitions"

    struct_a = find_type_by_name(result, "A")
    assert struct_a is not None, "Struct A not found"

    expected_fields = [
        {
            "name": "i",
            "c_type": "int32_t",
            "elements": [],
            "bitoffset": 0,
            "size_in_bits": 32,
            "bitfield": False,
        },
        {
            "name": "f",
            "c_type": "float",
            "elements": [],
            "bitoffset": 32,
            "size_in_bits": 32,
            "bitfield": False,
        },
    ]

    assert len(struct_a.fields) == len(expected_fields), f"Expected {len(expected_fields)} fields"

    for idx, expected in enumerate(expected_fields):
        field = struct_a.fields[idx]
        for key, value in expected.items():
            actual = getattr(field, key)
            assert actual == value, f"Field '{field.name}' expected {key}={value}, got {actual}"

    expected_size = 8  # two 4-byte fields
    assert struct_a.size == expected_size, f"Expected struct size {expected_size}, got {struct_a.size}"
    validate_definitions(result)
    
def test_class():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'class.xml'))

    assert isinstance(result, list), "Expected list of class definitions"

    a = find_type_by_name(result, "A")
    assert a is not None, "Class A not found"
    assert len(a.fields) == 2, "A should have 2 fields"
    assert a.fields[0].name == "i" and a.fields[0].c_type == "int32_t"
    assert a.fields[1].name == "f" and a.fields[1].c_type == "float"
    validate_definitions(result)

def test_basics():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'basics.xml'))

    assert isinstance(result, list), "Expected list of class definitions"

    a = find_type_by_name(result, "A")
    assert a is not None, "Struct A not found"
    assert len(a.fields) == 2
    assert a.fields[0].name == "i" and a.fields[0].c_type == "int32_t"
    assert a.fields[1].name == "f" and a.fields[1].c_type == "float"

    b = find_type_by_name(result, "B")
    assert b is not None, "Struct B not found"
    assert len(b.fields) == 2
    assert b.fields[0].name == "i" and b.fields[0].c_type == "int8_t"
    assert b.fields[1].name == "d" and b.fields[1].c_type == "double"

    c = find_type_by_name(result, "C")
    assert c is not None, "Class C not found"
    assert len(c.fields) == 3
    assert c.fields[0].name == "i" and c.fields[0].c_type == "int8_t"
    assert c.fields[1].name == "us" and c.fields[1].c_type == "uint16_t"
    assert c.fields[2].name == "s" and c.fields[2].c_type == "int16_t"
    validate_definitions(result)

def test_normalize_integral_type():
    fn = CastXmlParse._normalize_integral_type  # staticmethod

    assert fn("int", 32) == "int32_t"
    assert fn("unsigned int", 32) == "uint32_t"
    assert fn("short", 16) == "int16_t"
    assert fn("unsigned short", 16) == "uint16_t"
    assert fn("long long", 64) == "int64_t"
    assert fn("unsigned long long", 64) == "uint64_t"
    assert fn("char", 8) == "int8_t"
    assert fn("unsigned char", 8) == "uint8_t"

    assert fn("float", 32) == "float"
    assert fn("double", 64) == "double"
    assert fn("long double", 128) == "long double"
    assert fn("void*", 64) == "void*"

    assert fn("bool", 8) == "uint8_t"
    assert fn("bool", 8, use_bool=True) == "bool"


def test_all_basic_types():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'basic_types.xml'))

    assert isinstance(result, list), "Expected list of class definitions"

    struct_def = find_type_by_name(result, "AllBasicTypes")
    assert struct_def is not None, "Struct AllBasicTypes not found"
    expected_fields = [
        ("b", "uint8_t"),  # or "bool" if use_bool=True is respected
        ("c", "int8_t"),
        ("sc", "int8_t"),
        ("uc", "uint8_t"),
        ("s", "int16_t"),
        ("us", "uint16_t"),
        ("i", "int32_t"),
        ("ui", "uint32_t"),
        ("l", "int64_t"),
        ("ul", "uint64_t"),
        ("ll", "int64_t"),
        ("ull", "uint64_t"),
        ("f", "float"),
        ("d", "double"),
        ("ld", "long double"),
    ]

    assert len(struct_def.fields) == len(expected_fields)

    for idx, (field_name, c_type) in enumerate(expected_fields):
        field = struct_def.fields[idx]
        assert field.name == field_name, f"Expected field '{field_name}', got '{field.name}'"
        assert field.c_type == c_type, f"Expected type '{c_type}' for '{field_name}', got '{field.c_type}'"

def test_nested_structs():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'nested.xml'))

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    a = find_type_by_name(result, "A")
    assert a is not None and len(a.fields) == 1
    assert a.fields[0].name == "a" and a.fields[0].c_type == "int32_t"

    b = find_type_by_name(result, "B")
    assert b is not None and len(b.fields) == 2
    assert b.fields[0].name == "a" and b.fields[0].c_type == "A"
    assert b.fields[1].name == "b" and b.fields[1].c_type == "int32_t"

    c = find_type_by_name(result, "C")
    assert c is not None and len(c.fields) == 3
    assert c.fields[0].name == "a" and c.fields[0].c_type == "A"
    assert c.fields[1].name == "b" and c.fields[1].c_type == "B"
    assert c.fields[2].name == "c" and c.fields[2].c_type == "int32_t"

def test_arrays():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'arrays.xml'))

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    b = find_type_by_name(result, "B")
    assert b is not None, "Struct B not found"

    expected_fields = [
        ("s", "A", [2]),
        ("a", "int32_t", [10]),
        ("b", "int32_t", [2, 3]),
        ("c", "int32_t", [2, 3, 4]),
        ("d", "int32_t", [5, 6, 7, 8]),
        ("e", "int32_t", [0]),
    ]

    assert len(b.fields) == len(expected_fields), f"Expected {len(expected_fields)} fields"

    for idx, (name, c_type, elements) in enumerate(expected_fields):
        field = b.fields[idx]
        assert field.name == name, f"Expected field name '{name}', got '{field.name}'"
        assert field.c_type == c_type, f"Expected c_type '{c_type}', got '{field.c_type}'"
        assert field.elements == elements, f"Expected elements {elements}, got {field.elements}"
        assert isinstance(field.size_in_bits, int) and field.size_in_bits > 0, f"Invalid size_in_bits for '{name}'"

    assert b.size > 0, f"Struct B size must be positive, got {b.size}"

def test_pointers():
    result = parse(os.path.join(here, os.pardir, 'headers', 'castxml', 'pointers.xml'))

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    struct_def = find_type_by_name(result, "Pointers")
    assert struct_def is not None, "Struct Pointers not found"

    expected_fields = [
        ("p_int", "void*"),
        ("pp_float", "void*"),
        ("p_void", "void*"),
        ("p_char", "void*"),
        ("p_const_double", "void*"),
        ("func_ptr", "void*"),
        ("void_func_ptr", "void*"),
        ("arr_func_ptr", "void*"),
    ]

    assert len(struct_def.fields) == len(expected_fields), f"Expected {len(expected_fields)} fields"

    for idx, (name, c_type) in enumerate(expected_fields):
        field = struct_def.fields[idx]
        assert field.name == name, f"Expected field name '{name}', got '{field.name}'"
        assert field.c_type == c_type, f"Expected type '{c_type}' for field '{name}', got '{field.c_type}'"
        assert field.elements in ([], [3]) if name == "arr_func_ptr" else field.elements == [], \
            f"Unexpected array dimensions in field '{name}': {field.elements}"
