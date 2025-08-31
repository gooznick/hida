import sys
import os

here = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(here, os.pardir))

from hida import (
    EnumDefinition,
    parse,
    validate_definitions,
    find_type_by_name,
    ClassDefinition,
    UnionDefinition,
    ConstantDefinition,
    TypedefDefinition,
    TypeBase,
)

from hida.cast_xml_parse import CastXmlParse


def test_basic(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "basic.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"

    struct_a = find_type_by_name(result, "A")
    assert struct_a is not None, "Struct A not found"

    expected_fields = [
        {
            "name": "i",
            "type": TypeBase("int32_t"),
            "elements": (),
            "bitoffset": 0,
            "size_in_bits": 32,
            "bitfield": False,
        },
        {
            "name": "f",
            "type": TypeBase("float"),
            "elements": (),
            "bitoffset": 32,
            "size_in_bits": 32,
            "bitfield": False,
        },
    ]

    assert len(struct_a.fields) == len(
        expected_fields
    ), f"Expected {len(expected_fields)} fields"

    for idx, expected in enumerate(expected_fields):
        field = struct_a.fields[idx]
        for key, value in expected.items():
            actual = getattr(field, key)
            assert (
                actual == value
            ), f"Field '{field.name}' expected {key}={value}, got {actual}"

    expected_size = 8  # two 4-byte fields
    assert (
        struct_a.size == expected_size
    ), f"Expected struct size {expected_size}, got {struct_a.size}"
    validate_definitions(result)


def test_class(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "class.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"

    a = find_type_by_name(result, "A")
    assert a is not None, "Class A not found"
    assert len(a.fields) == 2, "A should have 2 fields"
    assert a.fields[0].name == "i" and a.fields[0].type.fullname == "int32_t"
    assert a.fields[1].name == "f" and a.fields[1].type.fullname == "float"
    validate_definitions(result)


def test_basics(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "basics.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"

    a = find_type_by_name(result, "A")
    assert a is not None, "Struct A not found"
    assert len(a.fields) == 2
    assert a.fields[0].name == "i" and a.fields[0].type.fullname == "int32_t"
    assert a.fields[1].name == "f" and a.fields[1].type.fullname == "float"

    b = find_type_by_name(result, "B")
    assert b is not None, "Struct B not found"
    assert len(b.fields) == 2
    assert b.fields[0].name == "i" and b.fields[0].type.fullname == "int8_t"
    assert b.fields[1].name == "d" and b.fields[1].type.fullname == "double"

    c = find_type_by_name(result, "C")
    assert c is not None, "Class C not found"
    assert len(c.fields) == 3
    assert c.fields[0].name == "i" and c.fields[0].type.fullname == "int8_t"
    assert c.fields[1].name == "us" and c.fields[1].type.fullname == "uint16_t"
    assert c.fields[2].name == "s" and c.fields[2].type.fullname == "int16_t"
    validate_definitions(result)


def test_normalize_integral_type():
    fn = CastXmlParse._normalize_integral_type  # staticmethod

    assert fn(TypeBase("int"), 32) == TypeBase("int32_t")
    assert fn(TypeBase("unsigned int"), 32) == TypeBase("uint32_t")
    assert fn(TypeBase("short"), 16) == TypeBase("int16_t")
    assert fn(TypeBase("unsigned short"), 16) == TypeBase("uint16_t")
    assert fn(TypeBase("long long"), 64) == TypeBase("int64_t")
    assert fn(TypeBase("unsigned long long"), 64) == TypeBase("uint64_t")
    assert fn(TypeBase("char"), 8) == TypeBase("int8_t")
    assert fn(TypeBase("unsigned char"), 8) == TypeBase("uint8_t")

    assert fn(TypeBase("float"), 32) == TypeBase("float")
    assert fn(TypeBase("double"), 64) == TypeBase("double")
    assert fn(TypeBase("long double"), 128) == TypeBase("long double")
    assert fn(TypeBase("void*"), 64) == TypeBase("void*")

    assert fn(TypeBase("bool"), 8) == TypeBase("uint8_t")
    assert fn(TypeBase("bool"), 8, use_bool=True) == TypeBase("bool")


def test_all_basic_types(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "basic_types.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"

    struct_def = find_type_by_name(result, "AllBasicTypes")
    assert struct_def is not None, "Struct AllBasicTypes not found"

    expected_fields = [
        ("b", TypeBase("uint8_t")),  # or TypeBase("bool") if use_bool=True
        ("c", TypeBase("int8_t")),
        ("sc", TypeBase("int8_t")),
        ("uc", TypeBase("uint8_t")),
        ("s", TypeBase("int16_t")),
        ("us", TypeBase("uint16_t")),
        ("i", TypeBase("int32_t")),
        ("ui", TypeBase("uint32_t")),
        ("l", TypeBase("int32_t" if cxplat.windows else "int64_t")),
        ("ul", TypeBase("uint32_t" if cxplat.windows else "uint64_t")),
        ("ll", TypeBase("int64_t")),
        ("ull", TypeBase("uint64_t")),
        ("f", TypeBase("float")),
        ("d", TypeBase("double")),
        ("ld", TypeBase("long double")),
    ]

    assert len(struct_def.fields) == len(expected_fields)

    for idx, (field_name, expected_type) in enumerate(expected_fields):
        field = struct_def.fields[idx]
        assert (
            field.name == field_name
        ), f"Expected field '{field_name}', got '{field.name}'"
        assert (
            field.type == expected_type
        ), f"Expected type '{expected_type.fullname}' for '{field_name}', got '{field.c_type.fullname}'"

    validate_definitions(result)


def test_nested_structs(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "nested.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"

    a = find_type_by_name(result, "A")
    assert a is not None and len(a.fields) == 1
    assert a.fields[0].name == "a" and a.fields[0].type.fullname == "int32_t"

    b = find_type_by_name(result, "B")
    assert b is not None and len(b.fields) == 2
    assert b.fields[0].name == "a" and b.fields[0].type.fullname == "A"
    assert b.fields[1].name == "b" and b.fields[1].type.fullname == "int32_t"

    c = find_type_by_name(result, "C")
    assert c is not None and len(c.fields) == 3
    assert c.fields[0].name == "a" and c.fields[0].type.fullname == "A"
    assert c.fields[1].name == "b" and c.fields[1].type.fullname == "B"
    assert c.fields[2].name == "c" and c.fields[2].type.fullname == "int32_t"

    validate_definitions(result)


def test_arrays(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "arrays.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    b = find_type_by_name(result, "B")
    assert b is not None, "Struct B not found"

    expected_fields = [
        ("s", "A", (2,)),
        ("a", "int32_t", (10,)),
        ("b", "int32_t", (2, 3)),
        ("c", "int32_t", (2, 3, 4)),
        ("d", "int32_t", (5, 6, 7, 8)),
    ]

    assert len(b.fields) == len(
        expected_fields
    ), f"Expected {len(expected_fields)} fields"

    for idx, (name, type_str, elements) in enumerate(expected_fields):
        field = b.fields[idx]
        assert field.name == name, f"Expected field name '{name}', got '{field.name}'"
        assert (
            field.type.fullname == type_str
        ), f"Expected type '{type_str}', got '{field.type.fullname}'"
        assert (
            field.elements == elements
        ), f"Expected elements {elements}, got {field.elements}"
        assert (
            isinstance(field.size_in_bits, int) and field.size_in_bits > 0
        ), f"Invalid size_in_bits for '{name}'"

    assert b.size > 0, f"Struct B size must be positive, got {b.size}"
    validate_definitions(result)


def test_pointers(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "pointers.xml")
    )

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

    assert len(struct_def.fields) == len(
        expected_fields
    ), f"Expected {len(expected_fields)} fields"

    for idx, (name, expected_type) in enumerate(expected_fields):
        field = struct_def.fields[idx]
        assert field.name == name, f"Expected field name '{name}', got '{field.name}'"
        assert (
            field.type.fullname == expected_type
        ), f"Expected type '{expected_type}' for field '{name}', got '{field.type.fullname}'"
        if name == "arr_func_ptr":
            assert field.elements == (
                3,
            ), f"Expected elements (3,) for 'arr_func_ptr', got {field.elements}"
        else:
            assert (
                field.elements == ()
            ), f"Expected scalar field for '{name}', got elements {field.elements}"

    validate_definitions(result)


def test_typedefs(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "typedefs.xml")
    )
    assert isinstance(result, list), "Expected list of definitions"
    validate_definitions(result)

    expected_typedefs = {
        "MyInt": ("int32_t", ()),
        "MyULong": ("uint32_t" if cxplat.windows else "uint64_t", ()),
        "FloatPtr": ("void*", ()),
        "FuncPtr": ("void*", ()),
        "PointPtr": ("void*", ()),
        "Shapes": (None, (10,)),
        "ShapesPtr": ("void*", ()),
        "Alias1": ("int32_t", ()),
        "Alias2": ("int32_t", ()),
        "Alias3": ("int32_t", ()),
        "IntArray1D": ("int32_t", (5,)),
        "IntArray2D": ("int32_t", (3, 4)),
        "IntArray3D": ("int32_t", (2, 3, 4)),
        "Alias1D": ("int32_t", (5,)),
        "Alias2D": ("int32_t", (3, 4)),
        "Alias3D": ("int32_t", (2, 3, 4)),
    }

    for name, (expected_type_name, expected_elements) in expected_typedefs.items():
        typedef = find_type_by_name(result, name)
        assert typedef is not None, f"Typedef {name} not found"
        if expected_type_name is not None:
            assert (
                typedef.type.fullname == expected_type_name
            ), f"{name}: expected definition '{expected_type_name}', got '{typedef.type.fullname}'"

        assert (
            typedef.elements == expected_elements
        ), f"{name}: expected elements {expected_elements}, got {typedef.elements}"

    validate_definitions(result)


def test_typedef_struct_inline(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "typedef_struct.xml")
    )

    assert isinstance(result, list), "Expected list of definitions"

    typedef = find_type_by_name(result, "Point")
    assert typedef is not None, "Typedef 'Point' not found"
    assert isinstance(typedef, TypedefDefinition), "'Point' is not a TypedefDefinition"
    assert typedef.type is not None, "'Point' typedef must have a definition"
    assert typedef.elements == (), "'Point' typedef should not have array dimensions"

    # Look for the struct that this typedef refers to
    struct_def = find_type_by_name(result, typedef.type.fullname)
    assert struct_def is not None, f"Struct '{typedef.type.fullname}' not found"
    assert isinstance(
        struct_def, ClassDefinition
    ), f"Expected ClassDefinition for '{typedef.type.fullname}'"
    assert len(struct_def.fields) == 1, "Struct should have exactly one field"
    assert struct_def.fields[0].name == "x"
    assert struct_def.fields[0].type.fullname == "int32_t"
    validate_definitions(result)


def test_namespaces(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "namespaces.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"

    # Top-level namespace
    a = find_type_by_name(result, "TopLevel::A")
    assert a is not None, "Struct TopLevel::A not found"
    assert (
        len(a.fields) == 1
        and a.fields[0].name == "x"
        and a.fields[0].type.fullname == "int32_t"
    )

    # Nested namespace
    b = find_type_by_name(result, "Outer::Inner::B")
    assert b is not None, "Struct Outer::Inner::B not found"
    assert (
        len(b.fields) == 1
        and b.fields[0].name == "y"
        and b.fields[0].type.fullname == "float"
    )

    # Anonymous namespace — ends with ::C
    C_anon_structs = [s for s in result if s.fullname.endswith("::C")]
    assert len(C_anon_structs) == 1, "Struct C (in anonymous namespace) not found"
    c = C_anon_structs[0]
    assert (
        len(c.fields) == 1
        and c.fields[0].name == "z"
        and c.fields[0].type.fullname == "double"
    )

    # Aggregator
    agg = find_type_by_name(result, "AllNamespaces")
    assert agg is not None, "Struct AllNamespaces not found"
    assert [f.name for f in agg.fields] == ["a", "b", "c"]
    assert agg.fields[0].type.fullname == "TopLevel::A"
    assert agg.fields[1].type.fullname == "Outer::Inner::B"
    assert agg.fields[2].type.fullname.endswith("::C")

    validate_definitions(result)


def test_std_types_pointers(cxplat):
    result = parse(
        os.path.join(
            here, os.pardir, "headers", cxplat.directory, "std_types_pointers.xml"
        ),
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    struct_a = find_type_by_name(result, "A")
    assert struct_a is not None, "Struct A not found"

    expected_fields = [
        ("v", "void*"),
        ("s", "void*"),
    ]

    assert len(struct_a.fields) == len(
        expected_fields
    ), f"Expected {len(expected_fields)} fields"

    for idx, (name, expected_type) in enumerate(expected_fields):
        field = struct_a.fields[idx]
        assert field.name == name, f"Expected field '{name}', got '{field.name}'"
        assert (
            field.type.fullname == expected_type
        ), f"Field '{name}' expected type '{expected_type}', got '{field.type.fullname}'"
        assert field.elements == (), f"Field '{name}' should not be an array"


def test_remove_unknown_behavior(cxplat):
    xml_path = os.path.join(
        here, os.pardir, "headers", cxplat.directory, "std_types.xml"
    )

    # ✅ Case: skip_failed_parsing and remove_unknown enabled — should work
    result = parse(xml_path, skip_failed_parsing=True, remove_unknown=True)

    validate_definitions(result)
    names = {d.name for d in result if hasattr(d, "name")}
    assert "B" in names, "Struct B should be present"

    #  Case: strict mode — allow error to propagate
    try:
        result = parse(xml_path, skip_failed_parsing=False, remove_unknown=False)

        assert False, "Expected exception due to unknown std::string"
    except Exception:
        pass  # Expected

    #  Case: skip_failed only — A skipped, B stays
    result = parse(xml_path, skip_failed_parsing=True, remove_unknown=False)
    names = {d.name for d in result if hasattr(d, "name")}
    assert "B" in names, "Struct B should be present in skip_failed mode"


def test_fixed_width_structs(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "fixed_width.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    expected_structs = {
        "A": [
            ("a1", "int8_t", ()),
            ("a2", "int16_t", ()),
            ("a3", "int32_t", ()),
            ("a4", "int64_t", ()),
            ("a5", "uint8_t", ()),
            ("a6", "uint16_t", ()),
            ("a7", "uint32_t", ()),
            ("a8", "uint64_t", ()),
        ],
        "B": [
            ("b1", "int8_t", ()),
            ("b2", "int16_t", ()),
            ("b3", "int32_t", ()),
            ("b4", "int64_t", ()),
            ("b5", "uint8_t", ()),
            ("b6", "uint16_t", ()),
            ("b7", "uint32_t", ()),
            ("b8", "uint64_t", ()),
        ],
        "C": [
            ("arr1", "int32_t", (4,)),
            ("arr2", "uint64_t", (2, 3)),
        ],
        "D": [
            ("d1", "uint16_t", (5, 6)),
        ],
    }

    for struct_name, expected_fields in expected_structs.items():
        s = find_type_by_name(result, struct_name)
        assert s is not None, f"Struct {struct_name} not found"
        assert len(s.fields) == len(
            expected_fields
        ), f"{struct_name}: Expected {len(expected_fields)} fields"

        for idx, (name, expected_type, elements) in enumerate(expected_fields):
            field = s.fields[idx]
            assert (
                field.name == name
            ), f"{struct_name}.{name}: expected name '{name}', got '{field.name}'"
            assert (
                field.type.fullname == expected_type
            ), f"{struct_name}.{name}: expected type '{expected_type}', got '{field.type.fullname}'"
            assert (
                field.elements == elements
            ), f"{struct_name}.{name}: expected elements {elements}, got {field.elements}"
            assert (
                isinstance(field.size_in_bits, int) and field.size_in_bits > 0
            ), f"{struct_name}.{name}: invalid size_in_bits"
        assert s.size > 0, f"{struct_name}: size must be positive"


def test_enums(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "enums.xml")
    )

    assert isinstance(result, list), "Expected list of definitions"
    validate_definitions(result)

    expected_enums = {
        "Color": {
            "size": 4,
            "values": {
                "Red": 0,
                "Green": 1,
                "Blue": 5,
                "Yellow": 6,
            },
        },
        "Direction": {
            "size": 4,
            "values": {
                "North": 0,
                "South": 1,
                "East": 2,
                "West": 3,
            },
        },
        "StatusCode": {
            "size": 1,
            "values": {
                "OK": 0,
                "Error": 1,
                "Timeout": 2,
                "Unknown": 255,
            },
        },
        "ErrorLevel": {
            "size": 2,
            "values": {
                "Info": 1,
                "Warning": 2,
                "Critical": 3,
            },
        },
    }

    for expected_name, enum_data in expected_enums.items():
        match = None
        for d in result:
            if isinstance(d, EnumDefinition) and (
                d.name == expected_name or d.name.startswith(expected_name)
            ):
                match = d
                break
        assert match is not None, f"Enum '{expected_name}' not found"
        assert (
            match.size == enum_data["size"]
        ), f"Enum '{match.name}' has incorrect size"
        parsed = {e.name: e.value for e in match.enums}
        assert parsed == enum_data["values"], f"Enum '{match.name}' values do not match"


def test_unions(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "unions.xml")
    )

    assert isinstance(result, list), "Expected list of class and union definitions"
    validate_definitions(result)

    # Test simple union
    u = find_type_by_name(result, "IntOrFloat")
    assert u is not None, "Union IntOrFloat not found"
    assert isinstance(u, UnionDefinition)
    assert len(u.fields) == 2
    assert set(f.name for f in u.fields) == {"i", "f"}

    # Test struct with named union
    packet = find_type_by_name(result, "Packet")
    assert packet is not None, "Struct Packet not found"
    assert isinstance(packet, ClassDefinition)
    assert any(
        f.name == "data" for f in packet.fields
    ), "Expected union field 'data' in Packet"

    # Test struct with anonymous union
    mixed = find_type_by_name(result, "Mixed")
    assert mixed is not None, "Struct Mixed not found"
    assert isinstance(mixed, ClassDefinition)
    anon = find_type_by_name(result, mixed.fields[1].type.fullname)
    assert anon is not None, "Mixed anon union not found"
    assert set(f.name for f in anon.fields).intersection(
        {"d", "l"}
    ), "Missing anonymous union fields in Mixed"

    # Test nested union
    nested_union = find_type_by_name(result, "NestedUnion")
    assert nested_union is not None, "NestedUnion not found"
    assert isinstance(nested_union, UnionDefinition)
    assert any(
        "nested" in f.name for f in nested_union.fields
    ), "Missing nested struct in NestedUnion"

    # Test deep union
    deep = find_type_by_name(result, "DeepUnion")
    assert deep is not None, "DeepUnion not found"
    assert isinstance(deep, UnionDefinition)
    assert any(
        "structured" in f.name for f in deep.fields
    ), "Missing structured field in DeepUnion"


def test_bitfields(cxplat):
    result = parse(
        os.path.join(
            here, os.pardir, "headers", cxplat.directory, "bitfields_basic.xml"
        )
    )

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    s = find_type_by_name(result, "StatusFlags")
    assert s is not None, "Struct StatusFlags not found"
    assert isinstance(s, ClassDefinition)

    expected_fields = [
        ("ready", "uint32_t", 1, True),
        ("error", "uint32_t", 1, True),
        ("reserved", "uint32_t", 6, True),
    ]

    assert len(s.fields) == len(
        expected_fields
    ), f"Expected {len(expected_fields)} fields"

    for idx, (name, expected_type, size_in_bits, bitfield) in enumerate(
        expected_fields
    ):
        f = s.fields[idx]
        assert f.name == name, f"Field {idx} expected name '{name}', got '{f.name}'"
        assert (
            f.type.fullname == expected_type
        ), f"Field '{name}' expected type '{expected_type}', got '{f.type.fullname}'"
        assert (
            f.size_in_bits == size_in_bits
        ), f"Field '{name}' expected size {size_in_bits}, got {f.size_in_bits}"
        assert (
            f.bitfield == bitfield
        ), f"Field '{name}' expected bitfield={bitfield}, got {f.bitfield}"


def test_bitfields_complex(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "bitfields.xml")
    )

    assert isinstance(result, list), "Expected list of class definitions"
    validate_definitions(result)

    # --- StatusFlags ---
    status = find_type_by_name(result, "StatusFlags")
    assert status is not None and len(status.fields) == 3
    assert [
        (f.name, f.type.fullname, f.size_in_bits, f.bitfield) for f in status.fields
    ] == [
        ("ready", "uint32_t", 1, True),
        ("error", "uint32_t", 1, True),
        ("reserved", "uint32_t", 6, True),
    ]

    # --- ControlRegister ---
    ctrl = find_type_by_name(result, "ControlRegister")
    assert ctrl is not None and len(ctrl.fields) == 4
    assert [
        (f.name, f.type.fullname, f.size_in_bits, f.bitfield) for f in ctrl.fields
    ] == [
        ("mode", "uint32_t", 3, True),
        ("speed", "int32_t", 5, True),
        ("enable", "uint32_t", 1, True),
        ("reserved", "uint32_t", 23, True),
    ]

    # --- Packed32 ---
    packed = find_type_by_name(result, "Packed32")
    assert packed is not None and len(packed.fields) == 4
    assert [(f.name, f.size_in_bits) for f in packed.fields] == [
        ("a", 8),
        ("b", 8),
        ("c", 8),
        ("d", 8),
    ]

    # --- Nested ---
    nested = find_type_by_name(result, "Nested")
    assert nested is not None
    outer_field = next((f for f in nested.fields if f.name == "outer"), None)
    inner_field = next((f for f in nested.fields if f.name == "inner"), None)
    assert (
        outer_field is not None
        and outer_field.size_in_bits == 4
        and outer_field.bitfield
    )

    # --- Flat ---
    flat = find_type_by_name(result, "Flat")
    assert flat is not None
    field_names = set(f.name for f in flat.fields)
    assert "top" in field_names

    nested = find_type_by_name(result, flat.fields[1].type.fullname)
    assert nested is not None, "Nested struct not found"
    assert nested.fields[1].name == "raw", "Nested raw field not found"

    nested2 = find_type_by_name(result, nested.fields[0].type.fullname)
    assert nested2 is not None, "Nested inner struct not found"
    assert nested2.fields[0].name == "u1"
    assert nested2.fields[0].bitfield is True
    assert nested2.fields[0].size_in_bits == 3
    assert nested2.fields[1].name == "u2"
    assert nested2.fields[1].bitfield is True
    assert nested2.fields[1].size_in_bits == 5


def test_constants(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "constants.xml")
    )

    assert isinstance(result, list), "Expected list of definitions"
    validate_definitions(result)

    expected_constants = {
        "buffer_size": ("int32_t", 256),
        "max_address": ("uint64_t", 281474976710655),
        "newline": ("int8_t", "\n"),
        "pi": ("float", 3.14159012),
        "e": ("double", 2.7182818279999998),
        "null_ptr": ("void*", 0),
    }

    for name, (expected_type, expected_value) in expected_constants.items():
        const = find_type_by_name(result, name)
        assert const is not None, f"Constant '{name}' not found"
        assert isinstance(
            const, ConstantDefinition
        ), f"{name} is not a ConstantDefinition"
        assert (
            const.type.fullname == expected_type
        ), f"{name}: expected type '{expected_type}', got '{const.type.fullname}'"
        assert (
            const.value == expected_value
        ), f"{name}: expected value '{expected_value}', got '{const.value}'"


def test_struct_packing(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "packing.xml")
    )

    assert isinstance(result, list), "Expected list of definitions"
    validate_definitions(result)

    expected_structs = {
        "DefaultAlign": (4, 8),  # default alignment and padded size
        "Packed1": (1, 5),  # tightly packed: 1 + 4 = 5
        "Packed2": (2, 6),  # 1 + 1 (padding) + 4 = 6
        "Packed4": (4, 8),  # same layout as default on 4-byte alignment
    }

    for name, (expected_align, expected_size) in expected_structs.items():
        struct = find_type_by_name(result, name)
        assert struct is not None, f"Struct '{name}' not found"
        assert (
            struct.alignment == expected_align
        ), f"{name}: expected alignment {expected_align}, got {struct.alignment}"
        assert (
            struct.size == expected_size
        ), f"{name}: expected size {expected_size}, got {struct.size}"


