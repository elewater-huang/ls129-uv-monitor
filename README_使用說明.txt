LS129 UV Monitor v0.1.0 (2026-11-19)
=================================

定位：Windows 桌面程式第一版；LS128 介面概念 + LS129 即時 Modbus RTU。
平台：Python 3.7.9 32-bit + Tkinter + pyserial 3.5；Windows 7 32-bit。

[檔案]
LS129_Monitor.py       主程式（Python 3.7 可用）
啟動_LS129.bat         快速啟動
Records\               測試結束後自動產生（UTF-8 BOM CSV，Excel 可開啟）

[安裝]
1. Python 3.7 安裝時必須有 tkinter / Tcl-Tk。
   檢查：python -m tkinter
2. 在命令列安裝串列埠套件：
   python -m pip install pyserial==3.5
   如公司電腦禁止安裝，將套件安裝到 portable Python 的套件目錄。
3. 執行「啟動_LS129.bat」，或 python LS129_Monitor.py。
4. 不接 LS129 時，可先勾「模擬模式」檢查介面，無需 pyserial。

[硬體與接線]
- ATK-MO340P 設 USB-RS485 模式，接上 LS129 的 RS485+/-；外部電源為 LS129 供電。
- 確認只有一支程式占用 COM；先關閉 AccessPort 1.37。
- 原廠預設：9600 baud, 8N1, station 1（依實際設備設定）

[操作]
1. 選 COM、9600、站號 1，按「連線」。
2. 在右側選擇探頭版本 UVALED/UVA/UVC（確定物理單位）。
3. 資料模式初始 INT (201–204)，這是已實測的格式。
   可用 FLOAT (101–106) 測試是否保留小數，切換前請斷線。
4. 待機時一直讀即時數值，未記錄正式 CSV。
5. 按「開始量測」會發送 06H 寫 Register 50=1，重置探頭最大功率及累積能量，
   等到設備回覆才開始 PC 記錄。
6. 按「結束並存檔」會再讀一次數值，停止 PC 記錄，並自動輸出 Records/*.csv。
   *注意：不會停止 LS129 的感測，也不會清除當前探頭數據。*
7. 設定頁中可讀取與修改平滑模式（Register 320，改後讀回驗證）。
8. 設定頁中 EIT PC 修正預設 OFF；只修正顯示值與 CSV 的 *_pc 欄位，
   *_raw 及 response_hex 永遠保存 LS129 原始值。不修改探頭內部校正。

[安全設計]
- 本版僅會寫入 Register 50（操作員開始量測）及 Register 320（確認後修改平滑）。
- 不讀／不寫 Register 350（保留給後續驗證），也不寫通訊 ID、鮑率。
- 結束時保留數據 CSV；通信失敗或停止時不捏造樣本。
- CRC16、站號、功能碼及讀寫回覆驗證。

[目前限制]
- 只支援單一探頭、單一連線；CSV 歷史檢索和 PDF 報表未開發。
- 量測曲線是 PC 讀取到的樣本，非 LS129 內部 2048 Hz 原始取樣。
- 定時輪詢目標 250 ms，實際頻率受 USB/RS485/Windows 延遲影響。
- 未連接實際 LS129 測試本版程式；先在現場確認連線及資料。
- 部分 LS129 版本的單位、讀取解析，請依實際探頭型號驗證。
- 暫不提供自動觸發與多探頭功能。
- 正式版前請加入工控現場持續運行測試、例外狀態測試、記錄驗證。

[自動化自我測試]
python LS129_Monitor.py --self-test
預期：SELF TEST OK ...

原廠參考：
https://images.linshangtech.com/user-manual/LS129_Communication_Protocol_V3.2.pdf
