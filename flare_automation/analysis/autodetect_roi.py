"""Automated ROI detection for the analysis pipeline."""
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from skimage.filters import threshold_otsu

from .roi import ROI, load_raw16_image, _contrast_scale

logger = logging.getLogger(__name__)


class ChartNotFoundError(RuntimeError):
    """Raised when the chart area cannot be located in an image."""


def autodetect_black_hole_roi(
    image_path: Path,
    *,
    width: int,
    height: int,
    stride: int | None = None,
    roi_size: tuple[int, int] = (16, 16),
) -> tuple[ROI, tuple[int, int, int, int]]:
    """
    Automatically detects the black hole ROI in a raw16 image.

    Args:
        image_path: Path to the raw16 image file.
        width: Image width.
        height: Image height.
        stride: Image stride.
        roi_size: The size of the ROI to create around the detected center.

    Returns:
        A tuple containing the detected ROI and the bounding box of the chart.
    """
    # 1. Load the raw16 image
    image = load_raw16_image(image_path, width=width, height=height, stride=stride)

    # 2. Normalize to 8-bit for robust thresholding
    # Use percentiles to be robust to hot/dead pixels
    high = np.percentile(image, 99.9)
    low = np.percentile(image, 0.1)
    if high <= low:
        high = np.max(image)
        low = np.min(image)

    scale = 255.0 / (high - low + 1e-6)
    norm_image = np.clip((image - low) * scale, 0, 255).astype(np.uint8)

    logger.debug(
        "Percentile scaling for %s -> low=%.2f, high=%.2f (scale=%.6f)",
        image_path,
        low,
        high,
        scale,
    )

    # 3. Apply Otsu's threshold to find the chart (assumes bimodal distribution)
    thresh = threshold_otsu(norm_image)

    logger.debug("Global Otsu threshold: %.2f", thresh)

    # First, find the bright illuminated area
    binary_bright = (norm_image > thresh).astype(np.uint8) * 255
    contours_bright, _ = cv2.findContours(binary_bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours_bright:
        raise ChartNotFoundError("No bright contours found in the image.")

    largest_bright_contour = max(contours_bright, key=cv2.contourArea)
    ill_x, ill_y, ill_w, ill_h = cv2.boundingRect(largest_bright_contour)

    logger.debug(
        "Illuminated (white) area bbox: x=%d y=%d w=%d h=%d", ill_x, ill_y, ill_w, ill_h
    )

    # Now, find the dark chart area within the illuminated area
    illuminated_region_norm = norm_image[ill_y : ill_y + ill_h, ill_x : ill_x + ill_w]

    # We need a new threshold for this sub-region
    thresh_chart = threshold_otsu(illuminated_region_norm)
    binary_dark = (illuminated_region_norm < thresh_chart).astype(np.uint8) * 255

    logger.debug("Chart (dark) Otsu threshold inside illuminated area: %.2f", thresh_chart)


    # 4. Find contours of the dark regions
    contours, _ = cv2.findContours(binary_dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        raise ChartNotFoundError("No contours found in the image.")

    # 5. Find the largest contour by area, which should be the chart
    largest_contour = max(contours, key=cv2.contourArea)
    chart_x_rel, chart_y_rel, chart_w, chart_h = cv2.boundingRect(largest_contour)

    # Convert relative coordinates to absolute
    chart_x = ill_x + chart_x_rel
    chart_y = ill_y + chart_y_rel
    chart_bbox = (chart_x, chart_y, chart_w, chart_h)

    logger.debug(
        "Chart (black) area bbox: x=%d y=%d w=%d h=%d", chart_x, chart_y, chart_w, chart_h
    )


    # 6. Find the darkest point within the chart's bounding box in the *original* image
    chart_region = image[chart_y : chart_y + chart_h, chart_x : chart_x + chart_w]
    if chart_region.size == 0:
        raise ChartNotFoundError("Chart bounding box is empty.")

    min_val_loc = np.unravel_index(np.argmin(chart_region), chart_region.shape)
    # The center is relative to the top-left of the chart region, so add the offset
    center_y = chart_y + min_val_loc[0]
    center_x = chart_x + min_val_loc[1]

    logger.debug(
        "Darkest point within chart region: x=%d y=%d (relative min value %.0f)",
        center_x,
        center_y,
        float(chart_region[min_val_loc]),
    )

    # 7. Create and return the ROI
    roi = ROI(name="black_hole", center=(center_x, center_y), size=roi_size)

    logger.info(
        "Autodetected black hole at (%d, %d) within chart bbox (%d, %d, %d, %d)",
        center_x,
        center_y,
        chart_x,
        chart_y,
        chart_w,
        chart_h,
    )

    return roi, chart_bbox


def generate_autodetect_verification_image(
    output_path: Path,
    image_path: Path,
    *,
    width: int,
    height: int,
    stride: int | None = None,
    chart_bbox: tuple[int, int, int, int],
    roi: ROI,
    contrast_percentile: float = 1.0,
) -> None:
    """
    Generates a verification image for the automated ROI detection.

    Args:
        output_path: The path to save the verification image.
        image_path: Path to the raw16 image file.
        width: Image width.
        height: Image height.
        stride: Image stride.
        chart_bbox: The bounding box of the detected chart area.
        roi: The detected ROI.
        contrast_percentile: Percentile for contrast scaling.
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib import patches
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("matplotlib is required to render ROI previews") from exc

    image = load_raw16_image(image_path, width=width, height=height, stride=stride)
    display_image, _, _ = _contrast_scale(image, percentile=contrast_percentile)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.imshow(display_image, cmap="gray")
    ax.set_title(f"Automated ROI Detection - {image_path.name}")

    # Draw the chart bounding box
    chart_x, chart_y, chart_w, chart_h = chart_bbox
    rect = patches.Rectangle(
        (chart_x, chart_y),
        chart_w,
        chart_h,
        linewidth=1.5,
        edgecolor="red",
        facecolor="none",
        label="Detected Chart Area",
    )
    ax.add_patch(rect)

    # Draw the ROI
    origin_x, origin_y, roi_w, roi_h = roi.bounds()
    roi_rect = patches.Rectangle(
        (origin_x, origin_y),
        roi_w,
        roi_h,
        linewidth=1.5,
        edgecolor="orange",
        facecolor="none",
    )
    ax.add_patch(roi_rect)
    ax.text(
        roi.center[0],
        roi.center[1],
        "+",
        color="orange",
        fontsize="large",
        ha="center",
        va="center",
        fontweight="bold",
    )

    ax.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info("Wrote autodetect verification image to %s", output_path)
