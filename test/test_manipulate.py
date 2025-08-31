from manipulate import *
from data import *
from data_helpers import *
from cast_xml_parse import CastXmlParse, parse

import os
import pytest


here = os.path.dirname(__file__)

def test_fill_bitfield_holes_with_padding(cxplat):
    # Parse the header
    result = parse(
        os.path.join(here, os.pardir, "headers", cxplat.directory, "bitfield_holes.xml"),
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
    assert any(p.size_in_bits == 23 for p in pads), "Expected 23-bit padding in Holey struct"

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
    assert any(p.elements == (3,) or p.elements == () for p in pads), "Expected 3-byte padding field"
    assert any(p.elements == (2,) or p.elements == () for p in pads), "Expected 2-byte trailing padding"

    # --- Packed Struct ---
    packed = find_type_by_name(filled_defs, "Packed")
    assert packed is not None and isinstance(packed, ClassDefinition)
    assert not any(f.name.startswith("__pad") for f in packed.fields), "No padding should be added to 'Packed'"

    # --- MultiHoles Struct ---
    multi = find_type_by_name(filled_defs, "MultiHoles")
    assert multi is not None and isinstance(multi, ClassDefinition)

    pads = [f for f in multi.fields if f.name.startswith("__pad")]
    assert pads, "Expected padding in 'MultiHoles'"
    assert any(p.size_in_bits % 8 == 0 for p in pads), "All padding fields should be byte aligned"

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
        os.path.join(here, os.pardir, "headers", cxplat.directory, "namespaced_types.xml"),
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
        os.path.join(here, os.pardir, "headers", cxplat.directory, "typedef_remove.xml"),
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
        assert base_type == exp_type, f"{f.name}: expected type {exp_type}, got {base_type}"
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
    result = filter_by_source_regexes(sample_definitions, include=[r"/usr/", r"/home/user/"])
    names = [d.name for d in result]
    assert "A" in names and "B" in names

def test_filter_connected_definitions(cxplat):
    path = os.path.join(here, os.pardir, "headers", cxplat.directory, "connected_filter.xml")
    all_defs = parse(path, skip_failed_parsing=True, remove_unknown=True)
    validate_definitions(all_defs)

    # Prune everything except what's needed by Main
    connected = filter_connected_definitions(all_defs, "Main")

    # We expect the following types to remain
    expected_types = {"Main", "Payload", "Wrapper", "Nested", "Status"}

    remaining_names = {d.fullname for d in connected}
    assert expected_types.issubset(remaining_names), f"Missing expected types: {expected_types - remaining_names}"

    # Ensure unrelated types are not included
    assert "Unused" not in remaining_names, "Disconnected type 'Unused' should have been removed"
