# msvc_runner.py
# Run commands with the MSVC/VS environment on Windows by:
#  1) discovering VsDevCmd.bat or vcvarsall.bat
#  2) launching a TEMP WRAPPER .BAT that `CALL`s the script then executes `set`
#  3) parsing the environment dump and reusing it for your real subprocess
#
# Why a wrapper .bat?
#  - Keeps `set` in the SAME batch context (avoids && short-circuit, preserves SETLOCAL)
#  - Robust across VsDevCmd/vcvarsall differences and non-zero ERRORLEVEL banners
#
# Public API:
#  - find_msvc_env_script(...): discover the env script path (Windows only)
#  - MSVCEnvRunner(...).run(cmd, **kwargs): run cmd with captured MSVC env
#
# Example:
#   runner = MSVCEnvRunner(env_args="x64", prefer_vcvarsall=True, debug=True)
#   cp = runner.run(["where", "cl"])
#   print(cp.stdout or cp.stderr)

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

Cmd = Union[str, Sequence[str]]

__all__ = ["MSVCEnvRunner", "find_msvc_env_script"]


# ─────────────────────────────────────────────────────────────────────────────
# Public: discover the VS/MSVC env script (Windows only)
# ─────────────────────────────────────────────────────────────────────────────

def find_msvc_env_script(
    env_script: Optional[Union[str, Path]] = None,
    *,
    debug: bool = False,
    prefer_vcvarsall: bool = False,
) -> str:
    """
    Locate a Visual Studio environment setup script on Windows.

    Resolution:
      0) explicit path (validated)
      1) env: VSINSTALLDIR / VCINSTALLDIR
      2) vswhere.exe (+ VC tools)
      3) default roots (2022/2019/2017; all editions)

    If prefer_vcvarsall=True, prefer vcvarsall.bat over VsDevCmd.bat when both exist.
    """
    if not _is_windows():
        raise FileNotFoundError("MSVC env script is only relevant on Windows.")

    # 0) explicit
    if env_script:
        path = _normalize_script_path(str(env_script))
        if not Path(path).is_file():
            raise FileNotFoundError(f"MSVC environment script not found: {path}")
        if debug:
            print(f"[find_msvc_env_script] explicit: {path}")
        return path

    roots: List[Path] = []

    # 1) env hints
    for var in ("VSINSTALLDIR", "VCINSTALLDIR"):
        val = os.environ.get(var)
        if val:
            roots.append(Path(val))

    # 2) vswhere
    vswhere = _vswhere_path()
    if vswhere and vswhere.exists():
        for ip in _vswhere_install_paths(vswhere):
            roots.append(Path(ip))

    # 3) defaults
    for base in _default_vs_roots():
        for ver in ("2022", "2019", "2017"):
            for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                roots.append(base / ver / edition)

    # Probe each root
    seen = set()

    def candidates_from_root(base: Path) -> List[Path]:
        # Prefer order adjusted by prefer_vcvarsall
        cands = [
            base / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat",
            base / "Common7" / "Tools" / "VsDevCmd.bat",
        ]
        if not prefer_vcvarsall:
            cands.reverse()  # VsDevCmd first
        return cands

    for base in roots:
        b = base.resolve()
        if b in seen:
            continue
        seen.add(b)
        for c in candidates_from_root(b):
            if c.is_file():
                if debug:
                    print(f"[find_msvc_env_script] found: {c}")
                return str(c)

    raise FileNotFoundError("Could not auto-locate a VS environment script (checked env vars, vswhere, and common roots).")


# ─────────────────────────────────────────────────────────────────────────────
# Runner: capture env via TEMP .BAT + `set`, then run your command with it
# ─────────────────────────────────────────────────────────────────────────────

