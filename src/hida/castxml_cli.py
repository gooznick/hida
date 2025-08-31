# src/hida/castxml_cli.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from .castxml_runner import (
    run_castxml_for_header,
    run_castxml_for_directory,
    CastxmlRunError,
    find_castxml,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hida-castxml",
        description="Wrapper to run castxml for a single header or an entire directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,  # avoid '-o' matching other long options accidentally
    )

    g_in = p.add_argument_group("input / mode")
    g_in.add_argument(
        "input",
        type=Path,
        help="Header file or directory. If directory, all headers are processed recursively.",
    )
    g_in.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="XML output file (single-file mode). If omitted, uses <header>.xml in --out-dir.",
    )
    g_in.add_argument(
        "-O",
        "--out-dir",
        type=Path,
        default=Path("castxml"),
        help="Output directory (directory mode, or used when --output not given).",
    )
    g_in.add_argument(
        "--ext",
        action="append",
        default=[".h", ".hpp", ".hh", ".hxx"],
        help="Header extensions to search in directory mode (repeatable).",
    )

    g_cx = p.add_argument_group("castxml / compiler options")
    g_cx.add_argument(
        "--castxml",
        type=Path,
        default=None,
        help="Path to castxml executable. If not set, use CASTXML_BIN env var or PATH.",
    )
    g_cx.add_argument(
        "-I",
        "--include",
        action="append",
        type=Path,
        default=[],
        help="Include directory for castxml (repeatable).",
    )
    g_cx.add_argument(
        "--std",
        default="c++17",
        help="C++ language standard to use (c++17, c++20, ...).",
    )
    g_cx.add_argument(
        "--cx",
        action="append",
        default=[],
        help="Extra argument forwarded to castxml/clang (repeatable). "
        "Unknown CLI args are also forwarded automatically.",
    )

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()

    # Parse known args; anything unknown gets forwarded to castxml
    args, unknown = parser.parse_known_args(argv)

    # Merge explicit --cx values and unknowns (e.g., things after -- or stray flags)
    extra = list(args.cx or []) + list(unknown or [])

    if args.input.is_dir():
        results = run_castxml_for_directory(
            input_dir=args.input,
            output_dir=args.out_dir,
            castxml_bin=args.castxml,
            include_dirs=args.include,
            extra_args=extra,
            cpp_std=args.std,
            exts=tuple(args.ext),
        )
        ok = sum(1 for r in results if r.returncode == 0)
        fail = len(results) - ok
        print(f"\nSummary: {ok} succeeded, {fail} failed.")
        return 0 if fail == 0 else 1

    # Single-file mode
    header: Path = args.input
    if not header.exists():
        parser.error(f"Header not found: {header}")

    xml_out = args.output or (args.out_dir / (header.stem + ".xml"))

    try:
        run_castxml_for_header(
            header=header,
            xml_out=xml_out,
            castxml_bin=find_castxml(args.castxml),
            include_dirs=args.include,
            extra_args=extra,
            cpp_std=args.std,
        )
        print(f"Wrote: {xml_out}")
        return 0
    except CastxmlRunError as e:
        # Runner already printed full command + stdout/stderr
        return e.result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
