"""Command-line entry point for the flare automation workflow."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flare_automation import CaptureConfig, FlareCaptureWorkflow


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
    for result in workflow.run():
        print(
            f"Captured {len(result.captured_files)} files for {result.illumination.name} "
            f"@ {result.exposure_us} us"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
