"""Utility helpers for flare automation."""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


class CommandError(RuntimeError):
    """Raised when an external command fails."""

    def __init__(self, cmd: Sequence[str], returncode: int, stdout: str, stderr: str):
        super().__init__(
            f"Command {' '.join(cmd)} failed with exit code {returncode}: {stderr.strip() or stdout.strip()}"
        )
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_command(cmd: Sequence[str], *, timeout: float | None = None) -> str:
    """Run a command and return stdout.

    Args:
        cmd: The command and arguments to execute.
        timeout: Optional timeout in seconds.
    """

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise CommandError(cmd, proc.returncode, proc.stdout, proc.stderr)
    return proc.stdout.strip()


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def dataclass_to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return {key: dataclass_to_dict(value) for key, value in asdict(obj).items()}
    if isinstance(obj, Mapping):
        return {key: dataclass_to_dict(value) for key, value in obj.items()}
    if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
        return [dataclass_to_dict(value) for value in obj]
    return obj


def write_metadata(path: Path, data: Any) -> None:
    path.write_text(json.dumps(dataclass_to_dict(data), indent=2), encoding="utf-8")
