# msvc_runner.py
# Run a command under MSVC/VS env on Windows by generating a TEMP .BAT:
#   @echo off
#   pushd "%CD%"
#   call "<env_script>" <args>
#   <your command>
#   popd
#   exit /b %errorlevel%
#
# This keeps everything in ONE cmd.exe and returns your command's exit code.
# Also exports a free finder: find_msvc_env_script(...)

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Union

Cmd = Union[str, Sequence[str]]

__all__ = ["MSVCEnvRunner", "find_msvc_env_script"]

# ─────────────────────────── Finder ───────────────────────────

def find_msvc_env_script(
    env_script: Optional[Union[str, Path]] = None,
    *, debug: bool = False, prefer_vcvarsall: bool = False,
) -> str:
    """Locate VsDevCmd.bat or vcvarsall.bat (Windows only)."""
    if not _is_windows():
        raise FileNotFoundError("MSVC env script is only relevant on Windows.")
    if env_script:
        p = _normalize_script_path(str(env_script))
        if not Path(p).is_file():
            raise FileNotFoundError(f"MSVC environment script not found: {p}")
        if debug: print(f"[find_msvc_env_script] explicit: {p}")
        return p

    roots: List[Path] = []
    for var in ("VSINSTALLDIR", "VCINSTALLDIR"):
        v = os.environ.get(var)
        if v: roots.append(Path(v))

    vsw = _vswhere_path()
    if vsw and vsw.exists():
        roots += [Path(ip) for ip in _vswhere_install_paths(vsw)]

    for base in _default_vs_roots():
        for ver in ("2022", "2019", "2017"):
            for ed in ("Community", "Professional", "Enterprise", "BuildTools"):
                roots.append(base / ver / ed)

    seen = set()
    def cands(root: Path) -> List[Path]:
        order = [
            root / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat",
            root / "Common7" / "Tools" / "VsDevCmd.bat",
        ]
        if not prefer_vcvarsall:
            order.reverse()  # VsDevCmd first
        return order

    for r in roots:
        rp = r.resolve()
        if rp in seen: continue
        seen.add(rp)
        for c in cands(rp):
            if c.is_file():
                if debug: print(f"[find_msvc_env_script] found: {c}")
                return str(c)

    raise FileNotFoundError("Could not auto-locate a VS environment script.")

# ─────────────────────────── Runner ───────────────────────────

class MSVCEnvRunner:
    """
    Run a command within a VS/MSVC environment in ONE cmd.exe by emitting a temp .bat.

    Params
    ------
    skip_env: bool                -> run like subprocess.run without VS env
    env_script: str|Path|None     -> explicit VsDevCmd/vcvarsall path (no quotes)
    env_args: str|None            -> 'x64'/'x86'/... or devcmd flags; we normalize
    prefer_vcvarsall: bool        -> choose vcvarsall first when discovering
    debug: bool                   -> print composed commands/paths
    """

    def __init__(
        self,
        skip_env: bool = False,
        env_script: Optional[Union[str, Path]] = None,
        env_args: Optional[str] = None,
        prefer_vcvarsall: bool = False,
        debug: bool = False,
    ) -> None:
        self.skip_env = bool(skip_env)
        self._env_script_raw = str(env_script) if env_script else None
        self.env_args = (env_args or "").strip()
        self.prefer_vcvarsall = prefer_vcvarsall
        self.debug = debug

    def run(self, cmd: Cmd, **kwargs) -> subprocess.CompletedProcess:
        """Emit a temp .bat that calls the env script and then runs `cmd`."""
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
        kwargs.setdefault("text", True)

        if not _is_windows() or self.skip_env:
            return subprocess.run(cmd, **kwargs)

        # 1) resolve script + normalize args
        script = find_msvc_env_script(
            self._env_script_raw, debug=self.debug, prefer_vcvarsall=self.prefer_vcvarsall
        )
        kind = _script_kind(script)
        args = _format_env_args_for_script(kind, self.env_args)

        # 2) build user command line as a single string
        user_cmd = _cmd_to_string(cmd)

        # 3) prepare safe prologue: pushd to current dir (handles UNC), optional cd
        prologue = 'pushd "%CD%"\r\n'
        # If current dir is UNC and pushd fails, still run from %SystemRoot%
        try:
            if os.getcwd().startswith("\\\\"):
                prologue = 'pushd "%CD%" || cd /d %SystemRoot%\\System32\r\n'
        except Exception:
            prologue = 'pushd "%CD%" || cd /d %SystemRoot%\\System32\r\n'

        # 4) write wrapper .bat
        bat_text = (
            "@echo off\r\n"
            + prologue +
            f'call "{_normalize_script_path(script)}" {args}\r\n'
            f"{user_cmd}\r\n"
            "set EXITCODE=%ERRORLEVEL%\r\n"
            "popd\r\n"
            "exit /b %EXITCODE%\r\n"
        )
        if self.debug:
            print(f"[MSVCEnvRunner] using script : {script}")
            print(f"[MSVCEnvRunner] script args  : {args or '(none)'}")
            print(f"[MSVCEnvRunner] user command : {user_cmd}")

        with tempfile.TemporaryDirectory() as td:
            bat_path = Path(td) / "hida_run.bat"
            bat_path.write_text(bat_text, encoding="utf-8", newline="\r\n")

            comspec = os.environ.get("COMSPEC", "cmd.exe")
            cmdline = f'{comspec} /d /c "{bat_path}"'
            if self.debug:
                print(f"[MSVCEnvRunner] exec: {cmdline}")
                # print(f"[MSVCEnvRunner] BAT:\n{bat_text}")

            # 5) run the single-hop batch (caller-provided env applies to cmd.exe)
            return subprocess.run(cmdline, shell=True, **kwargs)

