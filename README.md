# Flare Capture Automation Toolkit

The Flare Capture Automation Toolkit combines the original MATLAB reference
scripts with a modern Python pipeline that automates flare image acquisition and
post-processing. The Python workflow coordinates illumination hardware over
serial, controls an Android capture device via ADB, converts RAW10 frames to
RAW16, and optionally launches an ROI-driven analysis pass that mirrors the
legacy MATLAB process. The goal is to provide a reproducible, fully logged
workflow that can be executed by following a single configuration file.

## Repository Layout

```
flare_capture.py          # CLI entry point that runs capture + optional analysis
flare_automation/         # Python package containing the workflow and analysis
example_config.yaml       # Sample configuration to adapt for your hardware
unpack_mipi_raw10.py      # Legacy RAW10 -> RAW16 converter invoked by the workflow
step*.m                   # Original MATLAB scripts kept for reference
```

## Requirements

### Hardware
- Windows workstation (recommended) or Linux host with access to required
  serial drivers.
- USB-connected illumination controller that accepts the serial commands used in
  your tests.
- Android capture device with `camcapture` available and authorised for USB
  debugging.
- LED fixtures wired to your illumination controller.

### Software
- **Python**: 3.10 or newer.
- **Python packages** (install inside a virtual environment when possible):
  ```bash
  pip install pyserial PyYAML numpy matplotlib
  ```
  - `pyserial` – mandatory for serial discovery and communication.
  - `PyYAML` – enables YAML configuration files (JSON works without it).
  - `numpy` – required by the analysis pipeline for RAW16 processing.
  - `matplotlib` – required for interactive ROI selection, ROI previews, and
    diagnostic plots during analysis.
- **Android Platform Tools**: `adb` must be on your `PATH` and the capture
  device must be authorised.
