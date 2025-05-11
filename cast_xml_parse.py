import xml.etree.ElementTree as ET
from pathlib import Path
from data import *
import data_helpers


class CastXmlParse:
    CHAR_BITS = 8  # Number of bits in a byte (standard for most platforms)

    def __init__(
        self,
        use_bool=False,
        skip_failed_parsing=False,
        remove_unknown=True,
        verbose=False,
    ):
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
    def _normalize_integral_type(
        typename: str, size_in_bits: int, use_bool=False
    ) -> str:
        """
        Converts basic integral types to fixed-width types like uint32_t or int16_t.
        Leaves non-integral types unchanged.
        """
        normalized = " ".join(sorted(typename.fullname.split()))  # normalize order

        is_unsigned = "unsigned" in normalized

        if "double" in normalized:
            return typename
        if "bool" in normalized:
            if use_bool:
                return typename
            else:
                is_unsigned = True
        if any(
            word in normalized
            for word in ("char", "short", "long", "signed", "int", "bool")
        ):
            width_map = {
                8: "int8_t",
                16: "int16_t",
                32: "int32_t",
                64: "int64_t",
                128: "int128_t",
            }
            base = width_map.get(size_in_bits)
            if base:
                return TypeBase(name= f"u{base}" if is_unsigned else base)

        return typename

    def _remove_unknown(self):
        """
        Removes ClassDefinition and TypedefDefinition instances that refer to unknown types.
        A type is considered known if it's in builtin_types, or defined in self.data.
        """
        known_types = {TypeBase(t).fullname for t in data_helpers.builtin_types}

        # Add all defined types (Class, Union, Enum, Typedef names)
        for d in self.data:
            known_types.add(d.fullname)

        filtered = []
        for d in self.data:
            if isinstance(d, (UnionDefinition, ClassDefinition)):
                if all(f.type.fullname in known_types for f in d.fields):
                    filtered.append(d)
            elif isinstance(d, TypedefDefinition):
                if d.type.fullname in known_types:
                    filtered.append(d)
            else:
                filtered.append(d)  # keep Enums, Unions, Constants, etc.
        former_length = len(self.data)
        self.data = filtered
        if len(filtered) != former_length:
            if self.verbose:
                print(
                    f"Warning: Removed {former_length - len(filtered)} unknown types."
                )
            self._remove_unknown()

    def _build_id_map(self):
        self._id_map = {
            elem.get("id"): elem for elem in self.xml_root.findall(".//*[@id]")
        }

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
            new_def = []
            if elem.tag in ("Struct", "Class"):
                new_def = self._parse_struct_wrapper(elem)
            elif elem.tag in ("Typedef") and elem.get("name"):
                new_def = self._parse_typedef_wrapper(elem)
            elif elem.tag in ("Enumeration"):
                new_def = self._parse_enum_wrapper(elem)
            elif elem.tag in ("Union"):
                new_def = self._parse_union_wrapper(elem)
            elif elem.tag in ("Variable") and elem.get("init"):
                new_def = self._parse_constant_wrapper(elem)
            self.data = self.data + new_def

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
        
        if elem.get("incomplete", None) == "1":
            raise NotImplementedError(f"Incomplete type for type_id: {type_id}")
        
        tag = elem.tag
        if tag == "FundamentalType":
            type_ = self._get_typebase(elem)
            size = int(elem.get("size"))
            align = int(elem.get("align")) // self.CHAR_BITS
            return type_, size, align, ()

        elif tag == "Typedef":
            base_type, size, align, elements = self._get_raw_type(elem.get("type"))
            type_ = self._get_typebase(elem)
            return base_type if base_type != "" else type_, size, align, elements
        elif tag == "ElaboratedType":
            return self._get_raw_type(elem.get("type"))

        elif tag == "PointerType":
            size = int(elem.get("size"))
            align = int(elem.get("align")) // self.CHAR_BITS
            return TypeBase(name="void*", namespace=()), size, align, ()

        elif tag == "CvQualifiedType":
            base_type, size, align, elements = self._get_raw_type(elem.get("type"))
            return base_type, size, align, elements

        elif tag == "ArrayType":
            dim = int(elem.get("max", "-1")) + 1
            base_type, size, align, elements = self._get_raw_type(elem.get("type"))
            return base_type, size, align, tuple([dim] + list(elements))

        elif tag in ("Struct", "Class", "Union", "Enumeration"):
            type_ = self._get_typebase(elem)
            size = int(elem.get("size"))
            align = int(elem.get("align")) // self.CHAR_BITS
            return type_, size, align, ()

        raise NotImplementedError(f"Type resolution not implemented for tag: {tag}")

    def _get_type(self, type_id):
        type_name, size, align, elements = self._get_raw_type(type_id)
        base_type = CastXmlParse._normalize_integral_type(
            type_name, size, self.use_bool
        )

        return base_type, size, align, tuple(elements)

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

    def _get_typebase(self, elem):
        """
        Recursively resolves the full namespace-qualified name of an element,
        based on its 'context' chain. Anonymous namespaces are represented by their ID.
        """
        name = elem.get("name", "")
        if name == "":
            name = elem.get("id")
        context_id = elem.get("context")
        parts = []

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
            del parts[0]  # Global namespace removal
        return TypeBase(name=name, namespace=tuple(parts))

    def _parse_enum(self, enum_elem):
        """
        Parses a <Enumeration> element and returns an EnumDefinition object.
        """
        type_ = self._get_typebase(enum_elem)

        size_attr = enum_elem.get("size")
        if size_attr is None:
            raise ValueError(f"Enum '{type_.fullname}' missing 'size' attribute")

        size_bits = int(size_attr)
        if size_bits % self.CHAR_BITS != 0:
            raise ValueError(
                f"Enum '{type_.fullname}' size {size_bits} is not a multiple of CHAR_BITS"
            )

        size = size_bits // self.CHAR_BITS
        source = self._get_source_info(enum_elem)

        enum_values = []
        for val in enum_elem.findall("EnumValue"):
            val_name = val.get("name")
            val_init = val.get("init")
            if val_name is None or val_init is None:
                raise ValueError(
                    f"Enum '{type_.fullname}' has EnumValue with missing 'name' or 'init'"
                )
            enum_values.append(EnumName(name=val_name, value=int(val_init)))

        return [EnumDefinition(name=type_.name, namespace=type_.namespace, source=source, size=size, enums=tuple(enum_values))]

    def _parse_enum_wrapper(self, elem):
        """
        Wrapper for _parse_enum that respects skip_failed_parsing and verbose flags.
        """
        try:
            return self._parse_enum(elem)
        except Exception as e:
            if not getattr(self, "skip_failed_parsing", False):
                raise
            if getattr(self, "verbose", False):
                print(f"Warning: Failed to parse enum '{elem.get('name')}' - {e}")
        return []

    def _parse_union(self, union_elem):
        """
        Parses a <Union> element and returns a UnionDefinition object.
        """
        type_ = self._get_typebase(union_elem)

        size_attr = union_elem.get("size")
        if size_attr is None:
            raise ValueError(f"Union '{type_.fullname}' missing required 'size' attribute")
        size_bits = int(size_attr)

        if size_bits % self.CHAR_BITS != 0:
            raise ValueError(
                f"Union '{type_.fullname}' size {size_bits} is not a multiple of CHAR_BITS"
            )
        size = size_bits // self.CHAR_BITS

        align_attr = union_elem.get("align", None)
        alignment = int(align_attr) // self.CHAR_BITS if align_attr else 0
        if align_attr is None and self.verbose:
            print(f"Warning: Union '{type_.fullname}' has no alignment information, assuming 0.")

        source = self._get_source_info(union_elem)

        members_str = union_elem.get("members")
        if not members_str:
            raise ValueError(f"Union '{type_.fullname}' has no member list")

        fields = []
        for member_id in members_str.split():
            member_elem = self.xml_root.find(f".//*[@id='{member_id}']")
            if member_elem is not None and member_elem.tag == "Field":
                field = self._parse_field(member_elem)
                fields.append(field)

        return [
            UnionDefinition(
                name=type_.name, namespace=type_.namespace, source=source, alignment=alignment, size=size, fields=tuple(fields)
            )
        ]

    def _parse_union_wrapper(self, elem):
        try:
            return self._parse_union(elem)
        except Exception as e:
            if not getattr(self, "skip_failed_parsing", False):
                raise
            if getattr(self, "verbose", False):
                print(f"Warning: Failed to parse union '{elem.get('name')}' - {e}")
        return []

    def _parse_typedef(self, typedef_elem):
        """
        Parses a <Typedef> element and returns a TypedefDefinition object.
        If the typedef refers to a pointer, the definition is always 'void*'.
        """
        type_ = self._get_typebase(typedef_elem)

        type_id = typedef_elem.get("type")
        if not type_id:
            raise ValueError(f"Typedef '{type_.fullname}' missing 'type' attribute")

        source = self._get_source_info(typedef_elem)

        # Resolve type
        resolved_type, _, _, elements = self._get_type(type_id)

        return [
            TypedefDefinition(
                name=type_.name, namespace=type_.namespace, source=source, type=resolved_type, elements=tuple(elements)
            )
        ]

    def _parse_typedef_wrapper(self, elem):
        try:
            return self._parse_typedef(elem)
        except Exception as e:
            if not self.skip_failed_parsing:
                raise
            else:
                if self.verbose:
                    print(
                        f"Warning: Failed to parse typedef '{elem.get('name')}' - {e}"
                    )
        return []

    def _parse_struct_wrapper(self, struct_elem):
        try:
            return self._parse_struct(struct_elem)
        except Exception as e:
            if not self.skip_failed_parsing:
                raise
            elif self.verbose:
                print(
                    f"Warning: Failed to parse struct '{struct_elem.get('name')}' - {e}"
                )
        return []

    def _parse_struct(self, struct_elem):
        """
        Parses a <Struct> element and returns a ClassDefinition object.
        """
        if struct_elem.get("incomplete", None) == "1":
            return []

        type_ = self._get_typebase(struct_elem)

        size_attr = struct_elem.get("size")
        if size_attr is None:
            raise ValueError(f"Struct '{type_.fullname}' missing required 'size' attribute")
        size_bits = int(size_attr)

        if size_bits % self.CHAR_BITS != 0:
            raise ValueError(
                f"Struct '{type_.fullname}' size {size_bits} is not a multiple of CHAR_BITS ({self.CHAR_BITS})"
            )

        size = size_bits // self.CHAR_BITS

        align_attr = struct_elem.get("align", None)
        if align_attr is None:
            if self.verbose:
                print(
                    f"Warning: Struct '{type_.fullname}' has no 'align' attribute, defaulting to 0"
                )
            alignment = 0
        else:
            alignment = int(align_attr) // self.CHAR_BITS

        source = self._get_source_info(struct_elem)

        member_ids = struct_elem.get("members", "").split()
        fields = []
        for member_id in member_ids:
            member_elem = self._id_map.get(member_id, None)
            if member_elem is not None and member_elem.tag == "Field":
                field = self._parse_field(member_elem)
                fields.append(field)
        class_def = ClassDefinition( name=type_.name, namespace=type_.namespace, source=source, alignment=alignment, size=size, fields=fields) 
        return [class_def]

    def _parse_field(self, field_elem):
        """
        Parses a <Field> element and returns a Field object.
        """
        name = field_elem.get("name")
        if name == "":
            name = field_elem.get("id")

        type = field_elem.get("type")
        if not type:
            raise ValueError(f"Field '{name}' missing 'type' attribute")

        offset_attr = field_elem.get("offset")
        if offset_attr is None:
            raise ValueError(f"Field '{name}' missing required 'offset' attribute")
        offset = int(offset_attr)

        type_name, size_in_bits, align, elements = self._get_type(type)
        bits = field_elem.get("bits", None)
        if bits:
            size_in_bits = int(bits)

        return Field(
            name=name,
            type=type_name,
            elements=elements,
            size_in_bits=size_in_bits,
            bitoffset=offset,
            bitfield=bool(bits),
        )

    def _parse_init_value(self, init_str):
        """
        Converts a CastXML 'init' attribute string to a Python value.
        Handles numeric literals and char literals.
        """
        try:
            # Character literal e.g., '\'' or '\n'
            if init_str.startswith("'") or init_str.startswith("&apos;"):
                return bytes(init_str.strip("'&apos;"), "utf-8").decode(
                    "unicode_escape"
                )

            # Unsigned long long literal with ULL suffix
            if init_str.endswith("ULL") or init_str.endswith("ull"):
                return int(init_str.rstrip("ULL").rstrip("ull"))

            # Float literal with 'F'
            if init_str.endswith("F") or init_str.endswith("f"):
                return float(init_str.rstrip("Ff"))

            # Integer literal
            if init_str.isdigit():
                return int(init_str)

            # Float without suffix
            return float(init_str)

        except Exception as e:
            raise ValueError(f"Failed to parse init value '{init_str}': {e}")

    def _parse_constant(self, var_elem):
        """
        Parses a <Variable> element and returns a ConstantDefinition.
        Assumes the variable is a top-level const with an initializer.
        """
        type_ = self._get_typebase(var_elem)

        init = var_elem.get("init")
        if init is None:
            raise ValueError(f"Constant '{type_.fullname}' has no initializer")

        type_id = var_elem.get("type")
        if not type_id:
            raise ValueError(f"Constant '{type_.fullname}' missing type reference")

        type, _, _, _ = self._get_type(type_id)
        source = self._get_source_info(var_elem)

        # Convert init to typed Python value
        value = self._parse_init_value(init)

        return [
            ConstantDefinition(name=type_.name, namespace=type_.namespace, source=source, type=type, value=value)
        ]

    def _parse_constant_wrapper(self, elem):
        try:
            return self._parse_constant(elem)
        except Exception as e:
            if not getattr(self, "skip_failed_parsing", False):
                raise
            if getattr(self, "verbose", False):
                print(f"Warning: Failed to parse constant '{elem.get('name')}' - {e}")
        return []


def parse(xml_path: str, **kwargs):
    """
    Helper function to parse a CastXML XML file with optional configuration parameters.
    """
    parser = CastXmlParse(**kwargs)
    return parser.parse_xml(Path(xml_path))
