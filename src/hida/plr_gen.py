# plr_serializer.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

# ==== Import your data model ====
# Expecting the classes exactly as you provided:
# TypeBase, DefinitionBase, Field, ClassDefinition, EnumName, EnumDefinition, UnionDefinition, TypedefDefinition
from .data import (
    TypeBase,
    Field,
    ClassDefinition,
    EnumDefinition,
    EnumName,
    UnionDefinition,
    TypedefDefinition,
    DefinitionBase,
)

# ============================================================
#                          CONSTANTS
# ============================================================

DEFAULTS = {
    "A_Def": "1",
    "AlmMax_Def": "0",
    "AlmMin_Def": "0",
    "B_Def": "0",
    "Compound": "",
    # Formats:
    #   2 -> Decimal (normal numeric)
    #   3 -> String
    #   4 -> Literal (enum mapping)
    # We also use 1 as a best-guess for "Hex" when asked for hex display (void*).
    "FormatNumeric": "2",
    "FormatString": "3",
    "FormatLiteral": "4",
    "FormatHex": "1",
    "RingSize": "50000",
    "Unit": "",
    "UserFormat": "",
    "VldA": "0",
    "Subcommut": "0",
    "MsgType": "RT2BC",
}

# PLR "Type" codes (as you specified)
PLR_TYPE_FROM_C: Dict[str, str] = {
    "double": "57",
    "float": "15",

    "uint64_t": "78",
    "uint32_t": "11",
    "uint16_t": "13",
    "uint8_t":  "7",

    "int64_t": "77",
    "int32_t": "10",
    "int16_t": "12",
    "int8_t":  "6",

    # bool is uint8_t
    "bool": "7",
    # void* => treat as uint64_t
    "void*": "78",
}

# For Max_Def/Min_Def ranges and masks (full-width).
FULL_MASK_BY_BITS: Dict[int, str] = {
    8:  "000000FF",
    16: "0000FFFF",
    32: "FFFFFFFF",
    64: "FFFFFFFFFFFFFFFF",
}

# Floating ranges
FLOAT_LIMITS = {
    "float":  ("-3.4E+38", "3.4E+38"),
    "double": ("-1.7E+308", "1.7E+308"),
}

# Screen geometry for .sub. Units will be tiled HORIZONTALLY and share full height.
SCREEN_LEFT, SCREEN_TOP, SCREEN_RIGHT, SCREEN_BOTTOM = 0, 0, 1920, 1080

# A Unit can show up to this many Params/Paths
UNIT_MAX_PARAMS = 99


# ============================================================
#                    HELPER / UTILITY FUNCTIONS
# ============================================================

