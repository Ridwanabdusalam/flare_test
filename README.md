# Flare Capture Automation Toolkit

This repository collects the MATLAB reference scripts and a Python automation workflow used for flare test image acquisition. The Python tooling encapsulates every step of the capture sequence—lighting control, Android device orchestration, RAW conversion, and metadata recording—so that a test operator only supplies a configuration file describing the desired experiment.

## Repository Layout

```
flare_capture.py          # CLI entry point that runs the end-to-end workflow
flare_automation/         # Python package that houses the automation components
example_config.yaml       # Sample configuration file to customize for each run
unpack_mipi_raw10.py      # Legacy RAW10 -> RAW16 converter used by the workflow
step*.m                   # Original MATLAB scripts for manual or reference workflows
```

The MATLAB scripts are kept for parity and comparison, but new runs should be driven through `flare_capture.py` so that the entire process is repeatable and logged.

## Prerequisites

1. **Python**: Python 3.10 or newer is recommended.
2. **Python packages**: Install the runtime dependencies with pip:
   ```bash
   pip install pyserial pyyaml
   ```
   * `pyserial` is required for COM port discovery and illumination control.
   * `PyYAML` is optional but enables YAML configuration files (JSON works out of the box).
3. **Android platform tools**: `adb` must be available on your system `PATH` with the capture device authorized for debugging.
4. **RAW converter prerequisites**: `unpack_mipi_raw10.py` is invoked with `python3`. Ensure any libraries it requires are installed (see that script for details).
5. **Hardware**:
   * Windows PC or laptop connected to the illumination controller over USB serial.
   * Android capture device connected over USB.
   * LED fixtures wired to accept the serial commands defined in your configuration.

> **Tip:** If multiple Android devices or serial interfaces are connected, either unplug the extras or specify identifiers in the configuration file to avoid ambiguity.

## Quick Start

1. **Clone the repository** (or download the relevant files) onto the Windows host that will control the experiment.
2. **Create a virtual environment** (optional but recommended) and install dependencies.
3. **Copy `example_config.yaml`** to a new file (e.g., `my_run.yaml`) and edit the values to match your setup.
4. **Run the workflow**:
   ```bash
   python flare_capture.py my_run.yaml
   ```
5. Monitor the console output; a summary line is printed for each illumination/exposure combination captured. When the run finishes, the output directory contains raw footage, converted frames, and metadata files you can feed into downstream analysis scripts.

The sections below explain the configuration options and runtime behavior in more detail.

## Configuration Reference

The configuration file describes everything required for a capture run. YAML is encouraged for readability, but JSON files with the same structure are also accepted. Every path is resolved relative to the working directory unless an absolute path is provided.

### Global experiment settings

| Field | Required | Description |
| ----- | -------- | ----------- |
| `output_root` | Yes | Directory where run folders will be created. A timestamped subfolder is added per execution. |
| `scene_name` | Yes | Friendly name that prefixes the run directory (e.g., `lensA_darkroom`). |
| `camera_id` | No (default `0`) | Camera selector passed to `camcapture` on the Android device. |
| `resolution` | No (default `4032x3024`) | Sensor mode/resolution string for `camcapture`. |
| `remote_raw_dir` | No (default `/data/vendor/camera`) | Directory on the Android device where RAW files appear. |
| `raw_converter` | No (default `unpack_mipi_raw10.py`) | Path to the RAW10→RAW16 conversion script. |
| `raw_width`, `raw_height`, `raw_stride` | No | Frame geometry supplied to the converter; adjust to your sensor. |

### Serial communication

| Field | Required | Description |
| ----- | -------- | ----------- |
| `serial_baud` | No (default `19200`) | Baud rate for the illumination controller. |
| `serial_terminator` | No (default carriage return) | Character appended to each command (match your firmware expectations). |
| `preferred_com_port` | Recommended | Explicit COM port (e.g., `COM11`). Use when multiple serial devices exist. |
| `serial_vendor_id`, `serial_product_id` | Optional | USB VID/PID filters (hex strings like `0403`). Useful for auto-selection when the port number varies. |

### Android device control

| Field | Required | Description |
| ----- | -------- | ----------- |
| `adb_serial` | Optional | Android device serial number (from `adb devices -l`). Needed when more than one device is attached. |
| `adb_timeout_s` | No (default `10.0`) | Timeout (seconds) for ADB operations. |

### Illumination profiles

Define each lighting condition under the `illumination` array:

```yaml
illumination:
  - name: led_ring
    serial_command: "p 0 020"
    pwm_percent: 20      # Optional metadata only
    settle_time_s: 1.0   # Allow hardware to stabilize before capture
```

