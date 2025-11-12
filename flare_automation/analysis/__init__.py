"""Analysis pipeline utilities for flare capture runs."""
from .pipeline import (
    AnalysisConfig,
    CaptureRecord,
    RunMetadata,
    RunDataError,
    iter_capture_records,
    run_analysis,
)
from .photo_response import (
    PhotoResponseMeasurement,
    PhotoResponseResult,
    RoiFitResult,
    analyze_photo_response,
)
from .roi import (
    ROI,
    InteractiveROISelector,
    load_raw16_image,
    load_roi_set,
    render_roi_preview,
    save_roi_set,
    select_rois_interactively,
)

__all__ = [
    "AnalysisConfig",
    "CaptureRecord",
    "RunMetadata",
    "RunDataError",
    "ROI",
    "InteractiveROISelector",
    "PhotoResponseMeasurement",
    "PhotoResponseResult",
    "RoiFitResult",
    "analyze_photo_response",
    "load_raw16_image",
    "load_roi_set",
    "iter_capture_records",
    "render_roi_preview",
    "save_roi_set",
    "select_rois_interactively",
    "run_analysis",
]
