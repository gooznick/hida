# msvc_runner.py
# A robust subprocess wrapper that can (optionally) load MSVC/VS build
# environment (via VsDevCmd.bat/vcvarsall.bat) before running a command.
#
# Key features:
# - skip_env=True: behave like plain subprocess.run (useful when already in a Dev Prompt).
# - env_script=<path>: explicitly pick which VS env .bat to load (no quotes needed).
# - Auto-discovery when env_script is not provided: tries VSINSTALLDIR/VCINSTALLDIR,
#   vswhere.exe, and common Visual Studio install roots.
# - Builds the MSVC environment in a child cmd.exe and parses `set` output,
#   then runs your command with that environment (no fragile "call ... && <cmd>" chain).
#
# Usage example:
#
#   from msvc_runner import MSVCEnvRunner
#
#   runner = MSVCEnvRunner(env_args="x64", debug=True)
#   proc = runner.run(["where", "cl"])  # should print path(s) to cl.exe in stdout
#   print(proc.stdout)
#
#   # Already in Developer Command Prompt (or you don't need MSVC env):
#   runner = MSVCEnvRunner(skip_env=True)
#   proc = runner.run(["castxml", "--version"])
#
#   # Explicit script (pass WITHOUT quotes):
#   runner = MSVCEnvRunner(
#       env_script=r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
#       env_args="x64",
#       debug=True
#   )
#   proc = runner.run(["cl", "/?"])

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

Cmd = Union[str, Sequence[str]]

__all__ = ["MSVCEnvRunner"]


