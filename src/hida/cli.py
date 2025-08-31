from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import List, Optional

# --- Public API (from your __init__.py) ---
from hida import (
    parse,  # XML -> definitions
    # manipulators
    filter_by_source_regexes,
    get_system_include_regexes,
    fill_bitfield_holes_with_padding,
    fill_struct_holes_with_padding_bytes,
    resolve_typedefs,
    flatten_namespaces,
    filter_connected_definitions,
    # emitters
    write_header_from_definitions,
    write_c_header_from_definitions,
    generate_python_code_from_definitions,
)

# --- Runner (implementation you just wrote) ---
from .castxml_runner import (
    find_castxml,
    run_castxml_for_header,
    CastxmlRunError,
)


# ----------------- helpers -----------------

def _jsonable(obj):
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        return {k: _jsonable(v) for k, v in vars(obj).items()}
    return obj

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ----------------- CLI -----------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hida",
        description="CastXML XML → Python/Header/JSON converter with IR manipulators.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # INPUT
    g_in = p.add_argument_group("input")
    g_in.add_argument(
        "-i", "--input", type=Path, required=True,
        help="CastXML XML file OR a C/C++ header file. If header, hida runs castxml via the runner."
    )
    g_in.add_argument(
        "-I", "--include", action="append", default=[], type=Path,
        help="Include directory for castxml (repeatable). Only used when input is a header."
    )
    g_in.add_argument(
        "-x", "--xml-out", type=Path, default=None,
        help="Where to write the intermediate XML (when input is a header)."
    )
    g_in.add_argument(
        "--castxml", type=Path, default=None,
        help="Path to castxml executable. If omitted, use CASTXML_BIN env var or PATH."
    )
    g_in.add_argument(
        "--std", default="c++17",
        help="C++ language standard to use when invoking castxml (c++17, c++20, ...)."
    )
    g_in.add_argument(
        "--cx", action="append", default=[],
        help="Extra argument forwarded to castxml/clang (repeatable)."
    )
    p.add_argument(
        "remainder", nargs=argparse.REMAINDER,
        help="Flags after -- are forwarded to castxml (e.g., `-- -DMODE=2 -Wall`)."
    )

    # MANIPULATORS
    g_m = p.add_argument_group("manipulators")
    g_m.add_argument(
        "--exclude-source", action="append", default=[],
        help="Regex to exclude by 'source' path (repeatable)."
    )
    g_m.add_argument(
        "--exclude-system", action="store_true",
        help="Also exclude common system/builtin sources."
    )
    g_m.add_argument(
        "--pad-bitfield-holes", action="store_true",
        help="Fill bitfield holes with explicit padding fields."
    )
    g_m.add_argument(
        "--pad-struct-holes", action="store_true",
        help="Fill struct holes with padding bytes."
    )
    g_m.add_argument(
        "--resolve-typedefs", action="store_true",
        help="Resolve/inline typedefs."
    )
    g_m.add_argument(
        "--flatten-namespaces", action="store_true",
        help="Flatten namespace hierarchy."
    )
    g_m.add_argument(
        "--focus", action="append", default=[],
        help="Keep only definitions connected to these types (repeat)."
    )

    # OUTPUTS
    g_out = p.add_argument_group("output")
    g_out.add_argument("--python", type=Path, default=None,
                       help="Write generated Python to this file.")
    g_out.add_argument("--header", "--h", dest="header", type=Path, default=None,
                       help="Write generated (C++-style) header to this file.")
    g_out.add_argument("--c-header", dest="c_header", type=Path, default=None,
                       help="Write generated C header to this file.")
    g_out.add_argument("--json", type=Path, default=None,
                       help="Write JSON IR to this file.")
    g_out.add_argument("--assert-size", action="store_true",
                       help="Emit size asserts in Python output.")
    g_out.add_argument("--compact-json", action="store_true",
                       help="Compact JSON (no pretty indent).")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Validate at least one output
    if not any([args.python, args.header, args.c_header, args.json]):
        parser.error("Choose at least one output: --python / --header / --c-header / --json")

    # Gather extra castxml flags
    extra = list(args.cx or [])
    if args.remainder:
        if args.remainder and args.remainder[0] == "--":
            extra += args.remainder[1:]
        else:
            extra += args.remainder

    # 1) Acquire XML: either use the XML file directly, or run castxml on a header
    input_path: Path = args.input
    tmp_xml: Optional[Path] = None

    if input_path.suffix.lower() == ".xml":
        xml_path = input_path
        if not xml_path.exists():
            parser.error(f"XML not found: {xml_path}")
    else:
        # Header → XML using the runner
        if not input_path.exists():
            parser.error(f"Header not found: {input_path}")

        # Determine where to write the intermediate XML
        if args.xml_out is not None:
            xml_path = args.xml_out
        else:
            tf = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
            tmp_xml = Path(tf.name)
            tf.close()
            xml_path = tmp_xml

        try:
            run_castxml_for_header(
                header=input_path,
                xml_out=xml_path,
                castxml_bin=find_castxml(args.castxml),
                include_dirs=args.include,
                extra_args=extra,
                cpp_std=args.std,
            )
            # runner prints the command and surfaces errors already
        except CastxmlRunError as e:
            # error already printed in the runner; exit with same code
            return e.result.returncode

    # 2) Parse XML → defs
    defs = parse(str(xml_path))

    # 3) Manipulations
    exclude_patterns = []
    if args.exclude_system:
        exclude_patterns.extend(get_system_include_regexes())
    for pat in args.exclude_source:
        exclude_patterns.append(re.compile(pat))
    if exclude_patterns:
        defs = filter_by_source_regexes(defs, exclude=exclude_patterns)

    if args.pad_bitfield_holes:
        defs = fill_bitfield_holes_with_padding(defs)
    if args.pad_struct_holes:
        defs = fill_struct_holes_with_padding_bytes(defs)
    if args.resolve_typedefs:
        defs = resolve_typedefs(defs)
    if args.flatten_namespaces:
        defs = flatten_namespaces(defs)
    if args.focus:
        defs = filter_connected_definitions(defs, args.focus)

    # 4) Outputs
    if args.python:
        code = generate_python_code_from_definitions(defs, assert_size=args.assert_size)
        _write_text(args.python, code)
        print(f"[hida] wrote {args.python}")

    if args.header:
        write_header_from_definitions(defs, str(args.header))
        print(f"[hida] wrote {args.header}")

    if args.c_header:
        write_c_header_from_definitions(defs, str(args.c_header))
        print(f"[hida] wrote {args.c_header}")

    if args.json:
        text = json.dumps(
            _jsonable(defs),
            indent=None if args.compact_json else 2,
            ensure_ascii=False,
        )
        _write_text(args.json, text)
        print(f"[hida] wrote {args.json}")

    # 5) Cleanup temp XML if created
    if tmp_xml and tmp_xml.exists():
        try:
            tmp_xml.unlink()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