def prettify(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ")

def bits_for_ctype_name(name: str) -> int:
    n = name.lower()
    if n in ("double",):
        return 64
    if n in ("float",):
        return 32
    if n in ("bool", "uint8_t", "int8_t"):
        return 8
    if n in ("uint16_t", "int16_t"):
        return 16
    if n in ("uint32_t", "int32_t"):
        return 32
    if n in ("uint64_t", "int64_t", "void*"):
        return 64
    # fallback (should not happen given your constraint)
    return 32

def is_signed(name: str) -> bool:
    n = name.lower()
    return n in ("int8_t", "int16_t", "int32_t", "int64_t")

def is_floaty(name: str) -> bool:
    n = name.lower()
    return n in ("float", "double")

def is_string_char_array(field: Field) -> bool:
    # We only have char arrays if the type is int8_t (a.k.a char) and total elements > 1
    n = field.type.name.lower()
    if n not in ("int8_t",):
        return False
    total = 1
    for e in (field.elements or ()):
        total *= e
    return total > 1

def is_void_ptr(name: str) -> bool:
    return name.lower() == "void*"

def array_linear_indices(dims: Sequence[int]) -> List[Tuple[int, Tuple[int, ...]]]:
    """
    Return a list of (linear_index, multi_index) for dims (e.g., [2,3] -> 0..5).
    Multi-index is in C-order (row-major).
    """
    if not dims:
        return [(0, tuple())]
    # Generate all multi-indices
    def rec(prefix: List[int], rest: Sequence[int], out: List[Tuple[int, Tuple[int, ...]]]):
        if not rest:
            # compute linear index (row-major)
            lin = 0
            mul = 1
            for d, sz in zip(reversed(prefix), reversed(dims)):
                lin += d * mul
                mul *= sz
            out.append((lin, tuple(prefix)))
            return
        for i in range(rest[0]):
            prefix.append(i)
            rec(prefix, rest[1:], out)
            prefix.pop()
    res: List[Tuple[int, Tuple[int, ...]]] = []
    rec([], list(dims), res)
    # Sort by linear index
    res.sort(key=lambda x: x[0])
    return res

def name_with_index_suffix(base: str, multi_index: Tuple[int, ...]) -> str:
    """
    Convert a base name + multi-index into the required suffix format: _<n>_... (no square brackets).
    0-based indexing.
    """
    if not multi_index:
        return base
    parts = "_".join(str(i) for i in multi_index)
    return f"{base}_{parts}"

def mask_for_full_width(bits: int) -> str:
    return FULL_MASK_BY_BITS.get(bits, "FFFFFFFF")

def map_ctype_to_plr_type(name: str) -> str:
    return PLR_TYPE_FROM_C.get(name, PLR_TYPE_FROM_C["uint32_t"])

def default_format_for_field(
    field_type_name: str,
    is_enum: bool,
    force_hex: bool,
) -> str:
    if is_enum:
        return DEFAULTS["FormatLiteral"]  # "4" to show literals
    if force_hex:
        return DEFAULTS["FormatHex"]  # guessed hex code
    if is_string_char_array_name(field_type_name):
        return DEFAULTS["FormatString"]
    return DEFAULTS["FormatNumeric"]

def is_string_char_array_name(type_name: str) -> bool:
    return type_name.lower() == "int8_t"

def enum_of_field(field: Field, enums_by_name: Dict[str, EnumDefinition]) -> Optional[EnumDefinition]:
    # Match by simple name or fully qualified name
    if field.type.name in enums_by_name:
        return enums_by_name[field.type.name]
    fq = field.type.name if not getattr(field.type, "namespace", None) else field.type.fullname
    return enums_by_name.get(fq)

def collect_class_map(defs: Iterable[DefinitionBase]) -> Dict[str, ClassDefinition]:
    classes: Dict[str, ClassDefinition] = {}
    for d in defs:
        if isinstance(d, ClassDefinition):
            classes[d.name] = d
    return classes

def collect_enum_map(defs: Iterable[DefinitionBase]) -> Dict[str, EnumDefinition]:
    enums: Dict[str, EnumDefinition] = {}
    for d in defs:
        if isinstance(d, EnumDefinition):
            enums[d.name] = d
            # Also store fully qualified version if has namespaces
            if getattr(d, "namespace", None):
                enums[d.fullname] = d
    return enums

# Geom helper: tile horizontally across full width, full height
def unit_geom(total_units: int, unit_index_1based: int) -> Tuple[int, int, int, int]:
    total_width = SCREEN_RIGHT - SCREEN_LEFT
    slot = max(1, total_width // max(1, total_units))
    left = SCREEN_LEFT + (unit_index_1based - 1) * slot
    right = min(SCREEN_RIGHT, left + slot - 5)  # small gap
    top = SCREEN_TOP
    bottom = SCREEN_BOTTOM
    return (left, top, right, bottom)

# ============================================================
#                     CORE XML EMISSION
# ============================================================

@dataclass
class SubMsgRec:
    msg_name: str            # The owning message name (top-level ClassDefinition)
    name: str                # This sub-message's name (flat, no path)
    offset: int              # Offset relative to parent base (bytes)
    parent_path: str         # "" for none, or "foo\bar"
    remark: str              # The real type name (ClassDefinition name)


def generate_xml_from_definitions(
    defs: List[Union[ClassDefinition, EnumDefinition, TypedefDefinition, UnionDefinition]],
    *,
    message_names: Optional[Iterable[str]] = None,
) -> Tuple[str, List[SubMsgRec], Dict[str, List[Tuple[str, str]]]]:
    """
    Build the PLR XML string.

    Args:
      defs: list of definitions produced by your CastXML pipeline.
      message_names: optional iterable of class names to export as <Msg>. If None, all classes are messages.

    Returns:
      (xml_text, submsgs_list, per_message_param_paths)
      - xml_text: the pretty XML string
      - submsgs_list: the SubMsg records actually created
      - per_message_param_paths: mapping MsgName -> list of (PathName, FullPathString) for .sub files
    """
    classes = collect_class_map(defs)
    enums = collect_enum_map(defs)

    if message_names is None:
        selected_msgs = list(classes.values())
    else:
        # accept both simple and fully-qualified names
        wanted = set(message_names)
        selected_msgs = [c for c in classes.values() if c.name in wanted or c.fullname in wanted]

    # Build XML root
    root = ET.Element("PLR")

    # <Msges>
    msges = ET.SubElement(root, "Msges")
    for c in selected_msgs:
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

    # <Params>
    params_el = ET.SubElement(root, "Params")

    # sub-messages we will collect while walking nested structures
    submsgs: List[SubMsgRec] = []
    # also collect Paths per message (for .sub files): list of (param_name, "Msg\Param")
    per_msg_paths: Dict[str, List[Tuple[str, str]]] = {}

    # name → ClassDefinition resolver
    def resolve_class(t: TypeBase) -> Optional[ClassDefinition]:
        # exact match
        if t.name in classes:
            return classes[t.name]
        # fully qualified?
        if getattr(t, "namespace", None):
            return classes.get(t.fullname)
        return None

    # emit a single numeric/float/bool/void* param element
    def emit_numeric_param(
        msg_name: str,
        submsg_chain: List[str],
        pname: str,
        offset_bytes: int,
        ctype_name: str,
        width_bits: int,
        enum_def: Optional[EnumDefinition],
    ):
        # Type & Format
        force_hex = is_void_ptr(ctype_name)
        plr_type = map_ctype_to_plr_type(ctype_name)
        fmt = DEFAULTS["FormatLiteral"] if enum_def else (DEFAULTS["FormatHex"] if force_hex else DEFAULTS["FormatNumeric"])

        # Mask
        mask = mask_for_full_width(width_bits)

        # Min/Max
        if is_floaty(ctype_name):
            min_def, max_def = FLOAT_LIMITS["double"] if ctype_name == "double" else FLOAT_LIMITS["float"]
        else:
            # integers/bool/void*
            if is_signed(ctype_name):
                # show signed range by hinting via Min_Def negative;
                # we do not know exact min, so use -1 (viewer will interpret sign)
                min_def, max_def = "-1", str(int(mask, 16))
            else:
                min_def, max_def = "0", str(int(mask, 16))

        attrs = {
            "A_Def": DEFAULTS["A_Def"],
            "AlmMax_Def": DEFAULTS["AlmMax_Def"],
            "AlmMin_Def": DEFAULTS["AlmMin_Def"],
            "B_Def": DEFAULTS["B_Def"],
            "Compound": DEFAULTS["Compound"],
            "Format": fmt,
            "Mask": mask,
            "Max_Def": max_def,
            "Min_Def": min_def,
            "MsgName": msg_name,
            "Name": pname,
            "Offset": str(offset_bytes),
            "RingSize": DEFAULTS["RingSize"],
            "SubMsgName": "\\".join(submsg_chain) if submsg_chain else "",
            "Type": plr_type,
            "Unit": DEFAULTS["Unit"],
            "UserFormat": DEFAULTS["UserFormat"],
        }
        param_el = ET.SubElement(params_el, "Param", attrs)

        # Literals for enum
        if enum_def:
            lits_el = ET.SubElement(param_el, "Literals", {"FromIni": ""})
            for en in enum_def.enums:
                # If you need "To", you can duplicate From into To; many samples use just From
                ET.SubElement(lits_el, "Literal", {"From": str(en.value), "Name": en.name})

        # Track path for .sub files: "Msg\Param"
        full_path = f"{msg_name}\\{pname}"
        per_msg_paths.setdefault(msg_name, []).append((pname, full_path))

    # recursively expand a field (including arrays, nested structs)
    def expand_field(
        owner_msg: str,
        base_bitoffset: int,
        parent_chain: List[str],         # names of parent sub messages (for SubMsgName)
        parent_submsg_path: str,         # "" or "foo\bar" (used in SubMsgs ParentName)
        field: Field,
    ):
        # If string (char array)
        if is_string_char_array(field):
            dims = field.elements or tuple()
            total = 1
            for e in dims:
                total *= e
            # Emit as String (Type=14 in many PLR dialects) — however you asked to keep our type table.
            # Since our allowed types are limited, and you didn't ask for explicit strings in mapping,
            # we emit them as byte arrays shown as strings: Type "14" and Format "3".
            strlen = total
            for lin, mi in array_linear_indices(dims if dims else (1,)):
                elem_name = name_with_index_suffix(field.name, mi)
                offset_bytes = (field.bitoffset // 8) + lin  # byte per char
                attrs = {
                    "A_Def": DEFAULTS["A_Def"],
                    "AlmMax_Def": DEFAULTS["AlmMax_Def"],
                    "AlmMin_Def": DEFAULTS["AlmMin_Def"],
                    "B_Def": DEFAULTS["B_Def"],
                    "Compound": DEFAULTS["Compound"],
                    "Format": DEFAULTS["FormatString"],
                    "Mask": "0000FFFF",
                    "Max_Def": "0",
                    "Min_Def": "0",
                    "MsgName": owner_msg,
                    "Name": elem_name if total > 1 else field.name,
                    "Offset": str(offset_bytes),
                    "RingSize": DEFAULTS["RingSize"],
                    "SubMsgName": "\\".join(parent_chain) if parent_chain else "",
                    "Type": "14",
                    "Unit": DEFAULTS["Unit"],
                    "UserFormat": DEFAULTS["UserFormat"],
                }
                # Only first carries the declared length
                if lin == 0:
                    attrs["String_Len"] = str(strlen)
                else:
                    attrs["String_Len"] = "0"
                ET.SubElement(params_el, "Param", attrs)
                per_msg_paths.setdefault(owner_msg, []).append((attrs["Name"], f"{owner_msg}\\{attrs['Name']}"))
            return

        # If field is a struct/union (i.e., its type maps to a known ClassDefinition)
        nested_class = resolve_class(field.type)
        if nested_class is not None:
            # arrays of struct?
            dims = field.elements or tuple()
            if not dims:
                # Single sub-message
                sub_name = field.name
                # For <SubMsgs>, use a flat Name (no nesting)
                # Offset of this sub relative to the current parent (bytes)
                rel_off_bytes = (field.bitoffset - base_bitoffset) // 8
                submsgs.append(
                    SubMsgRec(
                        msg_name=owner_msg,
                        name=sub_name,
                        offset=rel_off_bytes,
                        parent_path=parent_submsg_path,
                        remark=nested_class.name,
                    )
                )
                # Recurse into children with submsg chain extended
                chain = parent_chain + [sub_name]
                new_parent_path = sub_name if not parent_submsg_path else f"{parent_submsg_path}\\{sub_name}"
                for child in nested_class.fields:
                    expand_field(owner_msg, field.bitoffset, chain, new_parent_path, child)
            else:
                # Array of struct: emit a sub-message per element: name_0, name_1, ...
                elem_bits = nested_class.size * 8  # size is bytes
                for lin, mi in array_linear_indices(dims):
                    sub_name = name_with_index_suffix(field.name, mi)
                    # offset of this element relative to parent base (bytes)
                    rel_off_bytes = ((field.bitoffset - base_bitoffset) + lin * elem_bits) // 8
                    submsgs.append(
                        SubMsgRec(
                            msg_name=owner_msg,
                            name=sub_name,
                            offset=rel_off_bytes,
                            parent_path=parent_submsg_path,
                            remark=nested_class.name,
                        )
                    )
                    # Recurse into that element
                    chain = parent_chain + [sub_name]
                    new_parent_path = sub_name if not parent_submsg_path else f"{parent_submsg_path}\\{sub_name}"
                    # Recompute children's absolute bitoffsets by adding element base
                    element_base_bits = field.bitoffset + lin * elem_bits
                    for child in nested_class.fields:
                        # We must adjust the child's bit offset (child.bitoffset is relative to struct start)
                        child_adjusted = Field(
                            name=child.name,
                            type=child.type,
                            elements=child.elements,
                            bitoffset=element_base_bits + child.bitoffset,
                            size_in_bits=child.size_in_bits,
                            bitfield=child.bitfield,
                        )
                        expand_field(owner_msg, element_base_bits, chain, new_parent_path, child_adjusted)
            return

        # Otherwise: numeric/float/bool/void* or arrays thereof
        width_bits = field.size_in_bits or bits_for_ctype_name(field.type.name)
        enum_def = enum_of_field(field, enums)

        dims = field.elements or tuple()
        if not dims:
            # single scalar
            offset_bytes = field.bitoffset // 8
            emit_numeric_param(
                owner_msg,
                parent_chain,
                field.name,
                offset_bytes,
                field.type.name,
                width_bits,
                enum_def,
            )
        else:
            # array of scalars
            for lin, mi in array_linear_indices(dims):
                elem_name = name_with_index_suffix(field.name, mi)
                offset_bits = field.bitoffset + lin * width_bits
                offset_bytes = offset_bits // 8
                emit_numeric_param(
                    owner_msg,
                    parent_chain,
                    elem_name,
                    offset_bytes,
                    field.type.name,
                    width_bits,
                    enum_def,
                )

    # Walk every selected message's fields
    for msg in selected_msgs:
        for f in msg.fields:
            expand_field(owner_msg=msg.name, base_bitoffset=0, parent_chain=[], parent_submsg_path="", field=f)

    # <SubMsgs>
    submsgs_el = ET.SubElement(root, "SubMsgs")
    for rec in submsgs:
        ET.SubElement(
            submsgs_el,
            "SubMsg",
            {
                "MsgName": rec.msg_name,
                "Name": rec.name,                     # flat name
                "Offset": str(rec.offset),            # relative to parent
                "ParentName": rec.parent_path,        # "" or chain
                "Remark": rec.remark,                 # actual type
            },
        )

    return prettify(root), submsgs, per_msg_paths


# ============================================================
#                    .SUB FILE GENERATION
# ============================================================

SUB_HEADER_GENERAL_TEMPLATE = """[General]
Comment=New Subset
{unit_lines}TotalElements={total_units}
Geom={geom_left},{geom_top},{geom_right},{geom_bottom}
ScaleSubset=1
"""

UNIT_BLOCK_TEMPLATE = """[Unit{idx}]
Params={params_csv}
UnitName={unit_name}
Freeze=0
ShowAddr=1
ShowUnit=1
ShowRawData=0
PreserveRed=0
NameWidth=113
EngDataWidth=191
RawDataWidth=292
AddressWidth=394
UnitWidth=40
NameColor=15790320
EngDataColor=14606046
RawDataWidthColor=15790320
AddressColor=14606046
UnitColor=15790320
Geom={u_left},{u_top},{u_right},{u_bottom}
ShowAddrUnit=1
RawDataColor=15790320
ShowLastColor=0
UnitsConversion={units_conv}
ValidityCondition=
ShowFormat=0
DisplayTime=0
UseHistory=0
RingSize=1000
FontSize=0
Font=Name="Courier New" H=16 W=8 I=0 Weight=700 Use=0
FormatWidth=60
FormatColor=15790320
ValidityPrmName=
"""

PARAMS_SECTION_HEADER = "[Params]\n"

def write_sub_file(
    out_path: str,
    msg_name: str,
    paths: List[str],
) -> str:
    """
    Write a single .sub file for the given message.

    Each Unit holds up to 99 params. If more, we add Unit2, Unit3, ...,
    tile horizontally, and list Param indices accordingly.
    """
    # Partition into chunks of up to 99
    chunks: List[List[int]] = []
    all_indices = list(range(1, len(paths) + 1))
    while all_indices:
        chunks.append(all_indices[:UNIT_MAX_PARAMS])
        all_indices = all_indices[UNIT_MAX_PARAMS:]

    total_units = max(1, len(chunks))
    # General header: Unit1=4, Unit2=4, ...
    unit_lines = "".join(f"Unit{i}=4\n" for i in range(1, total_units + 1))
    # Top-level Geom: full canvas
    general_hdr = SUB_HEADER_GENERAL_TEMPLATE.format(
        unit_lines=unit_lines,
        total_units=total_units,
        geom_left=SCREEN_LEFT,
        geom_top=SCREEN_TOP + 35,       # match sample's top margin
        geom_right=SCREEN_RIGHT,
        geom_bottom=SCREEN_BOTTOM + 17,  # sample used 1097 vs 1080; keep the feel
    )

    # Units
    unit_blocks: List[str] = []
    for i, indices in enumerate(chunks, start=1):
        left, top, right, bottom = unit_geom(total_units, i)
        # Fill full height; mini top margin like sample
        top = SCREEN_TOP + 90
        # Params CSV ends with a comma (matches samples)
        params_csv = ",".join(str(k) for k in indices) + ","
        units_conv = ",".join("_" for _ in indices) + ","
        unit_blocks.append(
            UNIT_BLOCK_TEMPLATE.format(
                idx=i,
                params_csv=params_csv,
                unit_name=msg_name,
                u_left=left,
                u_top=top,
                u_right=right,
                u_bottom=SCREEN_BOTTOM + 70,  # sample-like extra height
                units_conv=units_conv,
            )
        )

    # [Params] section – PathN=Msg\Param
    params_lines = [PARAMS_SECTION_HEADER]
    for idx, p in enumerate(paths, start=1):
        params_lines.append(f"Path{idx}={p}\n")

    text = "\n".join([general_hdr] + unit_blocks + ["".join(params_lines)])

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path


def write_pages_addition(pages_path: str, page_files: List[str]) -> str:
    """
    Write ThisIde.ini.addition with:
      [Pages]
      LastPage=<N-1>
      Page0=...
      Page1=...
      ...
    """
    lines = ["[Pages]\n", f"LastPage={len(page_files) - 1}\n"]
    for i, fn in enumerate(page_files):
        lines.append(f"Page{i}={fn}\n")
    with open(pages_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return pages_path


# ============================================================
#                      PUBLIC ENTRY POINTS
# ============================================================

def plr_generate(
    defs: List[Union[ClassDefinition, EnumDefinition, TypedefDefinition, UnionDefinition]],
    outputfile: str,
    *,
    message_names: Optional[Iterable[str]] = None,
    make_sub_files: bool = False,
) -> str:
    """
    Generate PLR XML from definitions and optionally create per-message .sub files.

    Args:
      defs: your parsed definitions list.
      outputfile: path to write the PLR XML.
      message_names: optional iterable with class names to export as messages. If None -> all classes.
      make_sub_files: if True, generate <Msg>.sub files (and ThisIde.ini.addition) in the SAME directory as outputfile.

    Returns:
      The path to the written XML file.
    """
    xml_text, submsgs, per_msg_paths = generate_xml_from_definitions(defs, message_names=message_names)

    # Write XML
    os.makedirs(os.path.dirname(os.path.abspath(outputfile)) or ".", exist_ok=True)
    with open(outputfile, "w", encoding="utf-8") as f:
        f.write(xml_text)

    # Write .sub files (and pages) if requested.
    if make_sub_files:
        out_dir = os.path.dirname(os.path.abspath(outputfile)) or "."
        page_files: List[str] = []
        # For each message we actually emitted (keys of per_msg_paths)
        for msg_name, pairs in per_msg_paths.items():
            # pairs: list[(ParamName, "Msg\Param")]
            paths = [p for _, p in pairs]
            sub_name = f"{msg_name}.sub"
            sub_path = os.path.join(out_dir, sub_name)
            write_sub_file(sub_path, msg_name, paths)
            page_files.append(sub_name)

        # Write pages file next to XML
        pages_path = os.path.join(out_dir, "ThisIde.ini.addition")
        write_pages_addition(pages_path, page_files)

    return outputfile


# ============================================================
#                       MODULE DOCSTRING
# ============================================================

__doc__ = """
PLR XML Generator

Key features:
- Uses your minimal type set: float, double, [u]int{8,16,32,64}_t, bool, void*.
- Maps PLR Type codes exactly as requested.
- Enums render with Format="4" so their Literals are visible.
- Arrays expand using suffixes _0, _1, ... (no square brackets).
- Nested structs:
    * Param.SubMsgName contains a backslash-separated chain of sub-container names.
    * <SubMsgs> entries are flat:
        Name        = the sub-message's own name (no nesting),
        Offset      = byte offset relative to parent (0 for the first field in that sub),
        ParentName  = "" for top-level sub-messages, otherwise a backslash path to the parent,
        Remark      = the actual type name of the sub-message.
- You can pass `message_names` to choose which classes are emitted as <Msg>.
- Optional .sub files:
    * Written into the SAME directory as the XML.
    * Each lists up to 99 params per Unit; if more, adds Unit2, Unit3, ...
    * Units are tiled horizontally across the full width, each occupying full height.
    * Creates 'ThisIde.ini.addition' with the list of created sub pages when `make_sub_files=True`.

Usage example:
    xml_path = plr_generate(defs, "out/project.plr.xml",
                            message_names=["Everything", "B"],
                            make_sub_files=True)
"""
