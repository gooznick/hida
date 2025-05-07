import xml.etree.ElementTree as ET
from pathlib import Path
from data import *

class CastXmlParse:

    CHAR_BITS = 8  # Number of bits in a byte (standard for most platforms)


    def __init__(self, use_bool=False):
        """
        Initialize the parser with an optional configuration dictionary.
        """
        self.use_bool = use_bool
        self.xml_root = None
        self.data = None  # This will hold parsed data after _parse

    def parse_xml(self, xml_path: Path):
        """
        Public method to load and parse the XML file.
        Returns a list of parsed class definitions.
        """
        try:
            tree = ET.parse(xml_path)
            self.xml_root = tree.getroot()
        except ET.ParseError as e:
            raise ET.ParseError(f"Failed to parse XML file '{xml_path}': {e}") from e

        try:
            self._parse()
        except Exception as e:
            raise RuntimeError(f"Failed to extract data from XML structure: {e}") from e

        return self.data

    @staticmethod
    def _normalize_integral_type(typename: str, size_in_bits: int, use_bool = False) -> str:
        """
        Converts basic integral types to fixed-width types like uint32_t or int16_t.
        Leaves non-integral types unchanged.
        """
        normalized = " ".join(sorted(typename.split()))  # normalize order

        is_unsigned = "unsigned" in normalized

        if "double" in normalized:
            return typename
        if "bool" in normalized:
            if use_bool:
                return typename
            else:
                is_unsigned = True
        if any(word in normalized for word in ("char", "short", "long", "signed", "int", "bool")):
            width_map = {
                8: "int8_t",
                16: "int16_t",
                32: "int32_t",
                64: "int64_t",
                128: "int128_t",
            }
            base = width_map.get(size_in_bits)
            if base:
                return f"u{base}" if is_unsigned else base

        return typename

    def _parse(self):
        """
        Extracts all <Struct> definitions and delegates parsing to _parse_struct().
        Populates self.data with a list of ClassDefinition instances.
        """
        if self.xml_root is None:
            raise RuntimeError("XML root is not loaded.")

        self.data = []
        for elem in self.xml_root.findall(".//"):
            if elem.tag in ("Struct", "Class") and elem.get("name"):
                struct_def = self._parse_struct(elem)
                if struct_def:
                    self.data.append(struct_def)
        return self.data

    def _get_type(self, type_id):
        """
        Recursively resolves a type ID to its base type name, size, align, and array dimensions.
        Returns: (type_name: str, size: int, align: int, elements: List[int])
        """
        elem = self.xml_root.find(f".//*[@id='{type_id}']")
        if elem is None:
            raise ValueError(f"Type element with id '{type_id}' not found")

        tag = elem.tag
        if tag == "FundamentalType":
            name = elem.get("name")
            size = int(elem.get("size"))
            align = int(elem.get("align"))
            return name, size, align, []

        elif tag == "Typedef":
            return self._get_type(elem.get("type"))

        elif tag == "PointerType":
            size = int(elem.get("size"))
            align = int(elem.get("align"))
            return "void*", size, align, []
        
        elif tag == "CvQualifiedType":
            base_type, size, align, elements = self._get_type(elem.get("type"))
            return base_type, size, align, elements

        elif tag == "ArrayType":
            dim = int(elem.get("max", "-1")) + 1
            base_type, size, align, elements = self._get_type(elem.get("type"))
            return base_type, size, align, [dim] + elements

        elif tag in ("Struct", "Class", "Union", "Enumeration"):
            name = elem.get("name")
            size = int(elem.get("size"))
            align = int(elem.get("align"))
            return name, size, align, []

        raise NotImplementedError(f"Type resolution not implemented for tag: {tag}")
                       
    def _get_source_info(self, elem):
        """
        Extracts a human-readable source location from a tag using 'file' and 'line' attributes.
        """
        file_id = elem.get("file")
        line = elem.get("line")

        if not file_id or not line:
            raise ValueError(f"Element {elem.tag} missing 'file' or 'line' attribute")

        file_elem = self.xml_root.find(f".//File[@id='{file_id}']")
        if file_elem is None:
            raise ValueError(f"File element with id '{file_id}' not found in XML")

        file_path = file_elem.get("name")
        if not file_path:
            raise ValueError(f"File element '{file_id}' missing 'name' attribute")

        return f"{file_path}:{line}"
                    
                    
    def _parse_struct(self, struct_elem):
        """
        Parses a <Struct> element and returns a ClassDefinition object.
        """
        struct_id = struct_elem.get("id")
        name = struct_elem.get("name")
        if not name:
            raise ValueError(f"Struct element {struct_id} missing name")

        size_attr = struct_elem.get("size")
        if size_attr is None:
            raise ValueError(f"Struct '{name}' missing required 'size' attribute")
        size_bits = int(size_attr)

        if size_bits % self.CHAR_BITS != 0:
            raise ValueError(f"Struct '{name}' size {size_bits} is not a multiple of CHAR_BITS ({self.CHAR_BITS})")

        size = size_bits // self.CHAR_BITS


        align_attr = struct_elem.get("align")
        if align_attr is None:
            print(f"Warning: Struct '{name}' has no 'align' attribute, defaulting to 0")
            alignment = 0
        else:
            alignment = int(align_attr)

        source = self._get_source_info(struct_elem)

        class_def = ClassDefinition(
            name=name,
            source=source,
            alignment=alignment,
            size=size
        )

        member_ids = struct_elem.get("members", "").split()
        for member_id in member_ids:
            member_elem = self.xml_root.find(f".//*[@id='{member_id}']")
            if member_elem is not None and member_elem.tag == "Field":
                field = self._parse_field(member_elem)
                class_def.fields.append(field)

        return class_def

    def _parse_field(self, field_elem):
        """
        Parses a <Field> element and returns a Field object.
        """
        name = field_elem.get("name")
        if not name:
            raise ValueError("Field element missing 'name' attribute")

        c_type = field_elem.get("type")
        if not c_type:
            raise ValueError(f"Field '{name}' missing 'type' attribute")

        offset_attr = field_elem.get("offset")
        if offset_attr is None:
            raise ValueError(f"Field '{name}' missing required 'offset' attribute")
        offset = int(offset_attr)

        type_name, size, align, elements = self._get_type(c_type)
        type_name = CastXmlParse._normalize_integral_type(type_name, size, self.use_bool)
        return Field(
            name=name,
            c_type=type_name,
            elements=elements,
            size_in_bits=size,
            bitoffset=offset
        )

def parse(xml_path: str, **kwargs):
    """
    Helper function to parse a CastXML XML file with optional configuration parameters.
    """
    parser = CastXmlParse(**kwargs)
    return parser.parse_xml(Path(xml_path))