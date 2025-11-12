"""ROI selection and persistence helpers for the analysis pipeline."""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ROI:
    """Represents a rectangular region of interest."""

    name: str
    center: tuple[int, int]
    size: tuple[int, int]

    def __post_init__(self) -> None:
        if self.size[0] <= 0 or self.size[1] <= 0:
            raise ValueError("ROI dimensions must be positive")

    def to_mapping(self) -> dict[str, object]:
        """Serialise the ROI to a JSON-friendly mapping."""

        return {
            "name": self.name,
            "center": {"x": self.center[0], "y": self.center[1]},
            "size": {"width": self.size[0], "height": self.size[1]},
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "ROI":
        """Construct an :class:`ROI` from a mapping."""

        if "name" not in data:
            raise ValueError("ROI mapping missing 'name'")
        name = str(data.get("name"))
        center_data = data.get("center", {})
        size_data = data.get("size", {})
        if not isinstance(center_data, Mapping) or not isinstance(size_data, Mapping):
            raise ValueError("ROI mapping must include 'center' and 'size' objects")
        try:
            center = (int(center_data["x"]), int(center_data["y"]))
            size = (int(size_data["width"]), int(size_data["height"]))
        except KeyError as exc:  # pragma: no cover - defensive programming
            raise ValueError("ROI mapping missing coordinate keys") from exc
        return cls(name=name, center=center, size=size)

    def bounds(self) -> tuple[int, int, int, int]:
        """Return the top-left coordinate and size of the ROI rectangle."""

        width, height = self.size
        x, y = self.center
        origin_x = x - width // 2
        origin_y = y - height // 2
        return origin_x, origin_y, width, height


def roi_file_path(run_root: Path, filename: str = "rois.json") -> Path:
    """Return the canonical path for ROI definitions within *run_root*."""

    return run_root / filename


def load_roi_set(run_root: Path, filename: str = "rois.json") -> list[ROI]:
    """Load persisted ROI definitions for *run_root* if available."""

    path = roi_file_path(run_root, filename)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Sequence):
        raise ValueError("ROI file must contain an array of ROI definitions")
    rois: list[ROI] = []
    for entry in payload:
        if not isinstance(entry, Mapping):
            raise ValueError("ROI entries must be objects")
        rois.append(ROI.from_mapping(entry))
    logger.info("Loaded %d ROIs from %s", len(rois), path)
    return rois


