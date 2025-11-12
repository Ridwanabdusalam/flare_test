"""Automation toolkit for flare image capture workflows."""

from .config import (
    AnalysisConfig,
    CaptureConfig,
    ExposureSequence,
    IlluminationConfig,
    ROIAnalysisConfig,
    SceneAnalysisConfig,
)
from .workflow import FlareCaptureWorkflow, RunContext
from .analysis import AnalysisResult, FlareAnalysisWorkflow

__all__ = [
    "AnalysisConfig",
    "CaptureConfig",
    "ExposureSequence",
    "IlluminationConfig",
    "ROIAnalysisConfig",
    "SceneAnalysisConfig",
    "FlareCaptureWorkflow",
    "FlareAnalysisWorkflow",
    "RunContext",
    "AnalysisResult",
]
