"""High-level workflow orchestrator for flare capture."""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from .adb_controller import AdbController
from .config import CaptureConfig, ExposureSequence, IlluminationConfig
from .raw_conversion import convert_raw10_to_raw16
from .serial_controller import SerialController
from .utils import ensure_directory, write_metadata


@dataclass
class CaptureResult:
    run_dir: Path
    illumination: IlluminationConfig
    sequence: ExposureSequence
    exposure_us: int
    captured_files: list[Path]
    converted_files: list[Path]


class FlareCaptureWorkflow:
    def __init__(self, config: CaptureConfig) -> None:
        self.config = config
        self.serial_controller = SerialController(
            baudrate=config.serial_baud, terminator=config.serial_terminator
        )
        self.adb_controller = AdbController(serial=config.adb_serial, timeout_s=config.adb_timeout_s)

    def _select_serial_port(self) -> str:
        if self.config.preferred_com_port:
            return self.config.preferred_com_port

        devices = list(
            SerialController.discover(
                vendor_id=self.config.serial_vendor_id, product_id=self.config.serial_product_id
            )
        )
        if not devices:
            raise RuntimeError("No serial devices matched the provided vendor/product filters")
        if len(devices) > 1:
            raise RuntimeError(
                "Multiple serial devices discovered. Specify 'preferred_com_port' to disambiguate."
            )
        return devices[0].port

    def _prepare_device(self) -> None:
        self.adb_controller.root()
        self.adb_controller.stop_service("captureengineservice")
        self.adb_controller.remount()
        self.adb_controller.clear_remote_patterns(
            self.config.remote_raw_dir,
            ["*.jpg", "*.mp4", "*.raw"],
        )

    def _prepare_output(self) -> Path:
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.config.output_root / f"{self.config.scene_name}_{timestamp}"
        ensure_directory(run_dir)
        write_metadata(run_dir / "config.json", self.config)
        return run_dir

    def run(self) -> Iterator[CaptureResult]:  # pragma: no cover - orchestrates hardware
        serial_port = self._select_serial_port()
        with self.serial_controller.open(serial_port) as connection:
            run_dir = self._prepare_output()
            self._prepare_device()
            for illumination, sequence in self.config.iter_sequences():
                self.serial_controller.send_command(
                    connection,
                    illumination.serial_command,
                    settle_time_s=illumination.settle_time_s,
                )
                illumination_dir = run_dir / illumination.name
                ensure_directory(illumination_dir)
                write_metadata(illumination_dir / "sequence.json", sequence)
                for exposure in sequence.exposure_us:
                    captured: list[Path] = []
                    converted: list[Path] = []
                    self.adb_controller.clear_remote_patterns(
                        self.config.remote_raw_dir, ["*.raw"]
                    )
                    self.adb_controller.capture_raw(
                        camera_id=self.config.camera_id,
                        resolution=self.config.resolution,
                        exposure_us=exposure,
                        iso=sequence.iso,
                        frame_count=sequence.frame_count,
                    )
                    exposure_dir = illumination_dir / f"{sequence.label}_{exposure}us"
                    local_camera_dir = exposure_dir / "raw10"
                    ensure_directory(local_camera_dir)
                    ensure_directory(exposure_dir)
                    self.adb_controller.pull(self.config.remote_raw_dir, local_camera_dir)
                    for raw_file in sorted(local_camera_dir.glob("*.raw")):
                        captured.append(raw_file)
                        converted_path = convert_raw10_to_raw16(
                            converter=self.config.raw_converter,
                            input_path=raw_file,
                            output_dir=exposure_dir / "raw16",
                            width=self.config.raw_width,
                            height=self.config.raw_height,
                            stride=self.config.raw_stride,
                        )
                        converted.append(converted_path)
                    write_metadata(
                        exposure_dir / "capture.json",
                        {
                            "illumination": asdict(illumination),
                            "sequence": asdict(sequence),
                            "exposure_us": exposure,
                            "captured": [str(path) for path in captured],
                            "converted": [str(path) for path in converted],
                        },
                    )
                    yield CaptureResult(
                        run_dir=run_dir,
                        illumination=illumination,
                        sequence=sequence,
                        exposure_us=exposure,
                        captured_files=list(captured),
                        converted_files=list(converted),
                    )