class MSVCEnvRunner:
    """
    Run a command with optional MSVC environment setup on Windows by:
      1) launching a short-lived cmd.exe,
      2) calling the VS env script through a temp .bat,
      3) running `set` and parsing all variables,
      4) executing your command with that env (no `call ... && cmd` chain).

    Parameters
    ----------
    skip_env : bool
        If True, do not set up MSVC env; behave like subprocess.run.
    env_script : str | Path | None
        Path to VsDevCmd.bat or vcvarsall.bat (WITHOUT quotes). If omitted, auto-discovered.
    env_args : str | None
        Arguments for the env script: e.g. "x64"/"amd64"/"x86"/"arm64".
        Bare tokens are adapted to VsDevCmd flags (x64 -> -arch=x64).
    prefer_vcvarsall : bool
        Prefer vcvarsall.bat when searching (useful with bare arch tokens).
    debug : bool
        Print diagnostics (commands, selected script, key env vars).
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
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
        kwargs.setdefault("text", True)

        if not _is_windows() or self.skip_env:
            return subprocess.run(cmd, **kwargs)

        script = find_msvc_env_script(
            self._env_script_raw, debug=self.debug, prefer_vcvarsall=self.prefer_vcvarsall
        )
        env = _capture_env_via_wrapper(script, self.env_args, debug=self.debug)

        # Merge with current env; caller-provided env (if any) wins last
        merged_env = os.environ.copy()
        merged_env.update(env)
        if "env" in kwargs and kwargs["env"]:
            merged_env.update(kwargs["env"])
        kwargs["env"] = merged_env

        return subprocess.run(cmd, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────────────────────

def _capture_env_via_wrapper(script_path: str, script_args: str, *, debug: bool = False) -> Dict[str, str]:
    """
    Build the MSVC env dict by calling the script INSIDE a temp .bat, then `set`.
    This guarantees `set` sees the same batch context (no operator surprises).
    """
    script_path = _normalize_script_path(script_path)
    kind = _script_kind(script_path)
    args = _format_env_args_for_script(kind, script_args)

    # If the cwd is UNC (e.g. \\VBoxSvr\...), some scripts behave oddly.
    # Switch to a safe local dir during the env hop.
    cd_prefix = ""
    try:
        if os.getcwd().startswith("\\\\"):
            cd_prefix = "cd /d %SystemRoot%\\System32\r\n"
    except Exception:
        pass

    # Build wrapper .bat
    bat_text = (
        "@echo off\r\n"
        + cd_prefix +
        f'call "{script_path}" {args}\r\n'   # call even if args empty
        "set\r\n"
    )

    if debug:
        print(f"[MSVCEnvRunner] env script : {script_path}")
        print(f"[MSVCEnvRunner] script args: {args or '(none)'}")

    with tempfile.TemporaryDirectory() as td:
        bat_path = Path(td) / "hida_env_probe.bat"
        bat_path.write_text(bat_text, encoding="utf-8", newline="\r\n")

        comspec = os.environ.get("COMSPEC", "cmd.exe")
        cmdline = f'{comspec} /d /c "{bat_path}"'

        if debug:
            print(f"[MSVCEnvRunner] env-build via wrapper: {cmdline}")
            # Optionally show contents:
            # print(f"[MSVCEnvRunner] wrapper contents:\n{bat_text}")

        proc = subprocess.run(
            cmdline,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,  # preserve quoting for cmd.exe
        )

    if debug and proc.stderr:
        print("[MSVCEnvRunner] env-build stderr:", proc.stderr)

    if proc.returncode != 0 and not proc.stdout:
        # If the script failed and produced no env output, bail out
        raise RuntimeError(
            "Failed to capture MSVC environment; wrapper produced no output.\n"
            f"Script: {script_path}\nArgs: {args}\nStderr:\n{proc.stderr}"
        )

    # Parse env dump
    env: Dict[str, str] = {}
    for line in (proc.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k] = v

    if debug:
        for k in ("VSINSTALLDIR", "VCINSTALLDIR", "VCToolsInstallDir"):
            if k in env:
                print(f"[MSVCEnvRunner] {k} -> {env[k]}")
        if "PATH" in env:
            head = env["PATH"].split(";")[:8]
            print("[MSVCEnvRunner] PATH(head):", ";".join(head))

    return env


def _script_kind(script_path: str) -> str:
    name = Path(script_path).name.lower()
    if "vsdevcmd" in name:
        return "vsdevcmd"
    if "vcvarsall" in name:
        return "vcvarsall"
    return "unknown"


def _format_env_args_for_script(kind: str, env_args: str) -> str:
    """
    Normalize env_args for VsDevCmd vs vcvarsall.
      - vcvarsall: supports bare tokens like 'x64', 'x86', 'arm64'
      - VsDevCmd : prefers '-arch=x64' etc. We translate common bare tokens.
    Also add stability flags for VsDevCmd.
    """
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
                out.append(tok)  # already a devcmd flag
            else:
                alias = arch_alias.get(tok.lower())
                if alias and not arch_set:
                    out.append(f"-arch={alias}")
                    arch_set = True
                else:
                    out.append(tok)
        # Useful defaults (don’t change dir, reduce noise)
        s = " ".join(out)
        if "-startdir=" not in s:
            s += " -startdir=none"
        if "-no_logo" not in s:
            s += " -no_logo"
        return s
    # vcvarsall path: pass through unchanged
    return args


def _default_vs_roots() -> List[Path]:
    roots: List[Path] = []
    for var, fallback in (("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                          ("ProgramFiles", r"C:\Program Files")):
        base = Path(os.environ.get(var, fallback)) / "Microsoft Visual Studio"
        if base.exists():
            roots.append(base)
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
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return [line for line in out.splitlines() if line.strip()]
    except Exception:
        return []


def _normalize_script_path(raw: str) -> str:
    s = raw.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if s.startswith(r'\"') and s.endswith(r'\"'):
        s = s[2:-2].strip()
    return str(Path(s))


def _is_windows() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def _cmd_to_string(cmd: Cmd) -> str:
    return subprocess.list2cmdline(list(cmd)) if isinstance(cmd, (list, tuple)) else str(cmd)


# ─────────────────────────────────────────────────────────────────────────────
# Manual smoke test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if _is_windows():
        r = MSVCEnvRunner(env_args="x64", prefer_vcvarsall=True, debug=True)
        try:
            print(r.run(["where", "cl"]).stdout or r.run(["where", "cl"]).stderr)
        except Exception as e:
            print("Error:", e)
    else:
        print("Non-Windows platform")
