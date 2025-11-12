"""Command-line entry point for the flare automation workflow."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flare_automation import (
    CaptureConfig,
    FlareAnalysisWorkflow,
    FlareCaptureWorkflow,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate flare capture experiments")
    parser.add_argument(
        "config",
        type=Path,
        help="Path to the JSON or YAML configuration file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config = CaptureConfig.load(args.config)
    workflow = FlareCaptureWorkflow(config)
    results = list(workflow.run())
    for result in results:
        print(
            f"Captured {len(result.captured_files)} files for {result.illumination.name} "
            f"@ {result.exposure_us} us"
        )
    if config.analysis and config.analysis.enabled:
        if workflow.run_context is None:
            raise RuntimeError("Capture workflow did not initialize a run context")
        analysis = FlareAnalysisWorkflow(config)
        result = analysis.run(workflow.run_context)
        print(f"Analysis complete. Summary written to {result.summary_file}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
