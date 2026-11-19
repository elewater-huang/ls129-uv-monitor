# LS129 UV Monitor — 简体中文说明

**[繁体中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [English](README.en.md)**

## 专案介绍

林上 LS129 无荧幕 UV 感测器，使用正点原子 ATK-MO340P USB–RS485 模组与电脑以 Modbus RTU 通讯。本程序透过 Tkinter 提供即时功率、最大功率、累积能量、曲线与 CSV 原始数据保存功能。目标系统是 Windows 7 32-bit、Python 3.7.9。

## v0.3.0 主要变更

- **介面三种语言**：繁体中文、简体中文、英文，画面右上方可立即切换。
- **语言设置自动保存**：`settings.json` 的 `language` 栏位为 `zh-TW`、`zh-CN` 或 `en`。重启自动还原。
- **手动轮询频率**：输入任何大于 0、最多 32 Hz 的数值，可用小数如 `0.2`、`2.5`、`31.5`、`32`；只控制 PC 轮询，不更动 LS129 的 ADC 取样率。
- **平滑模式保存**：0（OFF/DC）、1（50 Hz）、2（60 Hz），保存到 `smoothing_mode`。这是本机偏好设置，程序不会在连线时自动写入探头；连线后会读取探头真正的平滑模式，并更新画面/设置档。
- **COM、探头种类、Baud Rate、站号、INT/FLOAT** 与轮询频率持续自动保存。
- **保留 v0.2** 的小数第一位显示、逐笔 HEX 封包、收发时间戳、连续重复值侦测、测量 CSV 与模拟模式。

## 安装与启动

1. LS129 使用独立且符合规格的供电，ATK-MO340P 设置为 USB-485，正确连接 RS485 A/B。
2. 关闭 AccessPort，避免两个程序同时占用 COM 埠。
3. 安装具备 Tcl/Tk 的 Python 3.7.9，执行 `python -m pip install -r requirements.txt`（PySerial 3.5）。
4. 执行 `python LS129_Monitor.py`，或双击 `启动_LS129.bat`。
5. 在主画面选择 COM、探头种类与轮询频率；输入频率后按 Enter 或移开光标，即存入设置档。更动轮询频率需重新连线才会生效。
6. 「开始测量」会写入 Register 50 重置探头最大功率与累积能量统计；「结束并存档」在 `Records/` 输出 CSV。

## 设置档及语言保存

第一次修改设置时自动建立 `settings.json`。若程序所在目录无写入权限，使用用户目录 `~/LS129_UV_Monitor/settings.json`。此档列入 `.gitignore`，不会上传 GitHub。

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

`poll_hz: 0.2` 代表每 5 秒发送一次 Modbus 查询；`32` 代表目标间隔 31.25 ms。实际速度仍受串列传输时间、设备回应时间与 Windows 排程限制。

**重要区分：** `smoothing_mode` 是本机记住的偏好值，并非「下次连线自动写入」。只有用户在「设备与软件设置」选择「套用并读回验证」，才会使用 Modbus 06 写入 Register 320。为避免意外变更校正值，外部 EIT 校正暂存器完全不写入。

## CSV 与数据判读

每次记录包含原始功率、最大功率、累积能量、软件修正数值、送出/接收时间戳、往返时间、连续相同封包计数及完整 CRC 封包。`target_poll_hz` 保存当次使用的轮询频率，**不是**探头内部 ADC 的取样率。

Modbus RTU 采 Master 问／Slave 答，没有在原厂公开协议中确认 LS129 的连续推送（streaming）功能。Buffer 可以避免 UI 绘图拖慢接收，但不能取代设备对每次读取命令的回覆。

## 自我测试

`python LS129_Monitor.py --self-test` 验证 CRC、封包解析、显示四舍五入、小数轮询频率与设置档读写。三语 GUI／重启与模拟记录另有 `tests/test_v03_gui.py` 可用 `xvfb-run` 在 Linux 执行。真正 32 Hz 通讯稳定性需要再以 LS129 实机确认。

原厂通讯协议：[LS129 Communication Protocol V3.2](https://images.linshangtech.com/user-manual/LS129_Communication_Protocol_V3.2.pdf)。
