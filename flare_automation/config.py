"""Configuration models and loaders for flare capture automation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence
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
class SceneAnalysisConfig:
    """Maps an illumination profile to a measured scene illumination value."""

    illumination: str
    illumination_lux: float


@dataclass
class ROIAnalysisConfig:
    """Defines a region-of-interest used during post processing."""

    name: str
    row: int
    col: int
    half_width: int = 8
    role: str = "reflectance"
    reflectance: Optional[float] = None

    def __post_init__(self) -> None:
        if self.half_width <= 0:
            raise ValueError("ROI half_width must be positive")
        if self.row < 0 or self.col < 0:
            raise ValueError("ROI coordinates must be non-negative")
        if self.role not in {"reflectance", "direct_beam", "black_hole"}:
            raise ValueError(
                "ROI role must be one of 'reflectance', 'direct_beam', or 'black_hole'"
            )
        if self.role == "reflectance" and self.reflectance is None:
            raise ValueError("Reflectance ROIs must provide a reflectance value")


@dataclass
class AnalysisConfig:
    """Parameters controlling post-capture analysis."""

    enabled: bool = False
    sequence_label: Optional[str] = None
    scenes: Sequence[SceneAnalysisConfig] = field(default_factory=list)
    rois: Sequence[ROIAnalysisConfig] = field(default_factory=list)
    nd_filter_ratio: float = 1.0
    saturation_dn: float = 600.0
    preview_illumination: Optional[str] = None
    preview_exposure_us: Optional[int] = None

    def validate(self, capture_config: "CaptureConfig") -> None:
        if not self.enabled:
            return
        if not self.sequence_label:
            raise ValueError("Analysis requires a 'sequence_label' to be specified")
        if not self.scenes:
            raise ValueError("Analysis requires at least one scene definition")
        if not self.rois:
            raise ValueError("Analysis requires at least one ROI definition")
        illumination_names = {item.name for item in capture_config.illumination}
        for scene in self.scenes:
            if scene.illumination not in illumination_names:
                raise ValueError(
                    f"Analysis scene references unknown illumination '{scene.illumination}'"
                )
        if not any(seq.label == self.sequence_label for seq in capture_config.exposure_sequences):
            raise ValueError(
                f"Analysis sequence_label '{self.sequence_label}' not found in exposure sequences"
            )
        names = {roi.name for roi in self.rois}
        if len(names) != len(self.rois):
            raise ValueError("ROI names must be unique")
        if not any(roi.role == "direct_beam" for roi in self.rois):
            raise ValueError("Analysis requires exactly one ROI with role 'direct_beam'")
        if sum(1 for roi in self.rois if roi.role == "direct_beam") != 1:
            raise ValueError("Analysis requires exactly one ROI with role 'direct_beam'")
        if sum(1 for roi in self.rois if roi.role == "black_hole") > 1:
            raise ValueError("Analysis can have at most one ROI with role 'black_hole'")

    def direct_beam_index(self) -> int:
        for idx, roi in enumerate(self.rois):
            if roi.role == "direct_beam":
                return idx
        raise ValueError("No ROI with role 'direct_beam' defined")

    def black_hole_index(self) -> Optional[int]:
        for idx, roi in enumerate(self.rois):
            if roi.role == "black_hole":
                return idx
        return None

    def reflectance_indices(self) -> list[int]:
        return [idx for idx, roi in enumerate(self.rois) if roi.role == "reflectance"]

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "AnalysisConfig":
        scenes = [SceneAnalysisConfig(**entry) for entry in data.get("scenes", [])]
        rois = [ROIAnalysisConfig(**entry) for entry in data.get("rois", [])]
        preview = data.get("preview", {})
        if not isinstance(preview, Mapping):
            preview = {}
        return cls(
            enabled=data.get("enabled", True),
            sequence_label=data.get("sequence_label"),
            scenes=scenes,
            rois=rois,
            nd_filter_ratio=float(data.get("nd_filter_ratio", 1.0)),
            saturation_dn=float(data.get("saturation_dn", 600.0)),
            preview_illumination=preview.get("illumination"),
            preview_exposure_us=preview.get("exposure_us"),
        )


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
    analysis: Optional[AnalysisConfig] = None

    def validate(self) -> None:
        if not self.illumination:
            raise ValueError("At least one illumination profile must be defined")
        if not self.exposure_sequences:
            raise ValueError("At least one exposure sequence must be defined")
        if self.analysis is not None:
            self.analysis.validate(self)

    @classmethod
    def from_mapping(cls, data: dict) -> "CaptureConfig":
        illumination = [IlluminationConfig(**entry) for entry in data.get("illumination", [])]
        exposures = [ExposureSequence(**entry) for entry in data.get("exposure_sequences", [])]
        analysis_cfg = None
        if "analysis" in data and data["analysis"] is not None:
            if not isinstance(data["analysis"], Mapping):
                raise ValueError("Analysis configuration must be a mapping")
            analysis_cfg = AnalysisConfig.from_mapping(data["analysis"])
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
            analysis=analysis_cfg,
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
