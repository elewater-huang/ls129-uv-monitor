# LS129 UV Monitor

**[繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [English](README.en.md)**

Python/Tkinter desktop monitor for the Linshang LS129 via Modbus RTU over an ATK-MO340P USB–RS485 adapter. Designed for Windows 7 32-bit / Python 3.7.9.

**Version v0.3.0 — November 19, 2026.** Main improvements: trilingual UI (Traditional Chinese, Simplified Chinese, English), instant language switching with saved preference, manual PC polling rate **0 < Hz ≤ 32** (decimals accepted, e.g. `0.2`, `31.5`), and stored light-source smoothing preference (OFF/50 Hz/60 Hz).

**Important:** A saved smoothing preference **does not write to the LS129 automatically**. The app reads the actual sensor value after connecting; only an explicit **Apply and verify** action writes Modbus Register 320. No external EIT calibration register is written.

Run `python LS129_Monitor.py`, or `python LS129_Monitor.py --self-test`. Install PySerial using `python -m pip install -r requirements.txt` for physical RS485 connection. Demo mode does not need PySerial.

See the language-specific READMEs for installation, configuration, protocol behavior, CSV format, and limitations.

![V0.1 interface reference; the v0.3 UI adds a language dropdown and freeform polling-rate entry](docs/interface-preview.png)

The picture is an earlier layout reference, **not a screenshot of v0.3**.

Licensed status: no license chosen by the repository owner.
