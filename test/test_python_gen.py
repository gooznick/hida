import os
import tempfile
import importlib.util
import pytest
from cast_xml_parse import CastXmlParse, parse
from data_helpers import *
from manipulate import *
from python_gen import *
here = os.path.dirname(__file__)

def load_and_verify_header(header_basename: str, use_bool=True, skip_failed_parsing=True, remove_unknown=True):
    """
    Loads, converts, and verifies a header by its base XML filename.
    """
    header_path = os.path.join(here, os.pardir, "headers", "castxml", header_basename)
    result = parse(header_path, use_bool=use_bool, skip_failed_parsing=skip_failed_parsing, remove_unknown=remove_unknown)

    assert isinstance(result, list), f"{header_basename} parsing did not return a list"
    
    result = filter_by_source_regexes(result, exclude=get_system_include_regexes())
    
    validate_definitions(result)

    code = generate_python_code_from_definitions(result, assert_size=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "generated.py")
        write_code_to_file(code, py_file)

        spec = importlib.util.spec_from_file_location("generated_module", py_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        verify_struct_sizes([d for d in result if isinstance(d, (ClassDefinition, UnionDefinition))], module)

    return result  # Optionally return parsed result

@pytest.mark.parametrize("filename", [
    "basic.xml",
    "class.xml",
    "basics.xml",
    "basic_types.xml",
    "typedefs.xml",
    "typedef_struct.xml",
    "namespaces.xml",
    "pointers.xml",
    "std_types_pointers.xml",
    "arrays.xml",
    "enums.xml",
    "constants.xml",
    "all_types.xml",
    "includes.xml",
    "unions.xml",
    "bitfields.xml",
    "bitfields_basic.xml",
    "holes_real.xml",
    "fixed_width.xml",
    "typedefs_remove.xml",
    "complicated.xml",
])
def test_header_xml_to_python_and_verify(filename):
    load_and_verify_header(filename)
