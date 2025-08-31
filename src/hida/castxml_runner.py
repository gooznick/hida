from __future__ import annotations

import os
import platform
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

_IS_WINDOWS = platform.system() == "Windows"


@dataclass
class CastxmlResult:
    header: Path
    xml_out: Path
    returncode: int
    stdout: str
    stderr: str
    cmd: List[str]


class CastxmlRunError(RuntimeError):
    def __init__(self, result: CastxmlResult):
        self.result = result
        msg = [
            "castxml failed.",
            f"Return code: {result.returncode}",
            "Command:",
            _format_cmd(result.cmd),
            "--- stdout ---",
            (result.stdout or "<empty>"),
            "--- stderr ---",
            (result.stderr or "<empty>"),
        ]
        super().__init__("\n".join(msg))


def find_castxml(explicit: Optional[str | Path] = None) -> str:
    """
    Resolve castxml executable:
    1) explicit path argument
    2) CASTXML_BIN env var
    3) PATH lookup
    """
    if explicit:
        p = Path(str(explicit))
        if p.exists():
            return str(p)

    env = os.getenv("CASTXML_BIN")
    if env and Path(env).exists():
        return env

    from shutil import which
    exe_name = "castxml.exe" if _IS_WINDOWS else "castxml"
    exe = which(exe_name) or which("castxml")
    if exe:
        return exe

    raise FileNotFoundError(
        "castxml executable not found.\n"
        "Hints:\n"
        "  • On Linux: install via your package manager (e.g., `sudo apt install castxml`).\n"
        "  • On Windows: download a release ZIP and set CASTXML_BIN or pass --castxml PATH.\n"
    )


def run_castxml_for_header(
    header: Path,
    xml_out: Path,
    *,
    castxml_bin: Optional[str | Path] = None,
    include_dirs: Iterable[Path] = (),
    extra_args: Sequence[str] = (),
    cpp_std: str = "c++17",
) -> CastxmlResult:
    """
    Run castxml for a single header, writing XML to xml_out.
    Creates a temporary TU that #includes the header.

    Raises CastxmlRunError on failure; returns CastxmlResult on success.
    """
    header = header.resolve()
    xml_out = xml_out.resolve()
    xml_out.parent.mkdir(parents=True, exist_ok=True)

    cx = find_castxml(castxml_bin)

    # Create a temporary .cpp that includes the header (robust against headers needing TU context).
    tmp_cpp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as tmp_cpp:
            tmp_cpp.write(f'#include "{header}"\n')
            tmp_cpp_path = Path(tmp_cpp.name)

        cmd: List[str] = [cx, "--castxml-output=1"]

        if _IS_WINDOWS:
            # Use MSVC front-end by default; /std:c++17 for MSVC, not -std=c++17
            cmd += ["--castxml-cc-msvc", "cl", f"/std:{cpp_std}"]
        else:
            cmd += [f"--std={cpp_std}"]

        # Includes
        for inc in include_dirs:
            cmd += ["-I", str(inc)]

        # Output and input TU
        cmd += ["-o", str(xml_out), str(tmp_cpp_path)]

        # Extra args forwarded (placed near the end, before source is OK too)
        if extra_args:
            cmd[1:1] = list(extra_args)  # insert after executable for visibility; harmless

        # Print full command (shell-like)
        print("$", _format_cmd(cmd))

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        result = CastxmlResult(
            header=header,
            xml_out=xml_out,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmd=cmd,
        )

        if proc.returncode != 0:
            raise CastxmlRunError(result)

        return result
    finally:
        if tmp_cpp_path and tmp_cpp_path.exists():
            try:
                tmp_cpp_path.unlink()
            except Exception:
                pass


def run_castxml_for_directory(
    input_dir: Path,
    output_dir: Path,
    *,
    castxml_bin: Optional[str | Path] = None,
    include_dirs: Iterable[Path] = (),
    extra_args: Sequence[str] = (),
    cpp_std: str = "c++17",
    exts: Tuple[str, ...] = (".h", ".hpp", ".hh", ".hxx"),
) -> List[CastxmlResult]:
    """
    Recursively process a directory of headers. Returns a list of CastxmlResult
    (successes and failures). Failures are represented by results coming from the
    exception path; callers can catch individually if preferred.
    """
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    results: List[CastxmlResult] = []
    for ext in exts:
        for header in input_dir.rglob(f"*{ext}"):
            xml_out = output_dir / (header.stem + ".xml")
            try:
                r = run_castxml_for_header(
                    header,
                    xml_out,
                    castxml_bin=castxml_bin,
                    include_dirs=include_dirs,
                    extra_args=extra_args,
                    cpp_std=cpp_std,
                )
                results.append(r)
            except CastxmlRunError as e:
                # Print a concise error per file, but keep going
                print(f"[ERROR] {header} -> {xml_out}")
                print(str(e))
                # Still append a result-like object so callers can see what failed
                results.append(e.result)
    return results


def _format_cmd(cmd: Sequence[str]) -> str:
    """Pretty-print a command with quoting similar to a shell."""
    try:
        return shlex.join(list(cmd))
    except Exception:
        # Fallback: manual quoting
        def q(s: str) -> str:
            return f'"{s}"' if (" " in s or "\t" in s) else s
        return " ".join(q(str(c)) for c in cmd)
