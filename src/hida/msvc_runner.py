import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence, Union

Cmd = Union[str, Sequence[str]]

class MSVCEnvRunner:
    """
    Run a command with optional MSVC environment setup on Windows.

    Features:
    - If `skip_env` is True, just runs the command (assumes you're already in a dev console).
    - If `env_script` is provided, it will `call` that script first (e.g. setenv.cmd / VsDevCmd.bat).
    - If `env_script` is not provided, it will try 'setenv.cmd' from PATH when needed.
    - On non-Windows platforms, behaves like plain subprocess.run.

    Defaults:
    - text=True, stdout=PIPE, stderr=PIPE (matching your original snippet).
    """

    def __init__(
        self,
        skip_env: bool = False,
        env_script: Optional[Union[str, Path]] = None,
        env_args: Optional[str] = None,
    ) -> None:
        """
        :param skip_env: If True, don't run any setup script (user already in MSVC dev console).
        :param env_script: Full path (or name on PATH) to the setup batch (e.g. 'setenv.cmd' or 'VsDevCmd.bat').
        :param env_args: Optional args for the setup script (e.g. 'amd64', 'x64', etc.).
        """
        self.skip_env = bool(skip_env)
        self.env_script = str(env_script) if env_script else None
        self.env_args = env_args or ""

    def _is_windows(self) -> bool:
        return os.name == "nt" or sys.platform.startswith("win")

    def _list2cmd(self, cmd: Sequence[str]) -> str:
        # Windows-safe quoting for a list of args
        return subprocess.list2cmdline(list(cmd))

    def run(self, cmd: Cmd, **kwargs) -> subprocess.CompletedProcess:
        """
        Run the command, capturing text output by default.

        You can pass any subprocess.run kwargs to override defaults (e.g., cwd, env, timeout).
        """
        # Default to your original capturing behavior unless user overrides:
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
        kwargs.setdefault("text", True)

        # Non-Windows or user says "I'm already in a dev console": just run it.
        if not self._is_windows() or self.skip_env:
            return subprocess.run(cmd, **kwargs)

        # Windows + not skipping. Prepare to call the setup script first.
        script = self.env_script or "setenv.cmd"

        # If a path-like script was provided, confirm it exists; otherwise allow PATH resolution.
        if os.path.sep in script or script.endswith(".cmd") or script.endswith(".bat"):
            if not Path(script).exists():
                raise FileNotFoundError(f"MSVC environment script not found: {script}")
        else:
            # Let PATH resolve it; fail early if not found.
            if shutil.which(script) is None:
                raise FileNotFoundError(
                    f"'{script}' not found on PATH. Provide full path via env_script."
                )

        # Build the command line to:
        #   call "<script>" <env_args> && <your command>
        if isinstance(cmd, (list, tuple)):
            user_cmd = self._list2cmd(cmd)
        else:
            user_cmd = cmd

        env_part = f'call "{script}" {self.env_args}'.rstrip()
        composite = f'{env_part} && {user_cmd}'

        # Use cmd.exe to run the composite (so "call" and "&&" work).
        # Note: we do NOT force shell=True; instead, we explicitly run cmd.exe.
        return subprocess.run(["cmd.exe", "/S", "/C", composite], **kwargs)