- **RAW converter dependencies**: `unpack_mipi_raw10.py` is executed with
  `python3`. Install any libraries it expects (see that script's header).

## Initial Setup

1. **Clone the repository** onto the machine that will control the capture run.
2. **Create and activate a virtual environment** (optional but recommended).
   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Linux/macOS
   .\.venv\Scripts\activate         # Windows PowerShell
   pip install --upgrade pip
   pip install pyserial PyYAML numpy matplotlib
   ```
3. **Install Android platform tools** and confirm `adb devices` lists the target
   handset. If multiple devices appear, note the desired serial number.
4. **Connect hardware**:
   - Plug in the illumination controller and note the enumerated COM port.
   - Connect the Android device via USB and enable USB debugging.
   - Ensure the LED fixtures respond to commands sent through your controller's
     serial protocol.

## Preparing the Android Device

Before the first run, verify the Android device accepts the commands the
workflow issues:

```bash
adb root
adb remount
adb shell camcapture -h
```

You may need elevated privileges on the device to run `camcapture`. Grant any
permissions that prompt on-device and ensure root access is available, as the
workflow executes `adb root` and `adb remount` automatically.

## Configuring a Capture Run

Copy `example_config.yaml` to a new file (for example, `my_run.yaml`) and edit
it to reflect your hardware and desired capture sweep. All paths are resolved
relative to the configuration file unless absolute paths are supplied.

### Global Experiment Settings

| Field | Required | Description |
| ----- | -------- | ----------- |
| `output_root` | Yes | Directory where timestamped run folders will be created. |
| `scene_name` | Yes | Friendly name that prefixes each run directory (e.g. `lensA_darkroom`). |
| `camera_id` | No (default `0`) | Camera selector passed to `camcapture`. |
| `resolution` | No (default `4032x3024`) | Sensor mode string forwarded to `camcapture`. |
| `remote_raw_dir` | No (default `/data/vendor/camera`) | Device directory where RAW files appear. |
| `raw_converter` | No (default `unpack_mipi_raw10.py`) | Path to the RAW10→RAW16 converter script. |
| `raw_width`, `raw_height`, `raw_stride` | No (defaults `4032`, `3024`, `5040`) | Dimensions used when converting RAW16 frames. |

### Serial Communication

| Field | Required | Description |
| ----- | -------- | ----------- |
| `serial_baud` | No (default `19200`) | Baud rate for the illumination controller. |
| `serial_terminator` | No (default carriage return) | Character appended to each command. |
| `preferred_com_port` | Recommended | Explicit COM port name (e.g. `COM11`). Avoids ambiguity when multiple devices are attached. |
| `serial_vendor_id`, `serial_product_id` | Optional | USB VID/PID filters (hex strings such as `0403`). Used when auto-discovering the serial device. |

### Android Device Control

| Field | Required | Description |
| ----- | -------- | ----------- |
| `adb_serial` | Optional | Serial number reported by `adb devices -l`. Required when multiple phones/tablets are attached. |
| `adb_timeout_s` | No (default `10.0`) | Timeout (seconds) applied to individual ADB commands. |

### Illumination Profiles

Declare each lighting condition under the `illumination` array:

```yaml
illumination:
  - name: led_ring
    serial_command: "p 0 020"
    pwm_percent: 20      # Optional metadata stored in capture.json
    settle_time_s: 1.0   # Delay after setting illumination before capture starts
```

- `name` – Used for directory naming within the run output.
- `serial_command` – Raw command string written to the illumination controller.
- `pwm_percent` – Optional descriptive metadata recorded in `capture.json`.
- `settle_time_s` – Delay after sending the command before captures begin.

### Exposure Sequences

Define exposure sweeps under `exposure_sequences`:

```yaml
exposure_sequences:
  - label: visible
    exposure_us: [32000, 64000, 128000]
    iso: 1600
    frame_count: 1
```

- `label` – Included in directory names and metadata.
- `exposure_us` – List of shutter durations (µs). At least one value is required.
- `iso` – Gain applied to every exposure in the sequence.
- `frame_count` – Number of frames captured per exposure value.

Every illumination profile is paired with every exposure sequence. Ensure at
least one entry exists in each list or the configuration loader will raise an
error.

## Running the Workflow

Execute the end-to-end capture (and optional analysis) from the repository root:

```bash
python flare_capture.py my_run.yaml
```

The workflow:
1. Discovers or opens the configured serial port.
2. Creates a timestamped directory under `output_root` and writes `config.json`
   with the resolved configuration.
3. Issues ADB commands to stop `captureengineservice`, remount storage, and
   clear stale files in `remote_raw_dir`.
4. Iterates through the illumination/exposure Cartesian product:
   - Sends the illumination command and waits for `settle_time_s`.
   - Captures frames via `camcapture` for each exposure value.
   - Pulls RAW10 files into `<run>/<illumination>/<label>_<exposure>us/raw10/`.
   - Converts each RAW10 file to RAW16 under `raw16/` using the configured
     converter and geometry.
   - Writes `capture.json` summarising metadata and file lists.
5. Prints a progress line such as `Captured 3 files for led_ring @ 64000 us` for
   each capture group.
6. Unless `--skip-analysis` is supplied, launches the analysis pipeline against
   the most recent run (or the directory specified via `--analysis-run-root`).

### Command-line Flags

| Flag | Description |
| ---- | ----------- |
| `--skip-analysis` | Capture only; do not launch the analysis pipeline. |
| `--analysis-run-root PATH` | Analyse an existing run directory instead of the most recent capture. Useful when re-running ROI selection. |
| `--log-level LEVEL` | Adjust logging verbosity (`CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`). |

Run `python flare_capture.py --help` for the full argument list.

## Analysis Workflow

After capture the pipeline defaults to running analysis on the resulting run
folder. The analysis stages live under `flare_automation.analysis` and currently
perform:

1. **Interactive ROI selection** – Matplotlib opens a window showing a RAW16
   frame. Left-click to add ROIs, right-click (or middle-click) to remove the
   last ROI, then close the window when satisfied. The chosen ROIs are persisted
   to `<run>/rois.json`.
2. **ROI verification rendering** – For each capture group a PNG is written to
   `<run>/roi_verification/` showing the original frame next to a version with
   the ROIs zeroed out.
3. **Photo-response analysis** – ROI means are exported to
   `photo_response_measurements.csv`, linear fits are summarised in
   `photo_response_summary.json`, and log–log diagnostic plots are written for
   each ROI.

To rerun analysis later (for example after editing `rois.json`), execute the
analysis entry point directly from Python:

```bash
python -c "from flare_automation import AnalysisConfig, run_analysis; from pathlib import Path; run_analysis(Path('<path-to-run>'), AnalysisConfig())"
```

When you invoke `flare_capture.py` normally, you can include
`--analysis-run-root <path-to-run>` to analyse a specific run after the new
capture completes. Supply `--skip-analysis` if you want to capture only and
defer analysis entirely.

## Output Structure

Each run generates the following hierarchy:

```
<output_root>/
  sceneName_YYYYMMDD_HHMMSS/
    config.json
    rois.json                  # Created after analysis ROI selection
    roi_verification/
      led_ring_visible_64000us.png
    led_ring/
      sequence.json
      visible_64000us/
        capture.json
        raw10/
          frame_000.raw
        raw16/
          frame_000_16.raw
      ...
```

Metadata files (`config.json`, `sequence.json`, `capture.json`) capture all
inputs so downstream tools can reproduce the experiment context without parsing
folder names.

## Troubleshooting

- **Serial discovery fails** – Confirm `pyserial` is installed and supply
  `preferred_com_port` or VID/PID filters if multiple controllers are attached.
- **Multiple serial devices detected** – Disconnect unused devices or set
  `preferred_com_port` explicitly.
- **ADB timeouts** – Increase `adb_timeout_s`, verify the USB cable, and ensure
  the device authorises the host after `adb root`.
- **RAW conversion errors** – Verify `raw_width`, `raw_height`, and `raw_stride`
  match the sensor output. Test the converter manually:
  ```bash
  python unpack_mipi_raw10.py -i sample.raw -o sample_16.raw -x 4032 -y 3024 -s 5040
  ```
- **Matplotlib windows do not appear** – Ensure a desktop environment is
  available (remote sessions may require X forwarding) and that `matplotlib` is
  installed with a GUI backend.
- **Skipping analysis** – Use `--skip-analysis` during capture to avoid GUI
  prompts. You can run analysis later from a workstation with display support.

## Relationship to Legacy MATLAB Scripts

The MATLAB scripts (`step1_adjust_brightness.m` … `step7_check_rois.m`) describe
the original manual workflow. They remain for reference and validation, but new
experiments should use the automated Python tooling for repeatability, logging,
and integration with downstream analysis.

