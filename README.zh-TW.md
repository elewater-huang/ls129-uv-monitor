# LS129 UV Monitor — 繁體中文說明

**[繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [English](README.en.md)**

## 專案介紹

林上 LS129 無螢幕 UV 感測器，使用正點原子 ATK-MO340P USB–RS485 模組與電腦以 Modbus RTU 通訊。本程式透過 Tkinter 提供即時功率、最大功率、累積能量、曲線與 CSV 原始資料保存功能。目標系統是 Windows 7 32-bit、Python 3.7.9。

## v0.3.0 主要變更

- **介面三種語言**：繁體中文、簡體中文、英文，畫面右上方可立即切換。
- **語言設定自動保存**：`settings.json` 的 `language` 欄位為 `zh-TW`、`zh-CN` 或 `en`。重啟自動還原。
- **手動輪詢頻率**：輸入任何大於 0、最多 32 Hz 的數值，可用小數如 `0.2`、`2.5`、`31.5`、`32`；只控制 PC 輪詢，不更動 LS129 的 ADC 取樣率。
- **平滑模式保存**：0（OFF/DC）、1（50 Hz）、2（60 Hz），保存到 `smoothing_mode`。這是本機偏好設定，程式不會在連線時自動寫入探頭；連線後會讀取探頭真正的平滑模式，並更新畫面/設定檔。
- **COM、探頭種類、Baud Rate、站號、INT/FLOAT** 與輪詢頻率持續自動保存。
- **保留 v0.2** 的小數第一位顯示、逐筆 HEX 封包、收發時間戳、連續重複值偵測、測量 CSV 與模擬模式。

## 安裝與啟動

1. LS129 使用獨立且符合規格的供電，ATK-MO340P 設置為 USB-485，正確連接 RS485 A/B。
2. 關閉 AccessPort，避免兩個程式同時佔用 COM 埠。
3. 安裝具備 Tcl/Tk 的 Python 3.7.9，執行 `python -m pip install -r requirements.txt`（PySerial 3.5）。
4. 執行 `python LS129_Monitor.py`，或雙擊 `啟動_LS129.bat`。
5. 在主畫面選擇 COM、探頭種類與輪詢頻率；輸入頻率後按 Enter 或移開游標，即存入設定檔。更動輪詢頻率需重新連線才會生效。
6. 「開始量測」會寫入 Register 50 重置探頭最大功率與累積能量統計；「結束並存檔」在 `Records/` 輸出 CSV。

## 設定檔及語言保存

第一次修改設定時自動建立 `settings.json`。若程式所在目錄無寫入權限，使用使用者目錄 `~/LS129_UV_Monitor/settings.json`。此檔列入 `.gitignore`，不會上傳 GitHub。

```json
{
  "baud_rate": "9600",
  "com_port": "COM5",
  "data_mode": "INT",
  "language": "zh-TW",
  "poll_hz": 0.2,
  "probe_type": "UVALED",
  "slave_id": "1",
  "smoothing_mode": 2
}
```

`poll_hz: 0.2` 代表每 5 秒發送一次 Modbus 查詢；`32` 代表目標間隔 31.25 ms。實際速度仍受串列傳輸時間、設備回應時間與 Windows 排程限制。

**重要區分：** `smoothing_mode` 是本機記住的偏好值，並非「下次連線自動寫入」。只有使用者在「設備與軟體設定」選擇「套用並讀回驗證」，才會使用 Modbus 06 寫入 Register 320。為避免意外變更校正值，外部 EIT 校正暫存器完全不寫入。

## CSV 與資料判讀

每次記錄包含原始功率、最大功率、累積能量、軟體修正數值、送出/接收時間戳、往返時間、連續相同封包計數及完整 CRC 封包。`target_poll_hz` 保存當次使用的輪詢頻率，**不是**探頭內部 ADC 的取樣率。

Modbus RTU 採 Master 問／Slave 答，沒有在原廠公開協議中確認 LS129 的連續推送（streaming）功能。Buffer 可以避免 UI 繪圖拖慢接收，但不能取代設備對每次讀取命令的回覆。

## 自我測試

`python LS129_Monitor.py --self-test` 驗證 CRC、封包解析、顯示四捨五入、小數輪詢頻率與設定檔讀寫。三語 GUI／重啟與模擬記錄另有 `tests/test_v03_gui.py` 可用 `xvfb-run` 在 Linux 執行。真正 32 Hz 通訊穩定性需要再以 LS129 實機確認。

原廠通訊協議：[LS129 Communication Protocol V3.2](https://images.linshangtech.com/user-manual/LS129_Communication_Protocol_V3.2.pdf)。
