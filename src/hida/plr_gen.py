from __future__ import annotations
from typing import List, Union, Dict, Optional, Tuple
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

from .data import (
    TypeBase,
    DefinitionBase,
    Field,
    ClassDefinition,
    EnumName,
    EnumDefinition,
    UnionDefinition,
    TypedefDefinition,
)

# --------------------
# PLR XML serializer
# --------------------

DEFAULTS = {
    # PLR requires lots of attributes. These are sane viewer-friendly defaults.
    "A_Def": "1",
    "AlmMax_Def": "0",
    "AlmMin_Def": "0",
    "B_Def": "0",
    "Compound": "",
    "Format": "2",          # 2 works well for numeric values; strings use 3 automatically
    "RingSize": "50000",
    "Unit": "",
    "UserFormat": "",
    "VldA": "0",
    "Subcommut": "0",
    "MsgType": "RT2BC",     # default if you don't have bus direction; tweak per project
}

# Common C/C++ name → (bit-size, kind)
# kind in {"int","uint","float","bool","char","ptr","other"}
TYPE_TABLE: Dict[str, Tuple[int, str]] = {
    # integers
    "int8_t": (8, "int"), "int16_t": (16, "int"), "int32_t": (32, "int"), "int64_t": (64, "int"),
    "uint8_t": (8, "uint"), "uint16_t": (16, "uint"), "uint32_t": (32, "uint"), "uint64_t": (64, "uint"),
    "char": (8, "char"), "signed char": (8, "char"), "unsigned char": (8, "char"),
    "short": (16, "int"), "unsigned short": (16, "uint"),
    "int": (32, "int"), "unsigned int": (32, "uint"),
    "long": (64, "int"), "unsigned long": (64, "uint"),
    "long long": (64, "int"), "unsigned long long": (64, "uint"),
    # floats
    "float": (32, "float"), "double": (64, "float"),
    # bool
    "bool": (8, "bool"),
    # pointer-ish (fallback to 64-bit; change if you target 32-bit)
    "void*": (64, "ptr"),
}

