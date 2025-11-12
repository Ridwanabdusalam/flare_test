"""Command-line entry point for the flare automation workflow."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from flare_automation import (
    AnalysisConfig,
    CaptureConfig,
    FlareCaptureWorkflow,
    run_analysis,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automate flare capture experiments")
    parser.add_argument(
        "config",
        type=Path,
        help="Path to the JSON or YAML configuration file",
    )
    parser.add_argument(
        "--analysis-run-root",
        type=Path,
        help="Optional run directory to analyze instead of the most recent",
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Do not execute the analysis pipeline after capture completes",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity for the capture and analysis workflow",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=getattr(logging, args.log_level))
    config = CaptureConfig.load(args.config)
    if not config.output_root.is_absolute():
        config.output_root = (args.config.parent / config.output_root).resolve()
    workflow = FlareCaptureWorkflow(config)
    last_result = None
    for result in workflow.run():
        print(
            f"Captured {len(result.captured_files)} files for {result.illumination.name} "
            f"@ {result.exposure_us} us"
        )
        last_result = result
    if args.skip_analysis:
        return 0

    run_root = args.analysis_run_root
    if run_root is None:
        if last_result is not None:
            run_root = last_result.run_dir
        else:
            run_root = _find_latest_run(config.output_root)

    if run_root is None:
        print("No capture runs available for analysis", file=sys.stderr)
        return 1

    run_root = run_root.resolve()
    print(f"Running analysis for {run_root}")
    run_analysis(run_root, AnalysisConfig())
    return 0


def _find_latest_run(output_root: Path) -> Path | None:
    if not output_root.exists():
        return None
    candidates = [
        path
        for path in output_root.iterdir()
        if path.is_dir() and (path / "config.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
