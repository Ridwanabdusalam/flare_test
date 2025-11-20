"""Generate an autodetect ROI preview from an existing RAW16 frame."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from flare_automation.analysis.autodetect_roi import (
    autodetect_black_hole_roi,
    generate_autodetect_verification_image,
)

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect the darkest point in a RAW16 frame and render a PNG preview with "
            "the chart bounding box and ROI overlay."
        )
    )
    parser.add_argument(
        "--image",
        required=True,
        type=Path,
        help="Path to the RAW16 frame to analyse.",
    )
    parser.add_argument(
        "--width",
        type=int,
        help="Image width in pixels. Omit to let the script guess from file size.",
    )
    parser.add_argument(
        "--height",
        type=int,
        help="Image height in pixels. Omit to let the script guess from file size.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=None,
        help=(
            "Row stride in pixels. Defaults to width when omitted. "
            "Useful when frames include padding."
        ),
    )
    parser.add_argument(
        "--roi-size",
        nargs=2,
        metavar=("WIDTH", "HEIGHT"),
        type=int,
        default=(16, 16),
        help="Size of the ROI rectangle around the darkest point (default: 16 16).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("autodetect_roi_preview.png"),
        help="Destination PNG path (default: autodetect_roi_preview.png).",
    )
    parser.add_argument(
        "--contrast-percentile",
        type=float,
        default=1.0,
        help=(
            "Percentile used when contrast-scaling the preview image. "
            "Larger values reduce the effect of hot pixels."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging for troubleshooting the detection pipeline.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    logger.info("Running autodetect on %s", args.image)

    roi, chart_bbox = autodetect_black_hole_roi(
        args.image,
        width=args.width,
        height=args.height,
        stride=args.stride,
        roi_size=tuple(args.roi_size),
    )

    generate_autodetect_verification_image(
        args.output,
        args.image,
        width=args.width,
        height=args.height,
        stride=args.stride,
        chart_bbox=chart_bbox,
        roi=roi,
        contrast_percentile=args.contrast_percentile,
    )

    logger.info("Wrote preview to %s", args.output)


if __name__ == "__main__":
    main()
