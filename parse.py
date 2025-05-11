import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import re

CHAR_BIT = 8


@dataclass
class Field:
    name: str
    type: str
    elements: List[int]
    bitoffset: int
    size_in_bits: int = 0
    bitfield: bool = False


@dataclass
class ClassDefinition:
    name: str = ""
    alignment: int = 0
    fields: List[Field] = field(default_factory=list)
    size: int = 0


@dataclass
class EnumName:
    name: str
    value: int


@dataclass
class EnumDefinition:
    name: str = ""
    size: int = 0
    enums: List[EnumName] = field(default_factory=list)


@dataclass
class UnionDefinition:
    name: str = ""
    alignment: int = 0
    fields: List[Field] = field(default_factory=list)
    size: int = 0


@dataclass
class TypedefDefinition:
    name: str = ""
    definition: str = ""


def parse_xml(xml_file: str) -> ET.Element:
    tree = ET.parse(xml_file)
    return tree.getroot()


def get_element_dict(root: ET.Element) -> Dict[str, ET.Element]:
    return {elem.attrib["id"]: elem for elem in root}


def is_system_header(file_name: str) -> bool:
    system_paths = [
        "/usr/",
        "/x86_64-linux-gnu/",
        "/castxml/",
        "<built-in>",
        "<command-line>",
        "<builtin>",
    ]
    return any(p in file_name for p in system_paths)


def filter_out_system_headers(elements: Dict[str, ET.Element]) -> Dict[str, ET.Element]:
    return elements
    system_file_ids = set()
    for elem_id, elem in elements.items():
        if elem.tag == "File":
            file_name = elem.attrib.get("name", "")
            if is_system_header(file_name):
                system_file_ids.add(elem_id)

    filtered_elements = {}
    for elem_id, elem in elements.items():
        file_id = elem.attrib.get("file")
        if file_id and file_id in system_file_ids:
            continue
        filtered_elements[elem_id] = elem

    return filtered_elements


def get_full_namespace(elem: ET.Element, elements: Dict[str, ET.Element]) -> str:
    namespace = []
    context_id = elem.attrib.get("context")
    while context_id and context_id in elements:
        context = elements[context_id]
        name = context.attrib.get("name")
        if context.tag in ("Namespace", "Struct", "Class") and name:
            namespace.insert(0, name)
        context_id = context.attrib.get("context")
    return "::".join(namespace)


def resolve_type_name(type_id: str, elements: Dict[str, ET.Element]) -> str:
    visited = set()
    while type_id in elements and type_id not in visited:
        visited.add(type_id)
        elem = elements[type_id]
        print(type_id, elem.attrib)
        if "name" in elem.attrib:
            return elem.attrib["name"]
        type_id = elem.attrib.get("type")
    import ipdb

    ipdb.set_trace()
    return "unknown"


def parse_fields(elem: ET.Element, elements: Dict[str, ET.Element]) -> List[Field]:
    fields = []
    for member_id in elem.attrib.get("members", "").split():
        member = elements.get(member_id)
        if member is None or member.tag != "Field":
            continue
        type_ref = member.attrib.get("type", "")
        elements_list = []
        base_type_ref = type_ref
        field_type_elem = elements.get(base_type_ref)

        while field_type_elem is not None and field_type_elem.tag == "ArrayType":
            array_size = int(field_type_elem.attrib.get("max", "0")) + 1
            elements_list.append(array_size)
            base_type_ref = field_type_elem.attrib.get("type", "")
            field_type_elem = elements.get(base_type_ref)

        type_name = resolve_type_name(base_type_ref, elements)

        bitoffset = int(member.attrib.get("offset", "0"))
        size_in_bits = int(member.attrib.get("bits", member.attrib.get("size", "0")))

        fields.append(
            Field(
                name=member.attrib.get("name", ""),
                type=type_name,
                elements=elements_list[::-1],
                bitoffset=bitoffset,
                size_in_bits=size_in_bits,
                bitfield="bits" in member.attrib,
            )
        )
    return fields


def create_definitions(root: ET.Element) -> List:
    elements = filter_out_system_headers(get_element_dict(root))
    definitions = []
    for elem in elements.values():
        if elem.tag in ("Struct", "Class", "Enumeration", "Typedef", "Union"):
            ns = get_full_namespace(elem, elements)
            name = elem.attrib.get("name", "")
            full_name = f"{ns}::{name}" if ns and name else name or ns

            if elem.tag in ("Struct", "Class"):
                definitions.append(
                    ClassDefinition(
                        name=full_name,
                        alignment=int(elem.attrib["align"]) // CHAR_BIT,
                        size=int(elem.attrib["size"]) // CHAR_BIT,
                        fields=parse_fields(elem, elements),
                    )
                )

            elif elem.tag == "Union":
                definitions.append(
                    UnionDefinition(
                        name=full_name,
                        alignment=int(elem.attrib["align"]) // CHAR_BIT,
                        size=int(elem.attrib["size"]) // CHAR_BIT,
                        fields=parse_fields(elem, elements),
                    )
                )

            elif elem.tag == "Enumeration":
                enums = [
                    EnumName(ev.attrib["name"], int(ev.attrib["init"]))
                    for ev in list(elem)
                    if ev.tag == "EnumValue"
                ]
                definitions.append(
                    EnumDefinition(
                        name=full_name,
                        size=int(elem.attrib["size"]) // CHAR_BIT,
                        enums=enums,
                    )
                )

            elif elem.tag == "Typedef":
                typedef_type_id = elem.attrib.get("type", "")
                typedef_type_elem = elements.get(typedef_type_id)
                typedef_def = (
                    typedef_type_elem.attrib.get("name", "unknown")
                    if typedef_type_elem
                    else "unknown"
                )
                definitions.append(
                    TypedefDefinition(name=full_name, type=typedef_def)
                )
    return definitions


def find_gaps(class_def: ClassDefinition) -> List[str]:
    gaps = []
    offset = 0
    for field in sorted(class_def.fields, key=lambda x: x.bitoffset):
        if offset < field.bitoffset:
            gaps.append(f"gap of {field.bitoffset - offset} bits before {field.name}")
        offset = field.bitoffset + field.size_in_bits
    if offset < class_def.size * CHAR_BIT:
        gaps.append(f"gap of {(class_def.size * CHAR_BIT) - offset} bits at the end")
    return gaps


def print_structure(definitions: List, name: str):
    for definition in definitions:
        if isinstance(definition, ClassDefinition) and definition.name.endswith(name):
            print(
                f"Structure {definition.name}: size={definition.size} bytes, alignment={definition.alignment} bytes"
            )
            for field in definition.fields:
                print(
                    f"  {field.name}: offset={field.bitoffset} bits, size={field.size_in_bits} bits, type={field.type}, bitfield={field.bitfield}"
                )
            gaps = find_gaps(definition)
            if gaps:
                print("Gaps:")
                for gap in gaps:
                    print(f"  {gap}")
            break


if __name__ == "__main__":
    root = parse_xml("complicated_structs.xml")
    definitions = create_definitions(root)
    print([d.name for d in definitions])
    for d in definitions:
        print(d)
    print_structure(definitions, "::::OuterNamespace::InnerNamespace::PackedStruct")
