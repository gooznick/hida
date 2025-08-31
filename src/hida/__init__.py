"""
Public API for hida.

Stable surface:
- Classes: DefinitionBase, ClassDefinition, UnionDefinition, ...
- Functions: parse_xml, emit_header, emit_python, convert
"""

# Re-export selected items so users can: `from hida import X`

from .core import parse
from .data_helpers import validate_definitions, find_type_by_name
from .data import *
from .manipulate import filter_by_source_regexes, get_system_include_regexes, fill_bitfield_holes_with_padding, fill_struct_holes_with_padding_bytes, flatten_namespaces, resolve_typedefs, filter_connected_definitions

from .c_header_gen import write_c_header_from_definitions
from .header_gen import write_header_from_definitions
from .python_gen import generate_python_code_from_definitions, write_code_to_file, verify_struct_sizes

__all__ = [
    # functions
    "parse",
    # data_helpers
    "validate_definitions", "find_type_by_name",
    # manipulate
    "filter_by_source_regexes", "get_system_include_regexes", "fill_bitfield_holes_with_padding",
    "fill_struct_holes_with_padding_bytes", "flatten_namespaces", "resolve_typedefs", "filter_connected_definitions",
    # header_gen
    "write_header_from_definitions",
    # c_header_gen
    "write_c_header_from_definitions",    
    # python_gen
    "generate_python_code_from_definitions", "write_code_to_file", "verify_struct_sizes",
    # data
    "DefinitionBase", "ClassDefinition", "UnionDefinition", "StructDefinition",
    "EnumDefinition", "TypedefDefinition", "FunctionDefinition", "ConstantDefinition",
    
]
