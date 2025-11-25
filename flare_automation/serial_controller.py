"""Serial device discovery and control for illumination hardware."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable, Optional

try:  # pragma: no cover - optional dependency
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover
    serial = None  # type: ignore
    list_ports = None  # type: ignore


@dataclass
class SerialDevice:
    port: str
    description: str | None = None


class SerialController:
    """Utility class for LED/illumination serial communications."""

    # Common USB VID/PID pairs for Arduino Mega 2560 boards, including
    # official (2341/2A03) and CH340-based clones (1A86:7523).
    MEGA_2560_IDS = {
        (0x2341, 0x0042),
        (0x2341, 0x0010),
        (0x2A03, 0x0042),
        (0x2A03, 0x0010),
        (0x1A86, 0x7523),
    }

    def __init__(self, *, baudrate: int, terminator: str = "\r") -> None:
        self._baudrate = baudrate
        self._terminator = terminator
        if serial is None:
            raise RuntimeError(
                "pyserial is required for serial communication. Install with 'pip install pyserial'."
            )

    @staticmethod
    def discover(
        *, vendor_id: str | None = None, product_id: str | None = None
    ) -> Iterable[SerialDevice]:
        if list_ports is None:
            raise RuntimeError("pyserial is required for serial discovery")

        for port in list_ports.comports():
            if vendor_id:
                if port.vid is None or f"{port.vid:04x}" != f"{int(vendor_id, 16):04x}":
                    continue
            if product_id:
                if port.pid is None or f"{port.pid:04x}" != f"{int(product_id, 16):04x}":
                    continue
            yield SerialDevice(port=port.device, description=port.description)

    @classmethod
    def discover_mega_2560(cls) -> Iterable[SerialDevice]:
        """Yield Arduino Mega 2560 devices detected on the system."""

        if list_ports is None:
            raise RuntimeError("pyserial is required for serial discovery")

        for port in list_ports.comports():
            if port.vid is None or port.pid is None:
                continue
            if (port.vid, port.pid) in cls.MEGA_2560_IDS:
                yield SerialDevice(port=port.device, description=port.description)

    def open(self, port: str):  # pragma: no cover - hardware interaction
        connection = serial.Serial(port, baudrate=self._baudrate, timeout=2)
        connection.write_timeout = 2
        return connection

    def send_command(
        self,
        connection,
        command: str,
        *,
        settle_time_s: float = 0.0,
    ) -> str:  # pragma: no cover - hardware interaction
        connection.reset_input_buffer()
        connection.reset_output_buffer()
        payload = (command + self._terminator).encode("utf-8")
        connection.write(payload)
        connection.flush()
        time.sleep(settle_time_s)
        response = connection.read_all().decode("utf-8", errors="replace").strip()
        return response
