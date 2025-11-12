"""Automation toolkit for flare image capture workflows."""

from .analysis import AnalysisConfig, iter_capture_records, run_analysis
from .config import CaptureConfig, IlluminationConfig, ExposureSequence
from .workflow import FlareCaptureWorkflow

__all__ = [
    "AnalysisConfig",
    "CaptureConfig",
    "IlluminationConfig",
    "ExposureSequence",
    "FlareCaptureWorkflow",
    "iter_capture_records",
    "run_analysis",
]
