"""Analysis data pipeline for flare capture runs."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

from ..config import CaptureConfig, ExposureSequence, IlluminationConfig
from .roi import InteractiveROISelector

logger = logging.getLogger(__name__)


class RunDataError(RuntimeError):
    """Raised when a capture run directory is missing expected metadata."""


@dataclass(frozen=True)
class RunMetadata:
    """Top-level metadata for a capture run."""

    root: Path
    config: CaptureConfig


@dataclass(frozen=True)
class CaptureRecord:
    """Fully-resolved metadata for a single exposure capture."""

    run: RunMetadata
    illumination: IlluminationConfig
    sequence: ExposureSequence
    exposure_us: int
    capture_dir: Path
    captured_files: Sequence[Path]
    converted_files: Sequence[Path]
    raw10_dir: Path
    raw16_dir: Path
    capture_metadata: dict[str, Any]


StageResult = Any
RoiStage = Callable[[CaptureRecord], StageResult]
PhotoResponseStage = Callable[[CaptureRecord, StageResult], StageResult]
VerificationStage = Callable[[CaptureRecord, StageResult, StageResult], None]


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise RunDataError(f"Expected metadata file missing: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalise_path(value: Any) -> str:
    """Convert stored metadata path representations back to filesystem paths."""

    if isinstance(value, (str, Path)):
        return str(Path(value))
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        try:
            return str(Path(*value))
        except TypeError:
            pass
    raise RunDataError(f"Cannot interpret metadata path value: {value!r}")


def _load_capture_config(path: Path) -> CaptureConfig:
    raw = _load_json(path)
    if not isinstance(raw, dict):
        raise RunDataError("config.json must contain an object")
    payload = raw.copy()
    for key in ("output_root", "raw_converter"):
        if key in payload:
            payload[key] = _normalise_path(payload[key])
    return CaptureConfig.from_mapping(payload)


def _load_sequence(path: Path) -> ExposureSequence:
    raw = _load_json(path)
    if not isinstance(raw, dict):
        raise RunDataError("sequence.json must contain an object")
    return ExposureSequence(**raw)


def _load_capture_metadata(path: Path) -> tuple[IlluminationConfig, dict[str, Any]]:
    raw = _load_json(path)
    if not isinstance(raw, dict):
        raise RunDataError("capture.json must contain an object")
    illumination_data = raw.get("illumination")
    if not isinstance(illumination_data, dict):
        raise RunDataError("capture.json missing 'illumination' block")
    illumination = IlluminationConfig(**illumination_data)
    return illumination, raw


def _coerce_file_list(entries: Iterable[Any], base_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for entry in entries:
        path = Path(entry)
        if not path.is_absolute():
            path = base_dir / path
        paths.append(path)
    return paths


def iter_capture_records(run_root: Path) -> Iterator[CaptureRecord]:
    """Yield capture metadata for each exposure within *run_root*."""

    config_path = run_root / "config.json"
    config = _load_capture_config(config_path)
    run_meta = RunMetadata(root=run_root, config=config)

    for illumination_dir in sorted(p for p in run_root.iterdir() if p.is_dir()):
        sequence_path = illumination_dir / "sequence.json"
        if not sequence_path.exists():
            logger.debug("Skipping %s (missing sequence.json)", illumination_dir)
            continue
        sequence = _load_sequence(sequence_path)
        for capture_dir in sorted(p for p in illumination_dir.iterdir() if p.is_dir()):
            capture_path = capture_dir / "capture.json"
            if not capture_path.exists():
                logger.debug("Skipping %s (missing capture.json)", capture_dir)
                continue
            illumination, capture_metadata = _load_capture_metadata(capture_path)
            exposure_us = capture_metadata.get("exposure_us")
            if not isinstance(exposure_us, int):
                raise RunDataError(f"capture.json missing integer 'exposure_us': {capture_path}")
            captured_files = _coerce_file_list(
                capture_metadata.get("captured", []), capture_dir
            )
            converted_files = _coerce_file_list(
                capture_metadata.get("converted", []), capture_dir
            )
            record = CaptureRecord(
                run=run_meta,
                illumination=illumination,
                sequence=sequence,
                exposure_us=exposure_us,
                capture_dir=capture_dir,
                captured_files=captured_files,
                converted_files=converted_files,
                raw10_dir=capture_dir / "raw10",
                raw16_dir=capture_dir / "raw16",
                capture_metadata=capture_metadata,
            )
            logger.debug(
                "Loaded capture: run=%s, illumination=%s, sequence=%s, exposure=%sus",
                run_root.name,
                illumination.name,
                sequence.label,
                exposure_us,
            )
            yield record


def _default_roi_stage() -> RoiStage:
    return InteractiveROISelector()


def _noop_photo_response(record: CaptureRecord, roi_result: StageResult) -> StageResult:
    logger.info(
        "Photo-response placeholder executed for %s/%s/%sus",
        record.illumination.name,
        record.sequence.label,
        record.exposure_us,
    )
    return {}


def _noop_roi_verification(
    record: CaptureRecord, roi_result: StageResult, photo_response_result: StageResult
) -> None:
    logger.info(
        "ROI verification placeholder executed for %s/%s/%sus",
        record.illumination.name,
        record.sequence.label,
        record.exposure_us,
    )


@dataclass
class AnalysisConfig:
    """Configuration for orchestrating analysis stages."""

    roi_definition: RoiStage = field(default_factory=_default_roi_stage)
    photo_response: PhotoResponseStage = field(default=_noop_photo_response)
    roi_verification: VerificationStage = field(default=_noop_roi_verification)


def run_analysis(run_root: Path, config: AnalysisConfig) -> None:
    """Run the configured analysis stages for every capture in *run_root*."""

    logger.info("Starting analysis for %s", run_root)
    for record in iter_capture_records(run_root):
        roi_result = config.roi_definition(record)
        photo_response_result = config.photo_response(record, roi_result)
        config.roi_verification(record, roi_result, photo_response_result)
    logger.info("Analysis complete for %s", run_root)