def save_roi_set(run_root: Path, rois: Iterable[ROI], filename: str = "rois.json") -> Path:
    """Persist an iterable of ROIs for *run_root* in a deterministic manner."""

    path = roi_file_path(run_root, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialisable = [roi.to_mapping() for roi in sorted(rois, key=lambda item: item.name)]
    with path.open("w", encoding="utf-8") as handle:
        json.dump(serialisable, handle, indent=2, sort_keys=True)
        handle.write("\n")
    logger.info("Saved %d ROIs to %s", len(serialisable), path)
    return path


def load_raw16_image(path: Path, *, width: int, height: int, stride: int | None = None) -> np.ndarray:
    """Load a RAW16 frame into a 2D NumPy array using capture metadata."""

    if not path.exists():
        raise FileNotFoundError(path)

    stride = stride or width
    expected_pixels = stride * height
    data = np.fromfile(path, dtype=np.uint16)
    if data.size < expected_pixels:
        raise ValueError(
            f"RAW16 file {path} is too small for expected dimensions {width}x{height}"
        )
    image = data[:expected_pixels].reshape(height, stride)
    if stride != width:
        image = image[:, :width]
    return image


def select_rois_interactively(
    image: np.ndarray,
    *,
    roi_size: tuple[int, int] = (16, 16),
    existing: Sequence[ROI] | None = None,
    window_title: str | None = None,
) -> list[ROI]:
    """Display *image* and collect ROI centers via matplotlib clicks."""

    try:
        import matplotlib.pyplot as plt
        from matplotlib import patches
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("matplotlib is required for ROI selection") from exc

    rois: list[ROI] = list(existing or [])
    next_index = 1 + max(
        (int(roi.name.split("_")[-1]) for roi in rois if "_" in roi.name and roi.name.split("_")[-1].isdigit()),
        default=0,
    )

    fig, ax = plt.subplots()
    manager = getattr(fig.canvas, "manager", None)
    if manager is not None:
        try:  # pragma: no cover - backend specific
            manager.set_window_title(window_title or "ROI Selection")
        except AttributeError:
            pass
    ax.imshow(image, cmap="gray")
    ax.set_title("Left click to add ROI, right click to remove last, close window when done")

    artists: list[object] = []

    def redraw() -> None:
        while artists:
            artist = artists.pop()
            try:
                artist.remove()
            except Exception:  # pragma: no cover - matplotlib API
                pass
        for roi in rois:
            origin_x, origin_y, width, height = roi.bounds()
            rect = patches.Rectangle(
                (origin_x, origin_y),
                width,
                height,
                linewidth=1.5,
                edgecolor="tab:red",
                facecolor="none",
            )
            label = ax.text(
                roi.center[0],
                roi.center[1],
                roi.name,
                color="tab:red",
                fontsize="small",
                ha="center",
                va="center",
                backgroundcolor="black",
                alpha=0.7,
            )
            ax.add_patch(rect)
            artists.extend([rect, label])
        fig.canvas.draw_idle()

    def on_click(event) -> None:  # type: ignore[no-untyped-def]
        nonlocal next_index
        if event.inaxes != ax:
            return
        if event.button == 1:  # left click adds ROI
            x = int(round(event.xdata))
            y = int(round(event.ydata))
            name = f"roi_{next_index:02d}"
            next_index += 1
            rois.append(ROI(name=name, center=(x, y), size=roi_size))
            logger.info("Added ROI %s at (%d, %d)", name, x, y)
            redraw()
        elif event.button in {2, 3}:  # middle/right removes last ROI
            if rois:
                removed = rois.pop()
                next_index = max(next_index - 1, 1)
                logger.info("Removed ROI %s", removed.name)
                redraw()

    cid = fig.canvas.mpl_connect("button_press_event", on_click)
    redraw()
    plt.show()
    fig.canvas.mpl_disconnect(cid)
    plt.close(fig)

    if not rois:
        raise RuntimeError("No ROIs were selected")
    return rois


def render_roi_preview(
    image: np.ndarray,
    rois: Sequence[ROI],
    output_path: Path,
) -> None:
    """Render a PNG preview that overlays the ROI selections on *image*."""

    try:
        import matplotlib.pyplot as plt
        from matplotlib import patches
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("matplotlib is required to render ROI previews") from exc

    fig, ax = plt.subplots()
    ax.imshow(image, cmap="gray")
    ax.set_title("ROI Preview")
    for roi in rois:
        origin_x, origin_y, width, height = roi.bounds()
        rect = patches.Rectangle(
            (origin_x, origin_y),
            width,
            height,
            linewidth=1.5,
            edgecolor="tab:red",
            facecolor="none",
        )
        ax.add_patch(rect)
        ax.text(
            roi.center[0],
            roi.center[1],
            roi.name,
            color="tab:red",
            fontsize="small",
            ha="center",
            va="center",
            backgroundcolor="black",
            alpha=0.7,
        )
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    logger.info("Wrote ROI preview to %s", output_path)


def _select_verification_frame(record: "CaptureRecord") -> Path:
    """Return a RAW16 frame for verification distinct from ROI selection if possible."""

    candidates: list[Path] = []
    for path in record.converted_files:
        candidate = Path(path)
        if candidate.suffix.lower() in {".raw", ".raw16", ".bin"} and candidate.exists():
            candidates.append(candidate)
    if not candidates and record.raw16_dir.exists():
        for path in sorted(record.raw16_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in {".raw", ".raw16", ".bin"}:
                candidates.append(path)

    if not candidates:
        raise FileNotFoundError(
            f"No RAW16 frames available for verification in {record.capture_dir}"
        )

    candidates = sorted(dict.fromkeys(candidates))
    if len(candidates) >= 2:
        return candidates[1]
    logger.debug(
        "Only one RAW16 frame available for verification in %s; reusing it",
        record.capture_dir,
    )
    return candidates[0]


def _clip_roi_bounds(image: np.ndarray, roi: ROI) -> tuple[int, int, int, int] | None:
    x0, y0, width, height = roi.bounds()
    x1 = x0 + width
    y1 = y0 + height
    frame_height, frame_width = image.shape

    if x1 <= 0 or y1 <= 0 or x0 >= frame_width or y0 >= frame_height:
        logger.warning("ROI %s lies completely outside the frame and will be ignored", roi.name)
        return None

    clipped_x0 = max(x0, 0)
    clipped_y0 = max(y0, 0)
    clipped_x1 = min(x1, frame_width)
    clipped_y1 = min(y1, frame_height)
    if clipped_x0 != x0 or clipped_y0 != y0 or clipped_x1 != x1 or clipped_y1 != y1:
        logger.warning(
            "ROI %s extends beyond frame bounds; clipping to valid region", roi.name
        )
    return clipped_x0, clipped_y0, clipped_x1, clipped_y1


def _contrast_scale(image: np.ndarray, *, percentile: float = 1.0) -> tuple[np.ndarray, float, float]:
    if image.size == 0:
        raise ValueError("Cannot scale contrast of an empty image")
    lower = float(np.percentile(image, percentile)) if percentile > 0 else float(image.min())
    upper = (
        float(np.percentile(image, 100 - percentile))
        if percentile > 0
        else float(image.max())
    )
    if upper <= lower:
        upper = lower + 1.0
    clipped = np.clip(image.astype(np.float64), lower, upper)
    scaled = (clipped - lower) / (upper - lower)
    return (scaled * 255).astype(np.uint8), lower, upper


def _apply_existing_scale(image: np.ndarray, *, lower: float, upper: float) -> np.ndarray:
    clipped = np.clip(image.astype(np.float64), lower, upper)
    scaled = (clipped - lower) / (upper - lower)
    return (scaled * 255).astype(np.uint8)


def generate_roi_verification_image(
    record: "CaptureRecord",
    rois: Sequence[ROI],
    output_path: Path,
    *,
    contrast_percentile: float = 1.0,
) -> Path:
    """Create a side-by-side PNG comparing the original frame and ROIs masked out."""

    if not rois:
        raise ValueError("ROI verification requires at least one ROI")

    frame_path = _select_verification_frame(record)
    logger.info("Generating ROI verification image from %s", frame_path)
    frame = load_raw16_image(
        frame_path,
        width=record.run.config.raw_width,
        height=record.run.config.raw_height,
        stride=record.run.config.raw_stride,
    )

    masked = frame.copy()
    for roi in rois:
        clipped = _clip_roi_bounds(frame, roi)
        if clipped is None:
            continue
        x0, y0, x1, y1 = clipped
        masked[y0:y1, x0:x1] = 0

    original_display, lower, upper = _contrast_scale(frame, percentile=contrast_percentile)
    masked_display = _apply_existing_scale(masked, lower=lower, upper=upper)

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("matplotlib is required to render ROI verification images") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    titles = [
        "Original (scaled)",
        "ROIs zeroed (scaled)",
    ]
    for axis, image_data, title in zip(axes, (original_display, masked_display), titles):
        axis.imshow(image_data, cmap="gray", vmin=0, vmax=255)
        axis.set_title(title)
        axis.axis("off")
    fig.suptitle(f"ROI Verification - {frame_path.name}")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info("Wrote ROI verification comparison to %s", output_path)
    return output_path


class ROIVerificationRenderer:
    """Pipeline stage that emits ROI zeroing comparisons and a Markdown index."""

    def __init__(
        self,
        *,
        output_dirname: str = "roi_verification",
        filename_template: str = "{illumination}_{sequence}_{exposure}us.png",
        contrast_percentile: float = 1.0,
        report_filename: str | None = "roi_verification.md",
    ) -> None:
        self.output_dirname = output_dirname
        self.filename_template = filename_template
        self.contrast_percentile = contrast_percentile
        self.report_filename = report_filename
        self._report_entries: dict[Path, list[tuple[str, str, int, Path]]] = defaultdict(list)

    def __call__(self, record: "CaptureRecord", roi_result: Sequence[ROI]) -> None:
        rois = list(roi_result)
        if not rois:
            logger.debug("Skipping ROI verification for %s (no ROIs)", record.capture_dir)
            return

        filename = self.filename_template.format(
            illumination=_slugify(record.illumination.name),
            sequence=_slugify(record.sequence.label),
            exposure=record.exposure_us,
        )
        output_dir = record.capture_dir / self.output_dirname
        output_path = output_dir / filename

        try:
            generate_roi_verification_image(
                record,
                rois,
                output_path,
                contrast_percentile=self.contrast_percentile,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to create ROI verification for %s: %s", record.capture_dir, exc)
            return

        if self.report_filename is None:
            return

        rel_path: Path
        try:
            rel_path = output_path.relative_to(record.run.root)
        except ValueError:
            rel_path = output_path

        entry = (record.illumination.name, record.sequence.label, record.exposure_us, rel_path)
        self._report_entries[record.run.root].append(entry)
        self._write_report(record.run.root)

    def _write_report(self, run_root: Path) -> None:
        if self.report_filename is None:
            return
        report_path = run_root / self.report_filename
        entries = sorted(self._report_entries[run_root])
        lines = ["# ROI Verification Images\n\n"]
        for illumination, sequence, exposure_us, rel_path in entries:
            rel_str = rel_path.as_posix()
            lines.append(
                f"- **{illumination} / {sequence} / {exposure_us}\u00b5s**: [{rel_str}]({rel_str})\n"
            )
        report_path.write_text("".join(lines), encoding="utf-8")
        logger.info("Updated ROI verification report at %s", report_path)


def _slugify(component: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in component)


class InteractiveROISelector:
    """Callable analysis stage that ensures ROI definitions exist for a run."""

    def __init__(
        self,
        *,
        roi_size: tuple[int, int] = (16, 16),
        roi_filename: str = "rois.json",
        preview_filename: str = "roi_check.png",
    ) -> None:
        self.roi_size = roi_size
        self.roi_filename = roi_filename
        self.preview_filename = preview_filename
        self._cache: dict[Path, list[ROI]] = {}

    def __call__(self, record: "CaptureRecord") -> list[ROI]:  # pragma: no cover - requires GUI
        run_root = record.run.root
        cached = self._cache.get(run_root)
        if cached is not None:
            return cached

        rois = load_roi_set(run_root, self.roi_filename)
        if rois:
            preview_path = run_root / self.preview_filename
            if not preview_path.exists():
                try:
                    representative_frame = self._locate_representative_frame(record)
                    image = load_raw16_image(
                        representative_frame,
                        width=record.run.config.raw_width,
                        height=record.run.config.raw_height,
                        stride=record.run.config.raw_stride,
                    )
                except Exception as exc:  # pragma: no cover - best effort regeneration
                    logger.warning("Unable to regenerate ROI preview: %s", exc)
                else:
                    render_roi_preview(image, rois, preview_path)
            self._cache[run_root] = rois
            return rois

        representative_frame = self._locate_representative_frame(record)
        logger.info("Selecting ROIs using %s", representative_frame)
        image = load_raw16_image(
            representative_frame,
            width=record.run.config.raw_width,
            height=record.run.config.raw_height,
            stride=record.run.config.raw_stride,
        )
        rois = select_rois_interactively(
            image,
            roi_size=self.roi_size,
            window_title=f"ROI Selection - {record.run.config.scene_name}",
        )
        save_roi_set(run_root, rois, self.roi_filename)
        render_roi_preview(image, rois, run_root / self.preview_filename)
        self._cache[run_root] = rois
        return rois

    def _locate_representative_frame(self, record: "CaptureRecord") -> Path:
        """Find a RAW16 file that can be used for ROI selection."""

        candidates: list[Path] = []
        for path in record.converted_files:
            if path.suffix.lower() in {".raw", ".raw16"}:
                candidates.append(path)
        if not candidates and record.raw16_dir.exists():
            candidates.extend(sorted(record.raw16_dir.glob("*.raw")))
        if not candidates:
            raise FileNotFoundError(
                "No RAW16 frames available for ROI selection in " f"{record.capture_dir}"
            )
        return candidates[0]


# Import lazily to avoid circular dependencies at module import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from .pipeline import CaptureRecord