def test_all_basic_types_struct(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "all_types.xml"),
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    assert isinstance(result, list), "Expected list of definitions"
    validate_definitions(result)

    struct = find_type_by_name(result, "AllTypes")
    assert struct is not None, "Struct AllTypes not found"
    assert isinstance(struct, ClassDefinition)

    # Allow platform-dependent width aliases
    def is_equiv(actual_type, expected):
        actual = actual_type.fullname
        if isinstance(expected, (tuple, list)):
            return actual in expected
        return actual == expected

    expected_fields = [
        ("ch", "int8_t"),
        ("sch", "int8_t"),
        ("uch", "uint8_t"),
        ("wch", ("int32_t", "uint32_t", "int16_t")),
        ("ch16", ("int16_t", "uint16_t")),
        ("ch32", ("int32_t", "uint32_t")),
        ("b2", "uint8_t"),
        ("s", "int16_t"),
        ("us", "uint16_t"),
        ("i", "int32_t"),
        ("ui", "uint32_t"),
        ("l", "int32_t" if cxplat.windows else "int64_t"),
        ("ul", "uint32_t" if cxplat.windows else "uint64_t"),
        ("ll", "int64_t"),
        ("ull", "uint64_t"),
        ("i8", "int8_t"),
        ("ui8", "uint8_t"),
        ("i16", "int16_t"),
        ("ui16", "uint16_t"),
        ("i32", "int32_t"),
        ("ui32", "uint32_t"),
        ("i64", "int64_t"),
        ("ui64", "uint64_t"),
        ("f", "float"),
        ("d", "double"),
        ("ld", "long double"),
        ("ptr", "void*"),
    ]

    assert len(struct.fields) == len(
        expected_fields
    ), f"Expected {len(expected_fields)} fields, got {len(struct.fields)}"

    for idx, (name, expected_type) in enumerate(expected_fields):
        field = struct.fields[idx]
        assert (
            field.name == name
        ), f"Field {idx} name mismatch: expected '{name}', got '{field.name}'"
        assert is_equiv(
            field.type, expected_type
        ), f"Field '{name}' type mismatch: expected '{expected_type}', got '{field.type.fullname}'"
        assert (
            isinstance(field.size_in_bits, int) and field.size_in_bits > 0
        ), f"Field '{name}' has invalid size"


def test_includes(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "includes.xml"),
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    assert isinstance(result, list), "Expected list of definitions"
    validate_definitions(result)

    struct = find_type_by_name(result, "TestStruct")
    assert struct is not None, "Struct TestStruct not found"
    assert isinstance(struct, ClassDefinition)
    assert len(struct.fields) == 1, "Expected 1 field in TestStruct"

    field = struct.fields[0]
    assert field.name == "id", f"Expected field name 'id', got '{field.name}'"
    assert (
        field.type.fullname == "int32_t"
    ), f"Expected type 'int32_t', got '{field.type.fullname}'"
    assert field.elements == (), "Expected no array elements"
    assert (
        isinstance(field.size_in_bits, int) and field.size_in_bits > 0
    ), "Invalid size_in_bits"
    assert not field.bitfield, "Expected 'id' not to be a bitfield"
