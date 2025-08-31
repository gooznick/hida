import os
import tempfile
import subprocess
import pytest
import sys
here = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(here, os.pardir))
from cast_xml_parse import parse
from data_helpers import *
from manipulate import *
from header_gen import write_header_from_definitions

here = os.path.dirname(__file__)

def load_convert_compile_header(header_basename: str, cxplat):
    xml_path = os.path.join(here, os.pardir, "headers", cxplat.directory, header_basename)

    # Parse
    result = parse(xml_path, use_bool=True, skip_failed_parsing=True, remove_unknown=True)
    result = filter_by_source_regexes(result, exclude=get_system_include_regexes())
    validate_definitions(result)

    header_code = write_header_from_definitions(result)
    assert header_code.strip(), "Generated header is empty"

    # Sanity: check that some type names appear in the header
    type_names = [d.name for d in result if isinstance(d, (ClassDefinition, UnionDefinition, EnumDefinition))]
    if type_names:
        for name in type_names[:5]:  # Check presence of first few
            assert name in header_code, f"Expected type name '{name}' not found in generated header"

    with tempfile.TemporaryDirectory() as tmpdir:
        header_file = os.path.join(tmpdir, "generated.h")
        cpp_file = os.path.join(tmpdir, "check_compile.cpp")

        with open(header_file, "w") as f:
            f.write(header_code)

        with open(cpp_file, "w") as f:
            f.write('#include "generated.h"\nint main() { return 0; }\n')

        try:
            subprocess.run(
                ["g++", "-std=c++17", "-fsyntax-only", cpp_file],
                check=True,
                stderr=subprocess.PIPE,
                cwd=tmpdir
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"g++ compilation failed:\n{e.stderr.decode()}")

    return result


@pytest.mark.parametrize("filename", [
    "basic.xml",
    "class.xml",
    "basic_types.xml",
    "typedefs.xml",
    "typedef_struct.xml",
    "pointers.xml",
    "arrays.xml",
    "unions.xml",
    "enums.xml",
    "constants.xml",
    "bitfields.xml",
    "bitfields_basic.xml",
    "fixed_width.xml",
    "complicated.xml",
])
def test_generated_header_compiles(filename, cxplat):
    load_convert_compile_header(filename, cxplat)
