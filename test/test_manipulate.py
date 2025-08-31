import os
import pytest
from typing import List
from pathlib import Path, PurePath
import re
import pytest

from hida import (
    parse,
    find_type_by_name,
    validate_definitions,
    filter_by_source_regexes,
    fill_bitfield_holes_with_padding,
    fill_struct_holes_with_padding_bytes,
    flatten_namespaces,
    resolve_typedefs,
    filter_connected_definitions,
    DefinitionBase,
    ClassDefinition,
    UnionDefinition,
    flatten_structs,
    remove_enums,
    remove_source,
)

here = os.path.dirname(__file__)


def test_fill_bitfield_holes_with_padding(cxplat):
    # Parse the header
    result = parse(
        os.path.join(
            here, os.pardir, "headers", cxplat.directory, "bitfield_holes.xml"
        ),
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    # Find the "Holey" struct before filling
    holey = find_type_by_name(result, "Holey")
    assert holey is not None and isinstance(holey, ClassDefinition)

    # Count original bitfields
    orig_fields = [f for f in holey.fields if f.bitfield]
    assert len(orig_fields) == 3, "Expected 3 original bitfields in Holey"

    # Apply the padding filler
    filled = fill_bitfield_holes_with_padding(result)

    # Find the struct again (in-place modified)
    holey_filled = find_type_by_name(filled, "Holey")

    # Verify padding was inserted
    bitfields = [f for f in holey_filled.fields if f.bitfield]
    assert len(bitfields) > 3, "Padding bitfields were not inserted"

    # Look for the synthetic padding field
    pads = [f for f in bitfields if f.name.startswith("__pad")]
    assert len(pads) >= 1, "Expected at least one __pad field"

    # Verify the pad fills the correct hole
    assert any(
        p.size_in_bits == 23 for p in pads
    ), "Expected 23-bit padding in Holey struct"

    # Also check Packed has no padding
    packed = find_type_by_name(result, "Packed")
    before = len(packed.fields)
    fill_bitfield_holes_with_padding([packed])
    after = len(packed.fields)
    assert before == after, "No padding should be inserted into Packed"

    validate_definitions(result)


def test_fill_struct_holes_with_padding_bytes_multiple_structs(cxplat):
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "holes_real.xml"),
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    filled_defs = fill_struct_holes_with_padding_bytes(result)

    # --- Holey Struct ---
    holey = find_type_by_name(filled_defs, "Holey")
    assert holey is not None and isinstance(holey, ClassDefinition)

    pads = [f for f in holey.fields if f.name.startswith("__pad")]
    assert pads, "Expected padding in 'Holey'"
    assert any(
        p.elements == (3,) or p.elements == () for p in pads
    ), "Expected 3-byte padding field"
    assert any(
        p.elements == (2,) or p.elements == () for p in pads
    ), "Expected 2-byte trailing padding"

    # --- Packed Struct ---
    packed = find_type_by_name(filled_defs, "Packed")
    assert packed is not None and isinstance(packed, ClassDefinition)
    assert not any(
        f.name.startswith("__pad") for f in packed.fields
    ), "No padding should be added to 'Packed'"

    # --- MultiHoles Struct ---
    multi = find_type_by_name(filled_defs, "MultiHoles")
    assert multi is not None and isinstance(multi, ClassDefinition)

    pads = [f for f in multi.fields if f.name.startswith("__pad")]
    assert pads, "Expected padding in 'MultiHoles'"
    assert any(
        p.size_in_bits % 8 == 0 for p in pads
    ), "All padding fields should be byte aligned"

    # Sanity checks
    for struct in [holey, multi]:
        for field in struct.fields:
            assert isinstance(field.size_in_bits, int) and field.size_in_bits > 0
            assert not field.bitfield
            if field.name.startswith("__pad"):
                assert field.type.fullname == "uint8_t"
                assert isinstance(field.elements, tuple)


