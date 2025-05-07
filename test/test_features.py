import sys
import os

here = os.path.dirname(__file__)

sys.path.insert(0, os.path.join(here, os.pardir))

from cast_xml_parse import parse
from data import *
from data_helpers import *

def test_basic():
    # Parse XML
    result = parse(os.path.join(here, os.pardir, 'headers' , 'castxml', 'basic.xml'))

    # Basic assertions (assuming _parse sets self.data to list of ClassDefinition)
    assert isinstance(result, list), "Expected list of class definitions"
    struct_a = find_type_by_name(result, "A")
    assert struct_a, "Struct A not found"
    assert len(struct_a.fields) == 2, "Expected 2 fields"
    assert struct_a.fields[0].name == "i" and struct_a.fields[0].c_type == "int"
    assert struct_a.fields[1].name == "f" and struct_a.fields[1].c_type == "float"
