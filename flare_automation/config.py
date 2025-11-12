"""Configuration models and loaders for flare capture automation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence
import json

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - yaml optional at runtime
    yaml = None  # type: ignore

@dataclass
class ExposureSequence:
    """Represents a group of exposure times for a capture sweep."""

    label: str
    exposure_us: Sequence[int]
    iso: int = 1600
    frame_count: int = 1

    def __post_init__(self) -> None:
        if not self.exposure_us:
            raise ValueError("Exposure sequence cannot be empty")
        if any(value <= 0 for value in self.exposure_us):
            raise ValueError("Exposure times must be positive")


@dataclass
class IlluminationConfig:
    """Settings for a single illumination source."""

    name: str
    serial_command: str
    pwm_percent: Optional[float] = None
    settle_time_s: float = 1.0


@dataclass
class CaptureConfig:
    """Top level configuration for an experiment run."""

    output_root: Path
    scene_name: str
    serial_baud: int = 19200
    serial_terminator: str = "\r"
    serial_vendor_id: Optional[str] = None
    serial_product_id: Optional[str] = None
    preferred_com_port: Optional[str] = None
    adb_serial: Optional[str] = None
    adb_timeout_s: float = 10.0
    camera_id: int = 0
    resolution: str = "4032x3024"
    remote_raw_dir: str = "/data/vendor/camera"
    raw_converter: Path = Path("unpack_mipi_raw10.py")
    raw_width: int = 4032
    raw_height: int = 3024
    raw_stride: int = 5040
    illumination: Sequence[IlluminationConfig] = field(default_factory=list)
    exposure_sequences: Sequence[ExposureSequence] = field(default_factory=list)

    def validate(self) -> None:
        if not self.illumination:
            raise ValueError("At least one illumination profile must be defined")
        if not self.exposure_sequences:
            raise ValueError("At least one exposure sequence must be defined")

    @classmethod
    def from_mapping(cls, data: dict) -> "CaptureConfig":
        illumination = [IlluminationConfig(**entry) for entry in data.get("illumination", [])]
        exposures = [ExposureSequence(**entry) for entry in data.get("exposure_sequences", [])]
        config = cls(
            output_root=Path(data["output_root"]),
            scene_name=data["scene_name"],
            serial_baud=data.get("serial_baud", 19200),
            serial_terminator=data.get("serial_terminator", "\r"),
            serial_vendor_id=data.get("serial_vendor_id"),
            serial_product_id=data.get("serial_product_id"),
            preferred_com_port=data.get("preferred_com_port"),
            adb_serial=data.get("adb_serial"),
            adb_timeout_s=data.get("adb_timeout_s", 10.0),
            camera_id=data.get("camera_id", 0),
            resolution=data.get("resolution", "4032x3024"),
            remote_raw_dir=data.get("remote_raw_dir", "/data/vendor/camera"),
            raw_converter=Path(data.get("raw_converter", "unpack_mipi_raw10.py")),
            raw_width=data.get("raw_width", 4032),
            raw_height=data.get("raw_height", 3024),
            raw_stride=data.get("raw_stride", 5040),
            illumination=illumination,
            exposure_sequences=exposures,
        )
        config.validate()
        return config

    @classmethod
    def load(cls, path: Path) -> "CaptureConfig":
        """Load a configuration file from JSON or YAML."""

        with open(path, "r", encoding="utf-8") as handle:
            if path.suffix.lower() in {".yaml", ".yml"}:
                if yaml is None:
                    raise RuntimeError("PyYAML is required to load YAML configuration files")
                data = yaml.safe_load(handle)
            else:
                data = json.load(handle)

        if not isinstance(data, dict):
            raise ValueError("Configuration file must define an object at the top level")
        return cls.from_mapping(data)

    def iter_sequences(self) -> Iterable[tuple[IlluminationConfig, ExposureSequence]]:
        for illumination in self.illumination:
            for sequence in self.exposure_sequences:
                yield illumination, sequence
