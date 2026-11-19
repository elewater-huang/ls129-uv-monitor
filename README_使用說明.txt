LS129 UV Monitor v0.2.0（2026-11-19）
===================================
用途：Windows 7 32-bit / Python 3.7.9 / Tkinter / pyserial 3.5。
LS129 + ATK-MO340P USB-RS485，電腦即時顯示與記錄 Modbus 數值。

本版新增
---------
1. 即時功率／最大功率／累積能量，在畫面上顯示小數第一位（四捨五入）。
   原始 CSV 不會被四捨五入。INT 讀值本質上仍是整數，FLOAT 需實機驗證。
2. 可切換 4、5、20 Hz「電腦輪詢頻率」，需斷線後切換並重新連線。
3. 「輪詢實驗 / 逐筆資料」頁記錄每筆 Modbus 回覆是否與上一筆相同。
4. CSV 另外保存傳送/接收時間戳、往返時間、完整 HEX 和失敗次數。
5. COM、探頭種類、Baud、站號、INT/FLOAT、輪詢頻率會自動儲存在設定檔。

安裝與操作
----------
1. LS129 外接適當電源；ATK-MO340P 設為 USB-485 模式，連線時先關閉 AccessPort。
2. 安裝：python -m pip install pyserial==3.5
3. 啟動：python LS129_Monitor.py（或雙擊 啟動_LS129.bat）
4. 選擇 COM Port、實際探頭類別（UVA/UVALED/UVC）、9600/8N1、站號、INT 或 FLOAT。
5. 選 4、5 或 20 Hz，再按「連線」；可先勾選「模擬」在沒有探頭時測試。
6. 按「開始量測」，持續調整照度，完成後按「結束並存檔」。
7. 到「輪詢實驗 / 逐筆資料」查看資料，或打開 Records/*.csv 詳細分析。

設定檔
------
選好 COM 和探頭類別即儲存設定。手動輸入 COM/站號後離開欄位時儲存。
預設在主程式旁的 settings.json，目錄無法寫入時改存使用者
家目錄下的 LS129_UV_Monitor/settings.json。
下次啟動自動還原，若原 COM 未插入，也不自動改選其他 COM。
settings.json 已加入 .gitignore，避免個人設備設定上傳 GitHub。
EIT 修正每次啟動都預設關閉，不寫入 LS129 探頭。

20 Hz 實驗注意
-------------
20 Hz 是電腦每 50 ms 發送一次 Modbus 查詢的目標，不保證實際收得到 20 Hz。
如果 LS129 每 200 ms 才更新一次回覆，會出現約四筆相同回覆，
但因為軟體與探頭沒有同步，加上串口時間抖動，不會嚴格每四筆一組。
固定照度也可能連續相同；資料一直不同亦不代表一定有 20 Hz 探頭更新。
同時檢查 CSV 的 send_timestamp、receive_timestamp、round_trip_ms、
rx_gap_ms、response_hex、duplicate_previous 和 consecutive_run。

安全
----
程式只在開始量測時寫 Register 50 重置峰值/累積能量；
平滑模式 Register 320 需使用者確認後寫入，並讀回驗證。
不寫 LS129 外部校正係數；軟體 EIT 修正預設停用。

自我測試：python LS129_Monitor.py --self-test
本版未經實體 LS129 完整端到端測試，實機輪詢速度與資料單位請現場確認。