* `name` – Used for folder naming in the output directory.
* `serial_command` – Raw command string sent over serial.
* `pwm_percent` – Optional field stored in metadata (not interpreted by the workflow).
* `settle_time_s` – Delay after sending the command before the capture loop begins.

### Exposure sequences

Expose each sweep of captures under `exposure_sequences`:

```yaml
exposure_sequences:
  - label: visible
    exposure_us: [32000, 64000, 128000]
    iso: 1600
    frame_count: 1
```

* `label` – Included in directory names and metadata.
* `exposure_us` – List of shutter durations in microseconds. At least one value is required.
* `iso` – Gain applied for the entire sequence.
* `frame_count` – Number of frames to capture per exposure (looped on-device).

Every illumination profile is paired with every exposure sequence, resulting in a Cartesian product of capture runs.

## What the Workflow Does

For each illumination/sequence combination the workflow:

1. Selects or discovers the specified COM port and opens a serial connection.
2. Creates a timestamped run directory under `output_root` and writes `config.json` to record the exact settings used.
3. Issues ADB commands to stop the legacy capture service, remount storage (for permissions), and clear stale RAW frames from the device.
4. Sends the configured illumination command and waits for the specified settle delay.
5. Iterates through each exposure value:
   * Clears any leftover RAW files on the device.
   * Invokes `camcapture` via ADB to acquire the requested frame count.
   * Pulls the generated `.raw` files into `<run>/<illumination>/<label>_<exposure>us/raw10/`.
   * Runs `unpack_mipi_raw10.py` to convert each RAW10 file into RAW16 under `raw16/`.
   * Writes `capture.json` describing the illumination, exposure, and list of files produced.
6. Yields progress information back to the CLI, which prints a summary line for visibility.

All metadata is stored as JSON so downstream processing can reconstruct the capture context without inspecting folder names.

## Output Structure

The folder hierarchy created per run looks like:

```
<output_root>/
  sceneName_YYYYMMDD_HHMMSS/
    config.json
    led_ring/
      sequence.json
      visible_64000us/
        capture.json
        raw10/
          frame_000.raw
        raw16/
          frame_000_16.raw
    object_ring/
      ...
```

This layout ensures raw captures and converted frames remain paired by illumination and exposure. The metadata files can be ingested by analysis notebooks or ported MATLAB scripts.

## Troubleshooting & Tips

* **Serial discovery fails**: Provide `preferred_com_port` explicitly or confirm that `pyserial` is installed and the device drivers expose the interface as a COM port.
* **Multiple serial devices found**: Either disconnect the extras or set `preferred_com_port` so the workflow knows which one to use.
* **ADB timeouts**: Increase `adb_timeout_s` for slower devices or check the USB connection.
* **RAW conversion errors**: Validate that `raw_width`, `raw_height`, and `raw_stride` match the sensor output. You can test the converter independently:
  ```bash
  python unpack_mipi_raw10.py -i sample.raw -o sample_16.raw -x 4032 -y 3024 -s 5040
  ```
* **Dry runs**: If you want to validate serial and ADB connectivity without collecting frames, temporarily set `frame_count: 0` or comment out sequences while testing wiring.

## Extending the Workflow

The Python package is organized so you can swap or enhance individual pieces:

* `flare_automation.config` – Dataclasses and loaders for strongly-typed configuration.
* `flare_automation.serial_controller` – Serial discovery/control; adapt if your hardware requires different framing or acknowledgements.
* `flare_automation.adb_controller` – Thin wrapper around ADB operations; extend with custom shell commands if you need additional device setup.
* `flare_automation.raw_conversion` – Currently shells out to the legacy converter; replace with a native implementation if desired.
* `flare_automation.workflow` – High-level orchestration. Hooks can be added to log to a database, notify observers, or integrate with ROI selection tools.

Because every capture step is driven by configuration and metadata is written to disk, the workflow is reproducible and easier to audit than the ad hoc MATLAB pipeline.

## Relationship to Legacy MATLAB Scripts

The MATLAB scripts (`step1_adjust_brightness.m` through `step7_check_rois.m`) document the original manual procedure for flare testing. Use them as a reference for validation or when porting analysis code to Python, but prefer the automated Python workflow for production captures.

## Next Steps

Once images are captured, you can process the RAW16 files with your analysis pipeline (for example, porting the MATLAB flare calculations to Python/NumPy). The JSON metadata produced by the workflow provides the exposure ladder, illumination settings, and file lists needed to batch the analysis stage.