# ─────────────────────────── Internals ───────────────────────────

def _script_kind(script_path: str) -> str:
    name = Path(script_path).name.lower()
    if "vsdevcmd" in name: return "vsdevcmd"
    if "vcvarsall" in name: return "vcvarsall"
    return "unknown"

def _format_env_args_for_script(kind: str, env_args: str) -> str:
    """Translate bare arches for VsDevCmd; pass-through for vcvarsall."""
    args = (env_args or "").strip()
    if not args:
        return ""
    if kind == "vsdevcmd":
        arch_alias = {
            "x64": "x64", "amd64": "x64",
            "x86": "x86", "win32": "x86",
            "arm64": "arm64",
        }
        out: List[str] = []
        arch_set = False
        for tok in args.split():
            if tok.startswith("-"):
                out.append(tok)
            else:
                alias = arch_alias.get(tok.lower())
                if alias and not arch_set:
                    out.append(f"-arch={alias}")
                    arch_set = True
                else:
                    out.append(tok)
        s = " ".join(out)
        if "-startdir=" not in s: s += " -startdir=none"
        if "-no_logo"  not in s: s += " -no_logo"
        return s
    return args  # vcvarsall

def _cmd_to_string(cmd: Cmd) -> str:
    if isinstance(cmd, (list, tuple)):
        return subprocess.list2cmdline(list(cmd))
    return str(cmd)

def _normalize_script_path(raw: str) -> str:
    s = raw.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if s.startswith(r'\"') and s.endswith(r'\"'):
        s = s[2:-2].strip()
    return str(Path(s))

def _default_vs_roots() -> List[Path]:
    roots: List[Path] = []
    for var, fb in (("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                    ("ProgramFiles", r"C:\Program Files")):
        base = Path(os.environ.get(var, fb)) / "Microsoft Visual Studio"
        if base.exists(): roots.append(base)
    return roots

def _vswhere_path() -> Optional[Path]:
    pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    p = Path(pfx86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    return p if p.exists() else None

def _vswhere_install_paths(vswhere: Path) -> List[str]:
    try:
        out = subprocess.check_output(
            [
                str(vswhere),
                "-products", "*",
                "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property", "installationPath",
            ],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        return [ln for ln in out.splitlines() if ln.strip()]
    except Exception:
        return []

def _is_windows() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")

# ─────────────────────────── Smoke ───────────────────────────

if __name__ == "__main__":
    if _is_windows():
        r = MSVCEnvRunner(env_args="x64", prefer_vcvarsall=True, debug=True)
        out = r.run(["where", "cl"])
        print("RC:", out.returncode)
        print("STDOUT:\n", out.stdout)
        print("STDERR:\n", out.stderr)
    else:
        print("Non-Windows platform")
