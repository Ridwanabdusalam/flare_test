"""Wrapper around the legacy RAW10 -> RAW16 converter."""
from __future__ import annotations

from pathlib import Path

from .utils import ensure_directory, run_command


def convert_raw10_to_raw16(
    *,
    converter: Path,
    input_path: Path,
    output_dir: Path,
    width: int,
    height: int,
    stride: int,
) -> Path:
    ensure_directory(output_dir)
    output_path = output_dir / f"{input_path.stem}_16.raw"
    cmd = [
        "python3",
        str(converter),
        "-i",
        str(input_path),
        "-o",
        str(output_path),
        "-x",
        str(width),
        "-y",
        str(height),
        "-s",
        str(stride),
    ]
    run_command(cmd)
    return output_path
