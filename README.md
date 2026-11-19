# LS129 UV Monitor / 林上 LS129 紫外線即時監測軟體

**Version / 版本: v0.2.0 · 2026-11-19**  
**Target / 目標平台: Windows 7 32-bit + Python 3.7.9 + Tkinter + PySerial 3.5**

A desktop monitor for the **Linshang LS129** UV sensor through an **ATK-MO340P USB–RS485** adapter using Modbus RTU. The UI borrows the workflow of LS128, but LS129 is a live sensor: the **PC** is responsible for timestamping and recording each reply.

林上 LS129 無螢幕，本程式透過 RS485 即時顯示 UV 功率、最大功率、累積能量、曲線，並把每次測試的資料存到電腦。此版本重點是**驗證對外資料刷新頻率**，不宣稱能存取探頭內部的 2048 Hz 原始取樣。

> **Prototype / 原型狀態：** Modbus example frames, CRC decoding, local settings and a simulated 20 Hz polling run have been tested. **The v0.2.0 Python application has not yet been validated against the physical LS129.** Do not assume that 20 Hz requests produce 20 new sensor values per second.
>
> V0.2 已完成程式與模擬測試；仍須在實體 LS129 現場驗證輪詢成功率、資料格式與單位。

![Earlier interface illustration / V0.1 layout reference](docs/interface-preview.png)

## New in v0.2 / 本版新增

| Feature / 功能 | Behavior / 說明 |
|---|---|
| **1 decimal display / 小數第一位** | Show power/peak/energy with conventional half-up rounding (e.g. `21.25 → 21.3`). **Never round raw CSV data.** |
| **4 / 5 / 20 Hz PC polling** | Select before connecting: every 250 / 200 / 50 ms *target*. Observe **actual received Hz**, not just requested Hz. |
| **Polling lab / 輪詢實驗頁** | Each received sample: elapsed time, inter-reply interval, values, exact Modbus response HEX, duplicate flag, consecutive repeat run and round-trip latency. |
| **Auditable CSV / 可追溯 CSV** | One row per attempted poll during a recording (successful or failed), send/receive timestamps, request/response HEX, raw data, software-corrected data, error status. |
| **Persistent settings / 設定檔** | COM Port, probe type, baud rate, Slave ID, INT/FLOAT mode and selected polling Hz **automatically saved and restored**. |
| **Simulation / 模擬** | Demo intentionally refreshes its synthetic registers every 200 ms so 20 Hz querying creates repeated values for workflow testing. |

**Do not confuse** the PC's requested *polling frequency* with sensor internal *ADC sampling* or the LS129 register refresh rate. 20 Hz is an experiment, not a proven device output capability.

**注意：** 20 Hz 是電腦向 LS129 發問的目標頻率，不表示探頭有 20 Hz 的新數據；短時段可能受到 RS485 往返延遲、Windows 排程與探頭更新週期影響。

## Installation / 安裝

1. Connect the LS129 to an appropriate external power supply. Switch the ATK-MO340P to **USB-485**; connect the differential RS485 A/B lines correctly.
2. Close **AccessPort** before launching the application; only one program can own the COM Port at a time.
3. Install Python 3.7 with Tcl/Tk, then run `python -m pip install -r requirements.txt` (PySerial 3.5).
4. Launch `python LS129_Monitor.py` or double-click `啟動_LS129.bat`.
5. Select COM, **physical probe type** (UVALED / UVA / UVC), Baud/Slave ID, and INT or FLOAT data mode. The choices are saved automatically to `settings.json`.
6. Select **4 Hz, 5 Hz or 20 Hz** while disconnected, then connect. Try **模擬** mode first if no hardware is available.
7. Press **開始量測**, vary illumination, then **結束並存檔**. Inspect **輪詢實驗 / 逐筆資料** and `Records/*.csv`.

## Persistent settings / 設定檔保存

