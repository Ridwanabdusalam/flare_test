"""ADB helpers for managing Android capture devices."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .utils import run_command


@dataclass
class AdbDevice:
    serial: str
    description: str | None = None


class AdbController:
    def __init__(self, *, serial: str | None = None, timeout_s: float = 10.0) -> None:
        self._serial = serial
        self._timeout_s = timeout_s

    def _base_cmd(self) -> list[str]:
        cmd = ["adb"]
        if self._serial:
            cmd.extend(["-s", self._serial])
        return cmd

    def run(self, *args: str) -> str:
        cmd = self._base_cmd() + list(args)
        return run_command(cmd, timeout=self._timeout_s)

    def root(self) -> None:
        self.run("root")

    def remount(self) -> None:
        self.run("remount")

    def stop_service(self, service_name: str) -> None:
        self.run("shell", "setprop", "ctl.stop", service_name)

    def clear_remote_patterns(self, remote_dir: str, patterns: Iterable[str]) -> None:
        for pattern in patterns:
            self.run("shell", "rm", "-f", f"{remote_dir}/{pattern}")

    def capture_raw(
        self,
        *,
        camera_id: int,
        resolution: str,
        exposure_us: int,
        iso: int,
        frame_count: int = 1,
    ) -> None:
        for _ in range(frame_count):
            self.run(
                "shell",
                "camcapture",
                "-c",
                str(camera_id),
                "-d",
                resolution,
                "-e",
                f"{exposure_us},{iso}",
                "-r",
            )

    def pull(self, remote_dir: str, local_path: Path) -> None:
        cmd = self._base_cmd() + ["pull", f"{remote_dir}/.", str(local_path)]
        run_command(cmd, timeout=self._timeout_s)

    @staticmethod
    def list_devices() -> Iterable[AdbDevice]:
        output = run_command(["adb", "devices", "-l"])
        lines = [line.strip() for line in output.splitlines()[1:] if line.strip()]
        for line in lines:
            if "device" not in line:
                continue
            parts = line.split()
            serial = parts[0]
            desc = " ".join(parts[2:]) if len(parts) > 2 else None
            yield AdbDevice(serial=serial, description=desc)
