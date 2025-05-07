import xml.etree.ElementTree as ET
from pathlib import Path
from data import *
import data_helpers

class CastXmlParse:

    CHAR_BITS = 8  # Number of bits in a byte (standard for most platforms)


    def __init__(self, use_bool=False, skip_failed_parsing=False, remove_unknown=True, verbose=False):
        """
        Initialize the parser with an optional configuration dictionary.
        """
        self.use_bool = use_bool
        self.skip_failed_parsing = skip_failed_parsing
        self.remove_unknown = remove_unknown
        self.verbose = verbose
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

           
    def _remove_unknown(self):
        """
        Removes ClassDefinition and TypedefDefinition instances that refer to unknown types.
        A type is considered known if it's in builtin_types, or defined in self.data.
        """
        known_types = set(data_helpers.builtin_types)

        # Add all defined types (Class, Union, Enum, Typedef names)
        for d in self.data:
            if hasattr(d, "name") and isinstance(d.name, str):
                known_types.add(d.name)

        filtered = []
        for d in self.data:
            if isinstance(d, ClassDefinition):
                if all(f.c_type in known_types for f in d.fields):
                    filtered.append(d)
            elif isinstance(d, TypedefDefinition):
                if d.definition in known_types:
                    filtered.append(d)
            else:
                filtered.append(d)  # keep Enums, Unions, Constants, etc.
        former_length = len(self.data)
        self.data = filtered
        if len(filtered) != former_length:
            if self.verbose:
                print(f"Warning: Removed {former_length - len(filtered)} unknown types.")
            self._remove_unknown()

    
    def _build_id_map(self):
        self._id_map = {elem.get("id"): elem for elem in self.xml_root.findall(".//*[@id]")}

    def _parse(self):
        """
        Extracts all definitions and delegates parsing to _parse_*().
        Populates self.data with a list of *Definition instances.
        """
        if self.xml_root is None:
            raise RuntimeError("XML root is not loaded.")

        # cache by id
        self._build_id_map()
        
        self.data = []
        for elem in self.xml_root.findall(".//"):
            
            if elem.tag in ("Struct", "Class"):
                struct_def = self._parse_struct_wrapper(elem)
                if struct_def:
                    self.data.append(struct_def)
            elif elem.tag in ("Typedef") and elem.get("name"):
                typedef_def = self._parse_typedef_wrapper(elem)
                if typedef_def:
                    self.data.append(typedef_def)
        
        if self.remove_unknown:
            self._remove_unknown()
        return self.data

    def _get_raw_type(self, type_id):
        """
        Recursively resolves a type ID to its base type name, size, align, and array dimensions.
        Returns: (type_name: str, size: int, align: int, elements: List[int])
        """
        elem = self._id_map.get(type_id, None)
        if elem is None:
            raise ValueError(f"Type element with id '{type_id}' not found")

        tag = elem.tag
        if tag == "FundamentalType":
            name = self._add_namespace(elem)
            size = int(elem.get("size"))
            align = int(elem.get("align"))
            return name, size, align, []

        elif tag == "Typedef":
            base_type, size, align, elements = self._get_raw_type(elem.get("type"))
            name = self._add_namespace(elem)
            return base_type if base_type!="" else name, size, align, elements
        elif tag == "ElaboratedType":
            return self._get_raw_type(elem.get("type"))


        elif tag == "PointerType":
            size = int(elem.get("size"))
            align = int(elem.get("align"))
            return "void*", size, align, []
        
        elif tag == "CvQualifiedType":
            base_type, size, align, elements = self._get_raw_type(elem.get("type"))
            return base_type, size, align, elements

        elif tag == "ArrayType":
            dim = int(elem.get("max", "-1")) + 1
            base_type, size, align, elements = self._get_raw_type(elem.get("type"))
            return base_type, size, align, [dim] + elements


        elif tag in ("Struct", "Class", "Union", "Enumeration"):
            name = self._add_namespace(elem)  
            size = int(elem.get("size"))
            align = int(elem.get("align"))
            return name, size, align, []

        raise NotImplementedError(f"Type resolution not implemented for tag: {tag}")
    
    def _get_type(self, type_id):
        type_name, size, align, elements = self._get_raw_type( type_id)
        base_type = CastXmlParse._normalize_integral_type(type_name, size, self.use_bool)

        return base_type, size, align, elements
    
    def _get_source_info(self, elem):
        """
        Extracts a human-readable source location from a tag using 'file' and 'line' attributes.
        """
        file_id = elem.get("file")
        line = elem.get("line")

        if not file_id or not line:
            raise ValueError(f"Element {elem.tag} missing 'file' or 'line' attribute")

        file_elem = self._id_map.get(file_id, None)
        if file_elem is None:
            raise ValueError(f"File element with id '{file_id}' not found in XML")

        file_path = file_elem.get("name")
        if not file_path:
            raise ValueError(f"File element '{file_id}' missing 'name' attribute")

        return f"{file_path}:{line}"

    def _add_namespace(self, elem):
        """
        Recursively resolves the full namespace-qualified name of an element,
        based on its 'context' chain. Anonymous namespaces are represented by their ID.
        """
        name = elem.get("name")
        if name == "":
            name = elem.get("id")
        context_id = elem.get("context")
        parts = [name] if name else []

        while context_id:
            context_elem = self._id_map.get(context_id, None) 
            if context_elem is None:
                break

            if context_elem.tag == "Namespace":
                ns_name = context_elem.get("name")
                if not ns_name:  # anonymous namespace
                    ns_name = f"<anon@{context_elem.get('id')}>"
                parts.insert(0, ns_name)

            context_id = context_elem.get("context")
        if parts and parts[0] == "::":
            del parts[0] # Global namespace removal
        return "::".join(parts)
       
    def _parse_typedef(self, typedef_elem):
        """
        Parses a <Typedef> element and returns a TypedefDefinition object.
        If the typedef refers to a pointer, the definition is always 'void*'.
        """
        name = self._add_namespace(typedef_elem)


        type_id = typedef_elem.get("type")
        if not type_id:
            raise ValueError(f"Typedef '{name}' missing 'type' attribute")

        source = self._get_source_info(typedef_elem)

        # Resolve type
        resolved_type, _, _, elements = self._get_type(type_id)

        return TypedefDefinition(
            name=name,
            source=source,
            definition=resolved_type,
            elements=elements
        )
    def _parse_typedef_wrapper(self, elem):
        try:
            return self._parse_typedef(elem)
        except Exception as e:
            if not self.skip_failed_parsing:
                raise
            else:
                if self.verbose:
                    print(f"Warning: Failed to parse typedef '{elem.get('name')}' - {e}")
        return None
       
    def _parse_struct_wrapper(self, struct_elem):
        try:
            return self._parse_struct(struct_elem)
        except Exception as e:
            if not self.skip_failed_parsing:
                raise
            elif self.verbose:
                print(f"Warning: Failed to parse struct '{struct_elem.get('name')}' - {e}")
        return None

    def _parse_struct(self, struct_elem):
        """
        Parses a <Struct> element and returns a ClassDefinition object.
        """
        struct_id = struct_elem.get("id")
        name = self._add_namespace(struct_elem)

        size_attr = struct_elem.get("size")
        if size_attr is None:
            raise ValueError(f"Struct '{name}' missing required 'size' attribute")
        size_bits = int(size_attr)

        if size_bits % self.CHAR_BITS != 0:
            raise ValueError(f"Struct '{name}' size {size_bits} is not a multiple of CHAR_BITS ({self.CHAR_BITS})")

        size = size_bits // self.CHAR_BITS


        align_attr = struct_elem.get("align")
        if align_attr is None:
            if self.verbose:
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
            member_elem = self._id_map.get(member_id, None)  
            if member_elem is not None and member_elem.tag == "Field":
                field = self._parse_field(member_elem)
                class_def.fields.append(field)

        return class_def

    def _parse_field(self, field_elem):
        """
        Parses a <Field> element and returns a Field object.
        """
        name = field_elem.get("name")
        if name == '':
            name = field_elem.get("id")
        
        c_type = field_elem.get("type")
        if not c_type:
            raise ValueError(f"Field '{name}' missing 'type' attribute")

        offset_attr = field_elem.get("offset")
        if offset_attr is None:
            raise ValueError(f"Field '{name}' missing required 'offset' attribute")
        offset = int(offset_attr)

        type_name, size, align, elements = self._get_type(c_type)
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