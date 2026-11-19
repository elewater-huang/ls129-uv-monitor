# LS129 UV Monitor — English

**[繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [English](README.en.md)**

## Overview

A Python/Tkinter Windows desktop monitor for the display-less Linshang LS129 UV probe, connected through an ATK-MO340P USB–RS485 adapter using Modbus RTU. Displays live UV power, peak UV power, accumulated UV energy, and a real-time graph; saves complete raw communication records to CSV. Target environment: Windows 7 32-bit, Python 3.7.9, PySerial 3.5.

## What's new in v0.3.0

- **Three UI languages**: Traditional Chinese, Simplified Chinese, and English, selectable at the upper right of the window, with an immediate UI update.
- **Saved language**: `settings.json` stores `language` as `zh-TW`, `zh-CN`, or `en`; the next launch restores it.
- **Freeform polling rate**: Any decimal number `> 0` and `<= 32` Hz is allowed, such as `0.2`, `2.5`, `31.5`, or `32`. This is a PC request rate, **not** the LS129 internal ADC sampling rate.
- **Saved smoothing selection**: `smoothing_mode` is 0 (OFF/DC), 1 (50 Hz), or 2 (60 Hz). Saving a preference never automatically writes the device. After connecting, the app reads the actual smoothing register, displays it, and updates its stored selection.
- Previous v0.2 features remain: one-decimal display, per-poll timestamp and HEX trace, duplicate detection, CSV recording, demo mode, and PC-only EIT correction disabled by default.

## Install / Run

1. Power the LS129 correctly and set the ATK-MO340P to USB-485; wire the differential A/B pins properly.
2. Close AccessPort before launching; only one application can own the serial port.
3. Install Python 3.7 with Tcl/Tk and run `python -m pip install -r requirements.txt`.
4. Run `python LS129_Monitor.py`, or the Windows batch file `啟動_LS129.bat`.
5. Select COM, probe type, and enter a polling rate, then press Enter or leave the field to save it. Reconnect to apply a changed polling rate.
6. Start recording sends Register 50 to reset the sensor's peak and energy counters. Stop and save creates a CSV under `Records/`.

## Settings persistence

The program saves `settings.json` beside the Python script when writable; otherwise it falls back to `~/LS129_UV_Monitor/settings.json`. The file is git-ignored and specific to each computer.

```json
{
  "baud_rate": "9600",
  "com_port": "COM5",
  "data_mode": "INT",
  "language": "en",
  "poll_hz": 0.2,
  "probe_type": "UVALED",
  "slave_id": "1",
  "smoothing_mode": 2
}
```

0.2 Hz is one request every five seconds. 32 Hz is a target interval of 31.25 ms; actual throughput depends on Modbus round-trip time and PC scheduling.

**No automatic write-back of smoothing:** choosing OFF/50/60 Hz is saved as a PC preference. Only an explicit **Apply and verify** action writes Modbus Register 320 and reads the result back. The app does not write the LS129 external calibration register. EIT correction remains PC-only and OFF by default.

## CSV records and interpretation

Each CSV contains raw and PC-corrected values, Modbus request/response HEX including CRC, wall-clock timestamps, real receive gaps and round-trip latency, and duplicate-run counts. `target_poll_hz` records the configured request rate, not effective physical sensor bandwidth.

The public protocol describes Modbus RTU master requests and LS129 slave replies; it does not describe a confirmed unsolicited streaming mode. A PC queue decouples communication from plotting, but cannot replace sensor replies.

## Tests

Run `python LS129_Monitor.py --self-test`. This checks CRC, INT/FLOAT parsing, rounding, decimal polling rates, and config persistence. UI-level language/relaunch and demo CSV testing is available in `tests/test_v03_gui.py` (Linux Xvfb). Physical LS129 validation at 32 Hz remains to be performed.

Protocol: [LS129 Communication Protocol V3.2](https://images.linshangtech.com/user-manual/LS129_Communication_Protocol_V3.2.pdf).