def test_flatten_namespaces(cxplat):
    result = parse(
        os.path.join(
            here, os.pardir, "headers", cxplat.directory, "namespaced_types.xml"
        ),
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    # Full flatten
    flattened = flatten_namespaces(result)
    names = {d.name for d in flattened}
    assert "Alpha__Data" in names
    assert "Beta__Data" in names
    assert "Beta__Extra" in names
    assert all(d.namespace == () for d in flattened)


def test_resolve_typedefs(cxplat):
    result = parse(
        os.path.join(
            here, os.pardir, "headers", cxplat.directory, "typedef_remove.xml"
        ),
        skip_failed_parsing=True,
        remove_unknown=True,
    )

    resolved = resolve_typedefs(result)

    a = find_type_by_name(resolved, "A")
    assert a is not None and isinstance(a, ClassDefinition)

    expected = {
        "value": ("int32_t", ()),
        "arr1": ("float", (4,)),
        "arr2": ("float", (3, 4)),
    }

    for f in a.fields:
        base_type = f.type.fullname
        dims = f.elements
        assert f.name in expected, f"Unexpected field: {f.name}"
        exp_type, exp_dims = expected[f.name]
        assert (
            base_type == exp_type
        ), f"{f.name}: expected type {exp_type}, got {base_type}"
        assert dims == exp_dims, f"{f.name}: expected dims {exp_dims}, got {dims}"

    # Ensure typedefs are removed
    names = {d.name for d in resolved}
    assert "MyInt" not in names
    assert "Alias1" not in names
    assert "Alias2" not in names
    assert "MyArray" not in names
    assert "MyArray2D" not in names


@pytest.fixture
def sample_definitions() -> List[DefinitionBase]:
    return [
        DefinitionBase("A", (), "/usr/include/stdio.h"),
        DefinitionBase("B", (), "/home/user/project/foo.h"),
        DefinitionBase("C", (), "C:\\Program Files\\Microsoft SDKs\\bar.h"),
        DefinitionBase("D", (), "/usr/local/include/something.h"),
        DefinitionBase("E", (), "D:\\MyLib\\custom\\baz.h"),
    ]


def test_include_regex(sample_definitions):
    # Include only user/project headers
    result = filter_by_source_regexes(sample_definitions, include=r"/home/user/")
    assert len(result) == 1
    assert result[0].name == "B"


def test_exclude_regex(sample_definitions):
    # Exclude system headers (Linux-style)
    result = filter_by_source_regexes(sample_definitions, exclude=r"^/usr/include/")
    assert all(d.name != "A" for d in result)


def test_no_filters(sample_definitions):
    # No filtering: return all
    result = filter_by_source_regexes(sample_definitions)
    assert len(result) == len(sample_definitions)


def test_include_as_list(sample_definitions):
    # List of includes: both user and system headers
    result = filter_by_source_regexes(
        sample_definitions, include=[r"/usr/", r"/home/user/"]
    )
    names = [d.name for d in result]
    assert "A" in names and "B" in names


def test_filter_connected_definitions(cxplat):
    path = os.path.join(
        here, os.pardir, "headers", cxplat.directory, "connected_filter.xml"
    )
    all_defs = parse(path, skip_failed_parsing=True, remove_unknown=True)
    validate_definitions(all_defs)

    # Prune everything except what's needed by Main
    connected = filter_connected_definitions(all_defs, "Main")

    # We expect the following types to remain
    expected_types = {"Main", "Payload", "Wrapper", "Nested", "Status"}

    remaining_names = {d.fullname for d in connected}
    assert expected_types.issubset(
        remaining_names
    ), f"Missing expected types: {expected_types - remaining_names}"

    # Ensure unrelated types are not included
    assert (
        "Unused" not in remaining_names
    ), "Disconnected type 'Unused' should have been removed"


HERE = Path(__file__).parent
XML_DIR = HERE / "xml"


def _get_struct(defs, name: str):
    for d in defs:
        if isinstance(d, (ClassDefinition, UnionDefinition)):
            if d.name == name or d.fullname.endswith(name):
                return d
    raise AssertionError(f"Struct/union {name} not found in defs")


def _field_names(defn):
    return [f.name for f in defn.fields]


# -----------------------------
# flatten_structs manipulator
# -----------------------------
def test_flatten_structs_basic(cxplat):
    path = os.path.join(here, os.pardir, "headers", cxplat.directory, "flatten.xml")
    defs = parse(path, skip_failed_parsing=True, remove_unknown=True)
    validate_definitions(defs)

    # Sanity before: Wrapper has a composite field `inner`
    wrapper = _get_struct(defs, "Wrapper")
    assert any(
        f.name == "inner" for f in wrapper.fields
    ), "Expected composite field 'inner' before flattening"

    # Apply flattening on just Wrapper
    defs2 = flatten_structs(defs, targets=["Wrapper"])  # or ["demo::Wrapper"]

    wrapper2 = _get_struct(defs2, "Wrapper")
    names2 = _field_names(wrapper2)

    # After: `inner` field should be replaced by `inner__a` and `inner__b`
    assert "inner" not in names2, "Composite field should be flattened and removed"
    assert "inner__a" in names2, "Flattened member missing: inner__a"
    assert "inner__b" in names2, "Flattened member missing: inner__b"

    # x and y should still be present
    assert "x" in names2 and "y" in names2

    # The array-of-struct example should remain unflattened by default
    wrapper_arr = _get_struct(defs2, "WrapperArr")
    assert any(
        f.name == "items" for f in wrapper_arr.fields
    ), "Array field should remain unless flatten_arrays=True"


def _get_struct(defs, name_or_suffix: str):
    for d in defs:
        if isinstance(d, (ClassDefinition, UnionDefinition)):
            if d.name == name_or_suffix or d.fullname.endswith(name_or_suffix):
                return d
    raise AssertionError(f"Struct/union {name_or_suffix} not found")


def _field_names(defn):
    return [f.name for f in defn.fields]


# -----------------------------
# flatten_structs – extra coverage
# -----------------------------


def test_flatten_structs_fullname_and_separator(cxplat):
    """Flatten by fullname and with a custom separator."""
    path = os.path.join(here, os.pardir, "headers", cxplat.directory, "flatten.xml")
    defs = parse(path, skip_failed_parsing=True, remove_unknown=True)
    validate_definitions(defs)

    # Use fullname (namespace)::Wrapper if present
    # We allow either exact or suffix match “::Wrapper”
    target_fullname = None
    for d in defs:
        if isinstance(d, (ClassDefinition, UnionDefinition)) and d.name == "Wrapper":
            target_fullname = d.fullname
            break
    assert target_fullname is not None

    defs2 = flatten_structs(defs, targets=[target_fullname], separator="__FL__")
    wrapper2 = _get_struct(defs2, "Wrapper")
    names2 = _field_names(wrapper2)

    assert "inner" not in names2
    assert "inner__FL__a" in names2
    assert "inner__FL__b" in names2
    assert "x" in names2 and "y" in names2


def test_flatten_structs_arrays_offsets(cxplat):
    """
    When flattening arrays of composites (flatten_arrays=True), we expect:
      - original array field removed
      - per-element fields with index suffixes present
      - bitoffsets differ by struct element stride (size_in_bits of Inner)
    """
    path = os.path.join(here, os.pardir, "headers", cxplat.directory, "flatten.xml")
    defs = parse(path, skip_failed_parsing=True, remove_unknown=True)
    validate_definitions(defs)

    inner = _get_struct(defs, "Inner")
    inner_stride_bits = inner.size * 8  # size is in bytes

    defs2 = flatten_structs(defs, targets=["WrapperArr"], flatten_arrays=True)
    warr = _get_struct(defs2, "WrapperArr")
    names = _field_names(warr)

    # original array field should be gone
    assert "items" not in names

    # flattened element fields must exist
    need = ["items_0___a", "items_0___b", "items_1___a", "items_1___b"]
    for n in need:
        assert n in names, f"missing flattened array member {n}"

    # Check offsets stride between [0] and [1]
    f_by_name = {f.name: f for f in warr.fields}
    off_a0 = f_by_name["items_0___a"].bitoffset
    off_a1 = f_by_name["items_1___a"].bitoffset
    off_b0 = f_by_name["items_0___b"].bitoffset
    off_b1 = f_by_name["items_1___b"].bitoffset

    assert off_a1 - off_a0 == inner_stride_bits, "wrong stride for items[*]__a"
    assert off_b1 - off_b0 == inner_stride_bits, "wrong stride for items[*]__b"


# -----------------------------
# remove_enums manipulator
# -----------------------------
def test_remove_enums_basic(cxplat):
    path = os.path.join(here, os.pardir, "headers", cxplat.directory, "flat_enum.xml")
    defs = parse(path, skip_failed_parsing=True, remove_unknown=True)

    # Confirm the enum exists before transformation
    enum_names_before = {
        d.fullname for d in defs if d.__class__.__name__ == "EnumDefinition"
    }
    assert any(
        n.endswith("Color") for n in enum_names_before
    ), "Expected an EnumDefinition 'Color' before removal"

    # Apply removal
    defs2 = remove_enums(defs)

    # All enums should be gone
    enum_names_after = {
        d.fullname for d in defs2 if d.__class__.__name__ == "EnumDefinition"
    }
    assert (
        not enum_names_after
    ), f"Enum definitions remain after remove_enums: {enum_names_after}"

    # Fields that used to be enums should now be integer-typed (not the enum name)
    uses = _get_struct(defs2, "UsesColor")
    fields = {f.name: f for f in uses.fields}

    assert "c1" in fields and "c2" in fields and "n" in fields

    # Their TypeBase name should no longer be 'Color' (or namespaced Color)
    for fname in ("c1", "c2"):
        tname = fields[fname].type.name
        assert (
            "Color" not in tname
        ), f"{fname} still has enum name after remove_enums (got type {tname})"

    # And the plain byte field remains unchanged
    assert fields["n"].type.name in {
        "uint8_t",
        "unsigned char",
        "unsigned char __attribute__((__vector_size__(1)))",
    }


@pytest.mark.parametrize(
    "xml_name,struct_name",
    [
        ("flatten.xml", "Wrapper"),
        ("flat_enum.xml", "UsesColor"),
    ],
)
def test_remove_source_default_empties_source(cxplat, xml_name, struct_name):
    path = os.path.join(here, os.pardir, "headers", cxplat.directory, xml_name)
    defs = parse(path, skip_failed_parsing=True, remove_unknown=True)
    validate_definitions(defs)

    target = _get_struct(defs, struct_name)
    before = target.source
    # sanity: usually a path; allow empty in rare cases
    assert before is not None

    defs2 = remove_source(defs)  # default -> empty string
    target2 = _get_struct(defs2, struct_name)
    assert target2.source == "", "remove_source() should blank out source by default"


@pytest.mark.parametrize(
    "xml_name,struct_name",
    [
        ("flatten.xml", "Wrapper"),
        ("flat_enum.xml", "UsesColor"),
    ],
)
def test_remove_source_header_only_keeps_basename(cxplat, xml_name, struct_name):
    path = os.path.join(here, os.pardir, "headers", cxplat.directory, xml_name)
    defs = parse(path, skip_failed_parsing=True, remove_unknown=True)
    validate_definitions(defs)

    target = _get_struct(defs, struct_name)
    before = (target.source or "").strip().strip('"').strip("'")
    expected = (
        before
        if (before.startswith("<") and before.endswith(">"))
        else (PurePath(before).name if before else "")
    )

    defs2 = remove_source(defs, header_only=True)
    target2 = _get_struct(defs2, struct_name)
    assert (
        target2.source == expected
    ), f"expected basename '{expected}', got '{target2.source}'"