class MSVCEnvRunner:
    """
    Run a command with optional MSVC environment setup on Windows.

    Parameters
    ----------
    skip_env :
        If True, do not attempt to load the MSVC environment; run like plain subprocess.run.
        Use this when you already launched your Python from a Developer Command Prompt.
    env_script :
        Full path to the VS environment setup script (e.g., VsDevCmd.bat or vcvarsall.bat).
        Pass WITHOUT quotes. If omitted, auto-discovery is attempted.
    env_args :
        Optional arguments passed to the env script, e.g. "x64", "amd64", "x86", "arm64".
    debug :
        If True, prints helpful debug messages (e.g., the exact cmd used to build env).

    Behavior
    --------
    - On non-Windows platforms or when skip_env=True, this behaves like subprocess.run.
    - On Windows and skip_env=False:
        1) Resolve env script (explicit path OR auto-discovery).
        2) Launch a child cmd.exe to `call <script> <args> && set`, parse env vars.
        3) Run the requested command with those env vars injected (no quoting pitfalls).

    Notes
    -----
    - We intentionally use a single-string command with shell=True for the env-build hop
      to avoid Python adding backslash-escaped quotes that confuse cmd.exe.
    - Your actual command runs WITHOUT shell=True, unless you pass it yourself via kwargs.
    """

    def __init__(
        self,
        skip_env: bool = False,
        env_script: Optional[Union[str, Path]] = None,
        env_args: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        self.skip_env = bool(skip_env)
        self._env_script_raw = str(env_script) if env_script else None
        self.env_args = (env_args or "").strip()
        self.debug = debug

    # -------------------- public API --------------------

    def run(self, cmd: Cmd, **kwargs) -> subprocess.CompletedProcess:
        """
        Run the command with (optional) MSVC environment primed.

        kwargs are passed to subprocess.run. By default we capture stdout/stderr as text to
        match the user's original pattern (you can override these).
        """
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
        kwargs.setdefault("text", True)

        if not self._is_windows() or self.skip_env:
            return subprocess.run(cmd, **kwargs)

        script = self._resolve_env_script()
        env = self._compose_msvc_env(script, self.env_args)

        # Merge caller-provided env last (caller overrides)
        merged_env = os.environ.copy()
        merged_env.update(env)
        if "env" in kwargs and kwargs["env"]:
            merged_env.update(kwargs["env"])
        kwargs["env"] = merged_env

        return subprocess.run(cmd, **kwargs)

    # -------------------- env building --------------------

    def _compose_msvc_env(self, script_path: str, script_args: str) -> Dict[str, str]:
        """
        Start a transient cmd.exe, call the script to set env, then output `set`.
        Parse and return the environment as a dict.
        """
        # Build as a SINGLE STRING; use shell=True to avoid Python re-escaping quotes.
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        cmdline = f'{comspec} /d /c call "{script_path}" {script_args}'.rstrip() + " && set"

        if self.debug:
            print(f"[MSVCEnvRunner] env build: {cmdline}")

        proc = subprocess.run(
            cmdline,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,  # critical to preserve quotes exactly for cmd.exe
        )

        if proc.returncode != 0:
            raise RuntimeError(
                "Failed to load MSVC environment via script.\n"
                f"Script: {script_path}\nArgs: {script_args}\n"
                f"stderr:\n{proc.stderr}\n"
                "Hint: pass env_script WITHOUT quotes; this runner will quote it."
            )

        env: Dict[str, str] = {}
        for line in proc.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
        return env

    # -------------------- discovery --------------------

    def _resolve_env_script(self) -> str:
        # 0) If user provided a path, normalize & validate
        if self._env_script_raw:
            path = self._normalize_script_path(self._env_script_raw)
            if not Path(path).is_file():
                raise FileNotFoundError(f"MSVC environment script not found: {path}")
            if self.debug:
                print(f"[MSVCEnvRunner] using explicit env_script: {path}")
            return path

        # 1) Active environment hints (common when started inside some VS shells)
        for var in ("VSINSTALLDIR", "VCINSTALLDIR"):
            val = os.environ.get(var)
            if val:
                for cand in self._script_candidates_from_root(Path(val)):
                    if cand.is_file():
                        if self.debug:
                            print(f"[MSVCEnvRunner] found via {var}: {cand}")
                        return str(cand)

        # 2) vswhere.exe (reliable for modern VS)
        vswhere = self._vswhere_path()
        if vswhere and vswhere.exists():
            for ip in self._vswhere_install_paths(vswhere):
                for cand in self._script_candidates_from_root(Path(ip)):
                    if cand.is_file():
                        if self.debug:
                            print(f"[MSVCEnvRunner] found via vswhere: {cand}")
                        return str(cand)

        # 3) Known default roots (VS 2017/2019/2022; all editions)
        for root in self._default_vs_roots():
            for ver in ("2022", "2019", "2017"):
                for edition in ("Community", "Professional", "Enterprise", "BuildTools"):
                    base = root / ver / edition
                    for cand in self._script_candidates_from_root(base):
                        if cand.is_file():
                            if self.debug:
                                print(f"[MSVCEnvRunner] found via default roots: {cand}")
                            return str(cand)

        raise FileNotFoundError(
            "Could not auto-locate a Visual Studio environment script "
            "(checked env vars, vswhere, and default install roots). "
            "Pass env_script=... explicitly."
        )

    def _script_candidates_from_root(self, base: Path) -> List[Path]:
        return [
            base / "Common7" / "Tools" / "VsDevCmd.bat",
            base / "VC" / "Auxiliary" / "Build" / "vcvarsall.bat",
        ]

    def _vswhere_path(self) -> Optional[Path]:
        pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        p = Path(pfx86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
        return p if p.exists() else None

    def _vswhere_install_paths(self, vswhere: Path) -> List[str]:
        try:
            out = subprocess.check_output(
                [
                    str(vswhere),
                    "-products",
                    "*",
                    "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                    "-property",
                    "installationPath",
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            return [line for line in out.splitlines() if line.strip()]
        except Exception:
            return []

    def _default_vs_roots(self) -> List[Path]:
        roots: List[Path] = []
        for var, fallback in (("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                              ("ProgramFiles", r"C:\Program Files")):
            base = Path(os.environ.get(var, fallback)) / "Microsoft Visual Studio"
            if base.exists():
                roots.append(base)
        # De-dup while preserving order
        seen = set()
        uniq: List[Path] = []
        for r in roots:
            if r not in seen:
                seen.add(r)
                uniq.append(r)
        return uniq

    # -------------------- quoting & platform helpers --------------------

    def _normalize_script_path(self, raw: str) -> str:
        s = raw.strip()
        # Strip outer quotes if user supplied them
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1].strip()
        # Strip accidental backslash-escaped outer quotes: \"C:\...\"
        if s.startswith(r'\"') and s.endswith(r'\"'):
            s = s[2:-2].strip()
        return str(Path(s))

    def _is_windows(self) -> bool:
        return os.name == "nt" or sys.platform.startswith("win")

    def _list2cmd(self, cmd: Sequence[str]) -> str:
        return subprocess.list2cmdline(list(cmd))


if __name__ == "__main__":
    # Simple manual test helpers (run this file directly on Windows):
    runner = MSVCEnvRunner(env_args="x64", debug=True)
    try:
        # Expect to see cl.exe path(s)
        res = runner.run(["where", "cl"])
        print("where cl ->", res.stdout or res.stderr)
    except Exception as e:
        print("Auto-discovery failed:", e)

    # Uncomment to test an explicit script path:
    # runner2 = MSVCEnvRunner(
    #     env_script=r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
    #     env_args="x64",
    #     debug=True
    # )
    # print(runner2.run(["where", "cl"]).stdout)
