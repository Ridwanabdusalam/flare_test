"""Photo-response analysis utilities for flare capture runs.

This module processes RAW16 captures for a set of ROIs and computes per-ROI
photo-response statistics. The workflow closely mirrors the legacy MATLAB
scripts used during development by producing ROI means, applying saturation
filtering, performing linear regression, and generating log--log diagnostic
plots for each illumination/exposure group.
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from .pipeline import CaptureRecord
from .roi import ROI, load_raw16_image

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhotoResponseMeasurement:
    """Single ROI measurement for a captured frame."""

    illumination: str
    sequence: str
    exposure_us: int
    frame_index: int
    roi_name: str
    mean_dn: float
    normalised_dn: float
    saturated: bool
    nd_factor: float
    source_file: str


@dataclass(frozen=True)
class RoiFitResult:
    """Linear-fit coefficients derived from unsaturated ROI measurements."""

    roi_name: str
    slope: float | None
    intercept: float | None
    used_points: int
    total_points: int
    saturated_points: int


@dataclass
class PhotoResponseResult:
    """Container returned after processing a capture group."""

    measurements: list[PhotoResponseMeasurement] = field(default_factory=list)
    fits: list[RoiFitResult] = field(default_factory=list)
    saturation_threshold: float = 600.0

    def to_json(self) -> dict[str, object]:
        return {
            "saturation_threshold": self.saturation_threshold,
            "measurements": [asdict(entry) for entry in self.measurements],
            "fits": [asdict(entry) for entry in self.fits],
        }


def _nd_normalisation_factor(metadata: Mapping[str, object] | None) -> float:
    """Derive an ND normalisation factor from capture metadata.

    The metadata produced by the capture pipeline can describe ND filters in
    a handful of ways. This helper attempts to interpret common conventions:

    * ``nd_factor`` or ``nd_attenuation`` describe the multiplicative
      attenuation applied by the filter (e.g. 0.1 == 10 % transmission).
    * ``nd_density`` or ``density`` inside an ``nd_filter`` block report the
      optical density. The normalisation factor is calculated as ``10 ** (-D)``.
    * ``factor`` inside an ``nd_filter`` block maps directly to the attenuation
      factor.

    When no metadata is present the function falls back to ``1.0`` which
    effectively disables normalisation.
    """

    if not metadata:
        return 1.0

    direct_keys = ("nd_factor", "nd_attenuation", "attenuation", "transmission")
    for key in direct_keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            factor = float(value)
        except (TypeError, ValueError):
            logger.debug("Unable to coerce ND factor %r for key %s", value, key)
            continue
        if factor <= 0:
            logger.debug("Ignoring non-positive ND factor %.3f from key %s", factor, key)
            continue
        return factor

    nd_filter = metadata.get("nd_filter")
    if isinstance(nd_filter, Mapping):
        # First look for an explicit factor.
        for key in ("factor", "nd_factor", "attenuation", "transmission"):
            value = nd_filter.get(key)
            if value is None:
                continue
            try:
                factor = float(value)
            except (TypeError, ValueError):
                logger.debug("Unable to interpret ND factor %r within nd_filter", value)
                continue
            if factor > 0:
                return factor
        # Fall back to optical density if available.
        for key in ("nd_density", "density", "optical_density"):
            value = nd_filter.get(key)
            if value is None:
                continue
            try:
                density = float(value)
            except (TypeError, ValueError):
                logger.debug("Unable to interpret ND density %r", value)
                continue
            factor = 10 ** (-density)
            if factor > 0:
                return factor

    density_value = metadata.get("nd_density")
    if density_value is not None:
        try:
            density = float(density_value)
        except (TypeError, ValueError):
            logger.debug("Unable to interpret ND density %r", density_value)
        else:
            factor = 10 ** (-density)
            if factor > 0:
                return factor

    return 1.0


def _roi_mean(frame: np.ndarray, roi: ROI) -> float:
    x0, y0, width, height = roi.bounds()
    x1 = x0 + width
    y1 = y0 + height
    if (
        x0 < 0
        or y0 < 0
        or x1 > frame.shape[1]
        or y1 > frame.shape[0]
    ):
        raise ValueError(
            f"ROI {roi.name} falls outside the frame bounds {frame.shape[::-1]}"
        )
    region = frame[y0:y1, x0:x1]
    return float(region.mean())


def _list_raw16_frames(record: CaptureRecord) -> list[Path]:
    """Return RAW16 frame paths for *record* sorted lexicographically."""

    if not record.raw16_dir.exists():
        logger.warning("RAW16 directory missing for %s", record.raw16_dir)
        return []
    candidates = sorted(
        path
        for path in record.raw16_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".raw", ".raw16", ".bin"}
    )
    return candidates


def _measure_capture(
    record: CaptureRecord,
    rois: Sequence[ROI],
    *,
    saturation_threshold: float,
) -> list[PhotoResponseMeasurement]:
    """Compute ROI means for every frame associated with *record*."""

    width = record.run.config.raw_width
    height = record.run.config.raw_height
    stride = record.run.config.raw_stride

    nd_factor = _nd_normalisation_factor(record.capture_metadata)
    if nd_factor <= 0:
        logger.debug(
            "Normalisation factor %.3f invalid for %s; defaulting to 1.0",
            nd_factor,
            record.capture_dir,
        )
        nd_factor = 1.0

    frame_paths = _list_raw16_frames(record)
    measurements: list[PhotoResponseMeasurement] = []
    for frame_index, frame_path in enumerate(frame_paths, start=1):
        try:
            frame = load_raw16_image(frame_path, width=width, height=height, stride=stride)
        except Exception as exc:  # pragma: no cover - file handling errors
            logger.error("Failed to load RAW16 frame %s: %s", frame_path, exc)
            continue
        for roi in rois:
            try:
                mean_dn = _roi_mean(frame, roi)
            except Exception as exc:
                logger.error("Failed to compute mean for ROI %s: %s", roi.name, exc)
                continue
            saturated = mean_dn > saturation_threshold
            normalised_dn = mean_dn / nd_factor
            measurements.append(
                PhotoResponseMeasurement(
                    illumination=record.illumination.name,
                    sequence=record.sequence.label,
                    exposure_us=record.exposure_us,
                    frame_index=frame_index,
                    roi_name=roi.name,
                    mean_dn=mean_dn,
                    normalised_dn=normalised_dn,
                    saturated=saturated,
                    nd_factor=nd_factor,
                    source_file=str(frame_path),
                )
            )
    if not frame_paths:
        logger.warning(
            "No RAW16 frames discovered for %s/%s/%sus",
            record.illumination.name,
            record.sequence.label,
            record.exposure_us,
        )
    return measurements


def _linear_fit(exposures: np.ndarray, values: np.ndarray) -> tuple[float, float]:
    """Return ``(slope, intercept)`` for a best-fit line."""

    A = np.vstack([exposures, np.ones_like(exposures)]).T
    slope, intercept = np.linalg.lstsq(A, values, rcond=None)[0]
    return float(slope), float(intercept)


def _generate_diagnostic_plot(
    output_dir: Path,
    roi_name: str,
    exposures: np.ndarray,
    measured: np.ndarray,
    fitted: np.ndarray | None,
    *,
    illumination: str,
    sequence: str,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover - optional dependency
        logger.warning("matplotlib not available; skipping diagnostic plot for %s", roi_name)
        return

    if exposures.size == 0 or measured.size == 0:
        logger.debug("No data available to plot for ROI %s", roi_name)
        return

    positive_mask = (exposures > 0) & (measured > 0)
    if not np.any(positive_mask):
        logger.debug("ROI %s measurements not positive; skipping log-log plot", roi_name)
        return

    exposures = exposures[positive_mask]
    measured = measured[positive_mask]
    fitted_plot = None
    fit_exposures = exposures
    if fitted is not None:
        fitted = fitted[positive_mask]
        fit_mask = fitted > 0
        if np.any(fit_mask):
            fitted_plot = fitted[fit_mask]
            fit_exposures = exposures[fit_mask]
        else:
            fitted_plot = None

    fig, ax = plt.subplots()
    ax.loglog(exposures, measured, "o", label="Measured")
    if fitted_plot is not None:
        ax.loglog(fit_exposures, fitted_plot, "-", label="Linear fit")
    ax.set_xlabel("Exposure (µs)")
    ax.set_ylabel("Mean DN (normalised)")
    ax.set_title(f"Photo response — {illumination} / {sequence} / {roi_name}")
    ax.grid(True, which="both", ls="--", alpha=0.5)
    ax.legend()
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{roi_name}_photo_response.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved diagnostic plot for ROI %s to %s", roi_name, path)


def analyze_photo_response(
    records: Sequence[CaptureRecord],
    rois: Sequence[ROI],
    *,
    saturation_threshold: float = 600.0,
    output_dir: Path | None = None,
) -> PhotoResponseResult:
    """Compute photo-response metrics for *records*.

    Parameters
    ----------
    records:
        Collection of :class:`~flare_automation.analysis.pipeline.CaptureRecord`
        instances that belong to the same illumination/sequence sweep.
    rois:
        Rectangular ROIs for which mean DN measurements should be calculated.
    saturation_threshold:
        DN threshold beyond which measurements are discarded from fitting.
    output_dir:
        Directory where CSV/JSON artifacts and diagnostic plots will be written.
        Defaults to the parent directory of the first capture's RAW16 data.
    """

    if not records:
        raise ValueError("At least one capture record is required")

    base_dir = output_dir
    if base_dir is None:
        base_dir = records[0].capture_dir.parent
    base_dir.mkdir(parents=True, exist_ok=True)

    all_measurements: list[PhotoResponseMeasurement] = []
    for record in records:
        measurements = _measure_capture(record, rois, saturation_threshold=saturation_threshold)
        all_measurements.extend(measurements)

    result = PhotoResponseResult(measurements=all_measurements, saturation_threshold=saturation_threshold)

    # Persist raw measurements to CSV for downstream processing.
    csv_path = base_dir / "photo_response_measurements.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "illumination",
                "sequence",
                "exposure_us",
                "frame_index",
                "roi_name",
                "mean_dn",
                "normalised_dn",
                "saturated",
                "nd_factor",
                "source_file",
            ],
        )
        writer.writeheader()
        for entry in result.measurements:
            writer.writerow(asdict(entry))
    logger.info("Wrote ROI measurements to %s", csv_path)

    # Group measurements per ROI for fitting.
    by_roi: dict[str, list[PhotoResponseMeasurement]] = {}
    for entry in result.measurements:
        by_roi.setdefault(entry.roi_name, []).append(entry)

    illumination = records[0].illumination.name
    sequence = records[0].sequence.label

    fits: list[RoiFitResult] = []
    for roi_name, entries in sorted(by_roi.items()):
        total_points = len(entries)
        saturated_points = sum(1 for item in entries if item.saturated)

        # Aggregate unsaturated means per exposure (averaging across frames).
        exposure_map: dict[int, list[float]] = {}
        for item in entries:
            if item.saturated:
                continue
            exposure_map.setdefault(item.exposure_us, []).append(item.normalised_dn)

        if not exposure_map:
            fits.append(
                RoiFitResult(
                    roi_name=roi_name,
                    slope=None,
                    intercept=None,
                    used_points=0,
                    total_points=total_points,
                    saturated_points=saturated_points,
                )
            )
            continue

        exposures = np.array(sorted(exposure_map), dtype=float)
        averaged = np.array([np.mean(exposure_map[exp]) for exp in exposures], dtype=float)

        slope: float | None
        intercept: float | None
        fitted: np.ndarray | None
        if exposures.size >= 2:
            slope, intercept = _linear_fit(exposures, averaged)
            fitted = slope * exposures + intercept
        else:
            slope = intercept = None
            fitted = None

        fits.append(
            RoiFitResult(
                roi_name=roi_name,
                slope=slope,
                intercept=intercept,
                used_points=int(exposures.size),
                total_points=total_points,
                saturated_points=saturated_points,
            )
        )

        _generate_diagnostic_plot(
            base_dir,
            roi_name,
            exposures,
            averaged,
            fitted,
            illumination=illumination,
            sequence=sequence,
        )

    result.fits = fits

    json_path = base_dir / "photo_response_summary.json"
    with json_path.open("w", encoding="utf-8") as handle:
        payload = result.to_json()
        payload.update({"illumination": illumination, "sequence": sequence})
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    logger.info("Wrote photo-response summary to %s", json_path)

    return result
