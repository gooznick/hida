from __future__ import annotations

import os
import platform
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
import sys
import shutil

try:
    # Python 3.9+
    from importlib.resources import files, as_file
    HAVE_FILES = True
except ImportError:
    # Python 3.8 and below
    import importlib.resources as resources
    HAVE_FILES = False
    

from . import msvc_runner

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




VENDOR_PKG = "hida.bin"
BUNDLED_EXE = "castxml.exe"


def find_castxml(user_path: Optional[str | os.PathLike] = None) -> Path:
    """
    Resolve a usable castxml executable path.

    Precedence:
    1) user_path (if provided and exists)
    2) bundled Windows binary (only on Windows)
    3) system PATH (shutil.which)

    Returns:
        Path to an executable. Raises FileNotFoundError if none found.
    """
    # 1) User override
    if user_path:
        p = Path(user_path)
        if p.is_file():
            return p.resolve()
        raise FileNotFoundError(f"castxml not found at user path: {p}")

    # 2) Bundled exe (Windows only)
    if _IS_WINDOWS:
        try:
            if HAVE_FILES:
                # Python 3.9+
                target = files(VENDOR_PKG).joinpath(BUNDLED_EXE)
                with as_file(target) as real_path:
                    rp = Path(real_path)
                    if rp.is_file():
                        return rp.resolve()
            else:
                # Python 3.8 fallback
                import importlib.resources as resources
                with resources.path(VENDOR_PKG, BUNDLED_EXE) as real_path:
                    rp = Path(real_path)
                    if rp.is_file():
                        return rp.resolve()
        except ModuleNotFoundError:
            pass
        except Exception:
            pass

    # 3) PATH
    found = shutil.which("castxml")
    if found:
        return Path(found).resolve()

    raise FileNotFoundError(
        "castxml executable not found. "
        "Provide user_path, install castxml in PATH, or use the Windows-bundled binary."
    )



def run_castxml_for_header(
    header: Path,
    xml_out: Path,
    *,
    castxml_bin: Optional[str | Path] = None,
    include_dirs: Iterable[Path] = (),
    extra_args: Sequence[str] = (),
    cpp_std: str = "c++17",
    skip_env: bool = False,
    env_script: Optional[str | Path] = None,
) -> CastxmlResult:
    """
    Run castxml for a single header, writing XML to xml_out.
    Creates a temporary TU that #includes the header.

    On failure, raises CastxmlRunError and **preserves** the temporary TU file
    so the user can debug (and prints a message with its path).
    On success, the temporary file is deleted.
    """
    header = header.resolve()
    xml_out = xml_out.resolve()
    xml_out.parent.mkdir(parents=True, exist_ok=True)

    cx = find_castxml(castxml_bin)

    tmp_cpp_path: Optional[Path] = None
    success = False  # <- track outcome

    try:
        # Create a temporary .cpp that includes the header
        with tempfile.NamedTemporaryFile(
            suffix=".cpp", mode="w", delete=False
        ) as tmp_cpp:
            tmp_cpp.write(f'#include "{header}"\n')
            tmp_cpp_path = Path(tmp_cpp.name)

        cmd: List[str] = [cx, "--castxml-output=1"]

        if _IS_WINDOWS:
            # MSVC front-end uses /std:c++17 style
            cmd += ["--castxml-cc-msvc", "cl"]
        else:
            cmd += ["--castxml-cc-gnu", "g++", f"--std={cpp_std}"]

        # Includes
        for inc in include_dirs:
            cmd += ["-I", str(inc)]

        # Output and input TU
        cmd += ["-o", str(xml_out), str(tmp_cpp_path)]

        # Extra args (insert early so they’re visible in the printout)
        if extra_args:
            cmd[1:1] = list(extra_args)

        # Show the full command
        print("Running castxml command:\n$", _format_cmd(cmd))

        if _IS_WINDOWS:
            # Use MSVC runner to set up env if needed
            proc = msvc_runner.MSVCEnvRunner(skip_env, env_script).run(cmd)
        else:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

        result = CastxmlResult(
            header=header,
            xml_out=xml_out,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmd=cmd,
        )

        if proc.returncode != 0:
            # Keep the temp TU for debugging and tell the user
            if tmp_cpp_path is not None:
                sys.stderr.write(
                    f"\n[castxml] Failure (rc={proc.returncode}). "
                    f"Temporary TU preserved at:\n  {tmp_cpp_path}\n"
                    f"You can re-run (or inspect/preprocess) with the same command:\n  $ {_format_cmd(cmd)}\n\n"
                )
            raise CastxmlRunError(result)

        success = True
        return result

    finally:
        # Only delete the temp TU if we succeeded
        if success and tmp_cpp_path and tmp_cpp_path.exists():
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