def prettify(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")

def base_width_bits_for(bit_lsb: int, width_bits: int) -> int:
    """Choose the smallest base container (8/16/32/64) that can hold the bitfield at the given LSB."""
    end = bit_lsb + width_bits  # exclusive
    for B in (8, 16, 32, 64):
        if end <= B:
            return B
    # fallback
    return 64

def mask_for_bitfield(lsb: int, width: int, base_bits: int) -> int:
    """Build a mask aligned within a base container (LSB=0..base_bits-1)."""
    raw = (1 << width) - 1
    return (raw << lsb) & ((1 << base_bits) - 1)

def int_mask_for_full_width(width_bits: int) -> Tuple[int, int]:
    """Return (mask, base_bits) for a full-width integer field."""
    if width_bits <= 8:
        return (0xFF, 8)
    if width_bits <= 16:
        return (0xFFFF, 16)
    if width_bits <= 32:
        return (0xFFFFFFFF, 32)
    if width_bits <= 64:
        return (0xFFFFFFFFFFFFFFFF, 64)
    # very large: emit a ((1<<width)-1) mask and base width = width rounded up to 8
    base_bits = ((width_bits + 7) // 8) * 8
    return ((1 << width_bits) - 1, base_bits)

def hexmask(mask: int, base_bits: int) -> str:
    width_nibbles = (base_bits + 3) // 4
    return f"{mask:0{width_nibbles}X}"

def infer_bits_and_kind(t: TypeBase, explicit_bits: int) -> Tuple[int, str]:
    """
    Decide field bit-width & kind from:
      1) explicit size_in_bits if non-zero
      2) known typename table on t.name (last identifier only)
      3) best-effort parse of typical names (uint16, u16, etc.)
      4) default 16-bit unsigned
    """
    if explicit_bits:
        # Kind unknown: assume integer, viewer will rely on Min/Max if needed
        return explicit_bits, "uint"

    name = (t.name or "").strip()
    # Direct table
    if name in TYPE_TABLE:
        bits, kind = TYPE_TABLE[name]
        return bits, kind

    # Heuristics like "uint16", "u16", "int32", "i32"
    low = name.lower()
    for tag, kind in (("uint", "uint"), ("int", "int"), ("u", "uint"), ("i", "int")):
        if low.startswith(tag):
            # pull trailing digits
            digits = "".join(ch for ch in low if ch.isdigit())
            if digits:
                try:
                    b = int(digits)
                    if b in (8, 16, 32, 64):
                        return b, kind
                except ValueError:
                    pass

    if low in ("float32", "f32"):
        return 32, "float"
    if low in ("float64", "f64"):
        return 64, "float"
    if "bool" in low:
        return 8, "bool"
    if "char" in low:
        return 8, "char"

    # Fallback
    return 16, "uint"

def ctype_to_plr_type(kind: str) -> Tuple[str, str]:
    """
    Return (Type, Format) strings for PLR <Param>.
      float  → ("4","2")
      bool   → ("5","1")
      int/*  → ("5","2")
      char[] handled at call site as string
    """
    if kind == "float":
        return ("4", "2")
    if kind == "bool":
        return ("5", "1")
    # integers (signed/unsigned) and others
    return ("5", "2")

def is_c_char_array(field: Field) -> bool:
    n = field.type.name.lower()
    if n in ("char", "signed char", "unsigned char"):
        dims = field.elements or tuple()
        # string if at least one dimension and total size > 1
        total = 1
        for e in (dims or ()):
            total *= e
        return total > 1
    return False

def enum_lookup(field: Field, enums: Dict[str, EnumDefinition]) -> Optional[EnumDefinition]:
    """
    Match by typename (and also fully-qualified if you use namespaces for enums).
    """
    # try simple name
    if field.type.name in enums:
        return enums[field.type.name]
    # try fully qualified
    fq = field.type.fullname
    if fq in enums:
        return enums[fq]
    return None

def emit_msgs(root: ET.Element, classes: List[ClassDefinition]):
    msges = ET.SubElement(root, "Msges")
    for c in classes:
        ET.SubElement(
            msges,
            "Msg",
            {
                "Descript": c.name,
                "MsgName": c.name,
                "Subcommut": DEFAULTS["Subcommut"],
                "Type": DEFAULTS["MsgType"],
                "VldA": DEFAULTS["VldA"],
            },
        )

def emit_params(root: ET.Element, classes: List[ClassDefinition], enums: Dict[str, EnumDefinition]):
    params = ET.SubElement(root, "Params")

    for c in classes:
        for f in c.fields:
            # total elements = product of f.elements; empty -> 1
            dims = f.elements or tuple()
            total_elems = 1
            for e in dims:
                total_elems *= e
            elem_count = max(1, total_elems)

            for idx in range(elem_count):
                base_name = f.name
                pname = f"{base_name}[{idx}]" if elem_count > 1 else base_name

                # String?
                if is_c_char_array(f):
                    # decide declared total string len (use product of dims)
                    strlen = 1
                    for e in dims:
                        strlen *= e
                    # Offset in bytes from struct start (byte-per-char)
                    offset_bytes = (f.bitoffset // 8) + idx
                    ET.SubElement(
                        params,
                        "Param",
                        {
                            "A_Def": DEFAULTS["A_Def"],
                            "AlmMax_Def": DEFAULTS["AlmMax_Def"],
                            "AlmMin_Def": DEFAULTS["AlmMin_Def"],
                            "B_Def": DEFAULTS["B_Def"],
                            "Compound": DEFAULTS["Compound"],
                            "Format": "3",
                            "Mask": "0000FFFF",  # not used for strings
                            "Max_Def": "0",
                            "Min_Def": "0",
                            "MsgName": c.name,
                            "Name": pname,
                            "Offset": str(offset_bytes),
                            "RingSize": DEFAULTS["RingSize"],
                            "SubMsgName": "",
                            "Type": "14",
                            "Unit": DEFAULTS["Unit"],
                            "UserFormat": DEFAULTS["UserFormat"],
                            # PLR samples often put String_Len on the first param only
                            "String_Len": str(strlen if idx == 0 else 0),
                        },
                    )
                    continue

                # Numeric or bitfield
                width_bits, kind = infer_bits_and_kind(f.type, f.size_in_bits)
                offset_bits = f.bitoffset + idx * width_bits
                offset_bytes = offset_bits // 8
                bit_lsb_in_byte = offset_bits % 8

                # Decide base container for the mask
                if f.bitfield or bit_lsb_in_byte != 0 or width_bits not in (8, 16, 32, 64):
                    base_bits = base_width_bits_for(bit_lsb_in_byte, width_bits)
                    lsb_in_base = bit_lsb_in_byte
                    mask_int = mask_for_bitfield(lsb_in_base, width_bits, base_bits)
                else:
                    mask_int, base_bits = int_mask_for_full_width(width_bits)

                mask_hex = hexmask(mask_int, base_bits)
                Type, Format = ctype_to_plr_type(kind)

                # Signedness hint: if signed, set Min_Def negative so PLR shows it as signed
                signed_hint = (kind == "int")

                param_attrs = {
                    "A_Def": DEFAULTS["A_Def"],
                    "AlmMax_Def": DEFAULTS["AlmMax_Def"],
                    "AlmMin_Def": DEFAULTS["AlmMin_Def"],
                    "B_Def": DEFAULTS["B_Def"],
                    "Compound": DEFAULTS["Compound"],
                    "Format": Format,
                    "Mask": mask_hex,
                    "Max_Def": "0",
                    "Min_Def": "-1" if signed_hint else "0",
                    "MsgName": c.name,
                    "Name": pname,
                    "Offset": str(offset_bytes),
                    "RingSize": DEFAULTS["RingSize"],
                    "SubMsgName": "",
                    "Type": Type,
                    "Unit": DEFAULTS["Unit"],
                    "UserFormat": DEFAULTS["UserFormat"],
                }
                param_el = ET.SubElement(params, "Param", param_attrs)

                # Embed Literals if this field maps to an EnumDefinition
                enum_def = enum_lookup(f, enums)
                if enum_def:
                    lits_el = ET.SubElement(param_el, "Literals", {"FromIni": ""})
                    for en in enum_def.enums:
                        ET.SubElement(
                            lits_el,
                            "Literal",
                            {"From": str(en.value), "Name": en.name},
                        )

def emit_submsgs(root: ET.Element):
    # If you need per-message submessages, add them here (empty container for PLR compatibility).
    ET.SubElement(root, "SubMsgs")

def generate_xml_from_definitions(defs: List[Union[
    ClassDefinition, EnumDefinition, TypedefDefinition, UnionDefinition
]]) -> str:
    # Partition inputs
    classes: List[ClassDefinition] = []
    enums: Dict[str, EnumDefinition] = {}
    for d in defs:
        if isinstance(d, ClassDefinition):
            classes.append(d)
        elif isinstance(d, EnumDefinition):
            # allow both short and fully-qualified keys
            enums[d.name] = d
            enums[getattr(d, "fullname", d.name)] = d
        # Typedef/Union could be projected if needed; ignored for PLR XML by default.

    root = ET.Element("PLR")
    emit_msgs(root, classes)
    emit_params(root, classes, enums)
    emit_submsgs(root)
    return prettify(root)

def plr_generate(defs, outputfile) -> str:
    text = generate_xml_from_definitions(defs)
    with open(outputfile, "w", encoding="utf-8") as f:
        f.write(text)
    return outputfile

# --------------------
# Example usage
# --------------------
if __name__ == "__main__":
    # Build types (namespaces optional)
    u16 = TypeBase(name="uint16_t")
    u8  = TypeBase(name="uint8_t")
    ch  = TypeBase(name="char")
    b1  = TypeBase(name="bool")  # used as 1-bit flag with bitfield=True

    msg = ClassDefinition(
        name="I_01",
        fields=(
            Field(
                name="Heading",
                type=u16,
                elements=tuple(),   # scalar
                bitoffset=26 * 8,   # byte 26
                size_in_bits=16,
                bitfield=False,
            ),
            Field(
                name="INUMode2",
                type=u8,
                elements=tuple(),
                bitoffset=58 * 8,
                size_in_bits=8,
                bitfield=False,
            ),
            Field(
                name="WOW",
                type=b1,            # will still serialize as Type=5/Format=1 because kind 'bool'
                elements=tuple(),
                bitoffset=0,        # at byte 0 bit 0
                size_in_bits=1,
                bitfield=True,
            ),
            Field(
                name="String",
                type=ch,
                elements=(20,),     # becomes Type=14, String_Len=20
                bitoffset=0,
                size_in_bits=8,
                bitfield=False,
            ),
        ),
        alignment=0,
        size=0,
        source="",
    )

    ed = EnumDefinition(
        name="INUMode2",
        size=1,
        enums=(EnumName("Normal", 0), EnumName("Critical", 128)),
        source="",
    )

    xml_text = generate_xml_from_definitions([msg, ed])
    print(xml_text)
