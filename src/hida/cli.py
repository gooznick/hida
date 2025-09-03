from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import List, Optional
from textwrap import dedent

# Public API you already expose in __init__.py
from hida import (
    parse,
    # emitters
    write_header_from_definitions,
    write_c_header_from_definitions,
    python_generate,
    dumps, load,
    filter_by_source_regexes,
    filter_by_name_regexes,
    fill_bitfield_holes_with_padding,
    fill_struct_holes_with_padding_bytes,
    flatten_namespaces,
    resolve_typedefs,
    filter_connected_definitions,
    flatten_structs,
    remove_enums,
    remove_source,
)

# CastXML runner
from .castxml_runner import (
    find_castxml,
    run_castxml_for_header,
    CastxmlRunError,
)


# ---------- helpers ----------


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------- CLI ----------


# Nice help: defaults + preserved newlines/indent
class _HelpFmt(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    pass

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hida",
        formatter_class=_HelpFmt,
        allow_abbrev=False,
        description=dedent("""\
            CastXML XML → Python/Header/JSON with IR manipulators.

            INPUT MODES
              • CastXML XML   : use an existing CastXML XML file
              • JSON IR       : use a previously generated JSON IR file
              • C/C++ header  : run CastXML on the header (see CASTXML FORWARDING)
            """),
        epilog=dedent("""\
            CASTXML FORWARDING
              Anything after a literal `--` on the command line is passed verbatim to CastXML
              when the input is a header. The forwarded args are available as `args.castxml_args`.

              Examples:
                hida include/foo.hpp -I include -x build/foo.xml -- --castxml-cc-gnu g++ -DDEBUG
                hida include/foo.hpp -- --std=c++20 -isystem /opt/clang/include/c++/v1

            EXAMPLES
              # Use an existing CastXML XML and emit Python:
              hida build/foo.xml --python out.py

              # Use a header (runs CastXML), keep intermediate XML, then emit a C++ header:
              hida include/foo.hpp -I include -x build/foo.xml --header api.hpp

              # Use a JSON IR:
              hida api.json --header api.hpp
            """),
    )

    # ──────────────────────────────
    # POSITIONAL INPUT (first arg)  ← requirement #3
    # ──────────────────────────────
    p.add_argument(
        "input",
        type=Path,
        help=(
            "Input file: CastXML XML, JSON IR, or a C/C++ header. "  # ← requirement #4
            "If a header is given, hida will invoke CastXML (see CASTXML FORWARDING below)."
        ),
    )

    # INPUT
    g_in = p.add_argument_group("input")

    g_in.add_argument(
        "-I",
        "--include",
        action="append",
        default=[],
        type=Path,
        help="Include directory for CastXML (repeatable; header input only).",
    )
    g_in.add_argument(
        "-x",
        "--xml-out",
        type=Path,
        default=None,
        help="Where to write the intermediate XML (if input is a header).",
    )
    g_in.add_argument(
        "--castxml",
        type=Path,
        default=None,
        help="Path to CastXML executable. If omitted, uses CASTXML_BIN or PATH.",
    )
    g_in.add_argument(
        "--std",
        default="c++17",
        help="C++ language standard for CastXML (e.g., c++17, c++20).",
    )


    g_p = p.add_argument_group("parsing")
    g_p.add_argument(
        "--use_bool",
        action="store_true",
        help="Use bool as a type.",
    )
    g_p.add_argument(
        "--do_not_ignore_system",
        action="store_true",
        help="Do not ignore system includes.",
    )
    g_p.add_argument(
        "--verbose",
        action="store_true",
        help="Write parsing warnings.",
    )
    g_p.add_argument(
        "--do_not_skip_failed_parsing",
        action="store_true",
        help="Error if failed to parse.",
    )
    # MANIPULATORS
    g_m = p.add_argument_group("manipulators")

    g_m.add_argument(
        "--name-include",
        action="append",
        default=[],
        metavar="REGEX",
        help="Regex to include by definition name (repeatable). If provided, only matching names are kept.",
    )
    g_m.add_argument(
        "--name-exclude",
        action="append",
        default=[],
        metavar="REGEX",
        help="Regex to exclude by definition name (repeatable).",
    )
    # Source filters
    g_m.add_argument(
        "--source-include",
        action="append",
        default=[],
        help="Regex to include by source file or the definition (repeatable). If given, only matching sources are kept.",
    )
    g_m.add_argument(
        "--source-exclude",
        action="append",
        default=[],
        help="Regex to exclude by source file or the definition (repeatable).",
    )

    # Typedef + namespaces
    g_m.add_argument(
        "--resolve-typedefs",
        action="store_true",
        help="Resolve/inline typedefs and remove TypedefDefinition nodes.",
    )
    g_m.add_argument(
        "--flatten-namespaces",
        action="store_true",
        help="Flatten namespaces into names using a '__' separator.",
    )

    # Enums
    g_m.add_argument(
        "--remove-enums",
        action="store_true",
        help="Replace EnumDefinition uses with integers and drop enum declarations.",
    )
    g_m.add_argument(
        "--enum-int-type",
        default="int",
        help="Fallback integer type to use for enums with unknown underlying type.",
    )

    # Struct flattening
    g_m.add_argument(
        "--flatten-structs",
        action="extend",
        nargs="+",
        default=[],
        help="Struct/union types to flatten (name or fullname). Repeat or pass multiple names.",
    )
    g_m.add_argument(
        "--flatten-sep",
        default="__",
        help="Separator for names created by flattening.",
    )
    g_m.add_argument(
        "--flatten-arrays",
        action="store_true",
        help="When flattening, also inline arrays of composite types.",
    )

    # Graph trimming + ordering
    g_m.add_argument(
        "--focus",
        action="extend",
        nargs="+",
        default=[],
        help="Keep only definitions connected to these root types (repeat or pass multiple).",
    )


    # Padding
    g_m.add_argument(
        "--pad-bitfield-holes",
        action="store_true",
        help="Fill bitfield holes with synthetic bitfield padding members.",
    )
    g_m.add_argument(
        "--pad-struct-holes",
        action="store_true",
        help="Fill byte-aligned struct holes with uint8_t padding members/arrays.",
    )
    g_m.add_argument(
        "--pad",
        action="store_true",
        help="Both --pad-struct-holes and --pad-bitfield-holes.",
    )
    # Source scrubbing
    mx = g_m.add_mutually_exclusive_group()
    mx.add_argument(
        "--remove-source",
        action="store_true",
        help="Blank the 'source' field for all definitions.",
    )
    mx.add_argument(
        "--remove-source-basename",
        action="store_true",
        help="Keep only the basename in 'source' (preserves '<built-in>').",
    )

    # OUTPUTS
    g_out = p.add_argument_group("output")
    g_out.add_argument(
        "--python", type=Path, default=None, help="Write generated Python to this file."
    )
    g_out.add_argument(
        "--header",
        "--h",
        dest="header",
        type=Path,
        default=None,
        help="Write generated C++-style header to this file.",
    )
    g_out.add_argument(
        "--c-header",
        dest="c_header",
        type=Path,
        default=None,
        help="Write generated C header to this file.",
    )
    g_out.add_argument(
        "--json", type=Path, default=None, help="Write JSON IR to this file."
    )
    g_out.add_argument(
        "--assert-size", action="store_true", help="Emit size asserts in Python output."
    )
    g_out.add_argument(
        "--python-verify", action="store_true", help="Verify python output."
    )
    g_out.add_argument(
        "--python-verify-size", action="store_true", help="Verify python output and size."
    )
    g_out.add_argument(
        "--compact-json", action="store_true", help="Compact JSON (no pretty indent)."
    )

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    # We want to forward unknown flags to CastXML, so use parse_known_args
    args, unknown = parser.parse_known_args(argv)
    extra = list(unknown or [])

    # Require at least one output
    if not any([args.python, args.header, args.c_header, args.json]):
        parser.error(
            "Choose at least one output: --python / --header / --c-header / --json"
        )

    # 1) Get XML: path directly or generate from header via runner
    input_path: Path = args.input
    tmp_xml: Optional[Path] = None
    json_path: Optional[Path] = None

    if input_path.suffix.lower() == ".xml":
        xml_path = input_path
        if not xml_path.exists():
            parser.error(f"XML not found: {xml_path}")
        if extra:
            print(
                f"[hida] Warning: extra args {extra} ignored when input is XML",
                file=sys.stderr,
            )
    elif input_path.suffix.lower() == ".json":
        json_path = input_path
        if not json_path.exists():
            parser.error(f"JSON not found: {json_path}")
        if extra:
            print(
                f"[hida] Warning: extra args {extra} ignored when input is JSON",
                file=sys.stderr,
            )
    else:
        if not input_path.exists():
            parser.error(f"Header not found: {input_path}")

        if args.xml_out is not None:
            xml_path = args.xml_out
        else:
            tf = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
            tmp_xml = Path(tf.name)
            tf.close()
            xml_path = tmp_xml

        run_castxml_for_header(
            header=input_path,
            xml_out=xml_path,
            castxml_bin=find_castxml(args.castxml),
            include_dirs=args.include,
            extra_args=extra,
            cpp_std=args.std,
        )


    # 2) Parse XML → defs
    if json_path:
        defs = load(json_path)
    else:
        defs = parse(str(xml_path),use_bool=args.use_bool,do_not_ignore_system=args.do_not_ignore_system,
                    verbose=args.verbose, skip_failed_parsing=not args.do_not_skip_failed_parsing )

    # 3) Manipulations (order chosen to be practical)

    # 3.1 Source-based filtering
    include_src = [*args.source_include] if args.source_include else []
    exclude_src = [*args.source_exclude] if args.source_exclude else []
    if include_src or exclude_src:
        defs = filter_by_source_regexes(
            defs, include=include_src or None, exclude=exclude_src or None
        )

    # 3.2 Name-based filtering
    include_name = [*args.name_include] if args.name_include else []
    exclude_name = [*args.name_exclude] if args.name_exclude else []
    if include_name or exclude_name:
        defs = filter_by_name_regexes(
            defs, include=include_name or None, exclude=exclude_name or None
        )

    # 3.2 Typedefs and namespaces
    if args.resolve_typedefs:
        defs = resolve_typedefs(defs)
    if args.flatten_namespaces:
        defs = flatten_namespaces(defs)

    # 3.3 Enums
    if args.remove_enums:
        defs = remove_enums(defs, default_int_type=args.enum_int_type)

    # 3.4 Flatten selected composites
    if args.flatten_structs:
        defs = flatten_structs(
            defs,
            targets=args.flatten_structs,
            separator=args.flatten_sep,
            flatten_arrays=args.flatten_arrays,
        )

    # 3.5 Padding (after flatten so new holes can be handled)
    if args.pad:
        defs = fill_bitfield_holes_with_padding(defs)
        defs = fill_struct_holes_with_padding_bytes(defs)

    if args.pad_bitfield_holes:
        defs = fill_bitfield_holes_with_padding(defs)
    if args.pad_struct_holes:
        defs = fill_struct_holes_with_padding_bytes(defs)

    # 3.6 Focus/trim (after transforms so we keep only the needed set)
    if args.focus:
        defs = filter_connected_definitions(defs, args.focus)

    # 3.8 Source scrubbing (presentation concern; do last)
    if args.remove_source or args.remove_source_basename:
        defs = remove_source(defs, header_only=bool(args.remove_source_basename))

    # 4) Outputs
    if args.python:
        python_generate(defs, args.python, assert_size=args.assert_size, verify=args.python_verify, verify_size=args.python_verify_size)
        print(f"[hida] wrote {args.python}")

    if args.header:
        code = write_header_from_definitions(defs)
        _write_text(args.header, code)
        print(f"[hida] wrote {args.header}")

    if args.c_header:
        code = write_c_header_from_definitions(defs)
        _write_text(args.c_header, code)
        print(f"[hida] wrote {args.c_header}")

    if args.json:
        text = dumps(
            defs,
            indent=None if args.compact_json else 2,
        )
        _write_text(args.json, text)
        print(f"[hida] wrote {args.json}")

    # 5) Cleanup temp XML
    if tmp_xml and tmp_xml.exists():
        try:
            tmp_xml.unlink()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