- The first valid settings file is stored beside `LS129_Monitor.py` as **`settings.json`** for portable use. If the application directory is read-only, the fallback is `~/LS129_UV_Monitor/settings.json` (Windows user profile).
- Selecting **COM** or **探頭種類** saves immediately. Baud, Slave, INT/FLOAT and polling frequency are also retained. Manual COM/Slave text is saved on leaving the field, connecting or exiting.
- On next launch, the last chosen COM and probe are restored even if that COM is **temporarily absent**. The application will *not silently substitute another port* when a saved port is missing.
- `settings.json` is **excluded from GitHub** by `.gitignore`; each PC maintains its own preferences.
- **Software EIT correction is disabled on startup**, not auto-restored. No calibration coefficient is written into LS129. Smoothing 0/50/60 Hz is a **device setting**, read from the device after connection, not restored from PC configuration.

Example / 範例（本檔由程式自動產生，無需自行建立）:

```json
{
  "baud_rate": "9600",
  "com_port": "COM5",
  "data_mode": "FLOAT",
  "poll_hz": 20,
  "probe_type": "UVALED",
  "slave_id": "1"
}
```

## CSV output / 資料儲存

Press **結束並存檔** to create a UTF-8 BOM CSV in `Records/`. Notable fields:

- `send_timestamp`, `receive_timestamp`: wall-clock timestamps, millisecond display precision
- `elapsed_s`, `rx_gap_ms`, `round_trip_ms`: monotonic elapsed time, successful reply interval, and serial round-trip latency
- `target_poll_hz`: chosen 4 / 5 / 20 Hz, **not** a claim of actual 20 Hz sensor updates
- `poll_sequence`, `attempt_index`, `status`, `error`, `source`: attempt numbering, error and periodic/final read
- `duplicate_previous`, `consecutive_run`: **byte-for-byte comparison of valid Modbus responses**, excluding transport timing; a failed poll breaks the run
- `power_raw`, `peak_raw`, `energy_raw`: exact decoded numbers without display rounding
- `power_pc`, `peak_pc`, `energy_pc`, `pc_factor`: software-only correction, recorded separately
- `request_hex`, `response_hex`: full communication frames, CRC included
- `probe_type`, `data_mode`, `smoothing`, and other settings for traceability

Data under `Records/` and local `settings.json` are excluded from Git source control.

## What to look for in the 20 Hz experiment / 實驗判讀

If a sensor refreshes accessible registers near **5 Hz**, querying them at **20 Hz** is expected to return repeated values, *approximately* four reads per value. The intervals need not form groups of exactly four, because the PC's polling clock, device refresh and serial response timing are asynchronous. Identical data can also occur during steady illumination; non-identical data alone cannot prove a 20 Hz internal refresh. Compare timestamps, jitter, full HEX frames, and periods of actively changing UV irradiance.

假設 20 Hz 輪詢期間，LS129 真的是每 200 ms 才更新一次 Modbus 暫存器，那麼應有大量連續相同回覆，但**不一定恰好每四筆一組**。要從實測 CSV 判斷，不要只看畫出的曲線。

## Safety & limitations / 安全及限制

- Modbus writes: **register 50** on Start (reset LS129 peak/energy counters), **register 320** only when the user explicitly changes smoothing mode; register 320 write is followed by read-back verification.
- **Never writes the external calibration register**. EIT is software-only and OFF by default.
- Starting or stopping a PC recording does not stop physical sensing by LS129.
- Real LS129 FLOAT register support (101–106), unit scaling, and 20 Hz performance need on-site validation. **INT mode (201–204)** is the known AccessPort baseline; it reports integers, so `21.0` means *integer data rendered to one decimal*, not higher precision.
- Target: one attached probe. No automated triggering, formal calibration, historical database or PDF reports yet.
- This release does not contain actual factory measurement data.

## Self-test / 自我測試

```bash
python LS129_Monitor.py --self-test
```

Validates CRC16, provided INT and FLOAT example frame decoding, rounding, interval selection, duplicate classification, and settings file read/write using a temporary folder.

## Protocol reference / 原廠通訊協議

[LS129 Communication Protocol V3.2](https://images.linshangtech.com/user-manual/LS129_Communication_Protocol_V3.2.pdf)

No license has been chosen by the repository owner. / 授權條款尚待專案擁有者決定。
