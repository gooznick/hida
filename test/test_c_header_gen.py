import os
import tempfile
import subprocess
import sys
import pytest

here = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(here, os.pardir))

from hida import parse, validate_definitions, filter_by_source_regexes, get_system_include_regexes,  write_c_header_from_definitions
from hida import EnumDefinition, ClassDefinition


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
    "typedef_remove.xml",
    "complicated.xml",
])
def test_c_header_generation(filename, cxplat):
    xml_path = os.path.join(here, os.pardir, "headers", cxplat.directory, filename)
    definitions = parse(xml_path, skip_failed_parsing=True, remove_unknown=True)
    definitions = filter_by_source_regexes(definitions, exclude=get_system_include_regexes())
    validate_definitions(definitions)

    # Generate the header
    header_code = write_c_header_from_definitions(definitions)
    assert "#pragma once" in header_code
    
    enums = bool([d for d in definitions if isinstance(d, EnumDefinition)])
    classes = bool([d for d in definitions if isinstance(d, ClassDefinition)])
    assert not classes or any("typedef struct" in line for line in header_code.splitlines()), "No struct defined"
    assert not enums or  any("typedef enum" in line for line in header_code.splitlines()) or "enum" not in header_code, "No enum defined"

    with tempfile.TemporaryDirectory() as tmpdir:
        header_path = os.path.join(tmpdir, "generated.h")
        source_path = os.path.join(tmpdir, "main.c")

        with open(header_path, "w") as f:
            f.write(header_code)

        with open(source_path, "w") as f:
            f.write('#include "generated.h"\n')
            f.write("int main() { return 0; }\n")

        result = subprocess.run(
            ["gcc", "-std=c99", "-Wall", "-Werror", source_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tmpdir,
        )

        if result.returncode != 0:
            raise AssertionError(f"C compilation failed for {filename}:\n" + result.stderr.decode())
