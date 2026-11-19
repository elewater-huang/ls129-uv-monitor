# -*- coding: utf-8 -*-
"""LS129 UV Monitor 0.1 - Windows 7 / Python 3.7 compatible.

Requires pyserial for real RS485 communication. Demo mode requires only tkinter.
Protocol reference: Linshang LS129 Communication Protocol V3.2.
This application never writes the LS129 external calibration register.
"""
from __future__ import print_function

import csv
import datetime as dt
import math
import os
import queue
import random
import struct
import sys
import threading
import time
from collections import deque

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    raise SystemExit('tkinter is required. Install a Python distribution with Tcl/Tk.')

VERSION = '0.1.0'
APP_DIR = os.path.dirname(os.path.abspath(__file__))
POLL_SECONDS = 0.25  # 200 ms is LS129's advertised data refresh, not a guaranteed PC rate.


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xA001) if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF


def frame(payload):
    return payload + struct.pack('<H', crc16_modbus(payload))


def as_hex(data):
    return ' '.join('{:02X}'.format(b) for b in data)


def validate_frame(data, slave, func):
    if len(data) < 5:
        raise ValueError('Response too short: {}'.format(as_hex(data)))
    if crc16_modbus(data[:-2]) != struct.unpack('<H', data[-2:])[0]:
        raise ValueError('CRC mismatch: {}'.format(as_hex(data)))
    if data[0] != slave:
        raise ValueError('Wrong slave: {}'.format(as_hex(data)))
    if data[1] == (func | 0x80):
        raise ValueError('Modbus exception code {}'.format(data[2]))
    if data[1] != func:
        raise ValueError('Unexpected function {}'.format(data[1]))
    return data


def parse_measurement(data, slave, mode):
    validate_frame(data, slave, 3)
    expected_count = 12 if mode == 'FLOAT' else 8
    if data[2] != expected_count or len(data) != expected_count + 5:
        raise ValueError('Unexpected measurement byte count: {}'.format(as_hex(data)))
    values = data[3:-2]
    if mode == 'FLOAT':
        power, peak, energy = struct.unpack('>fff', values)
        if not all(math.isfinite(v) for v in (power, peak, energy)):
            raise ValueError('Non-finite float from LS129')
    else:
        power, peak = struct.unpack('>HH', values[:4])
        energy = struct.unpack('>I', values[4:8])[0]
    return float(power), float(peak), float(energy)


def parse_register(data, slave):
    validate_frame(data, slave, 3)
    if len(data) != 7 or data[2] != 2:
        raise ValueError('Invalid single-register response')
    return struct.unpack('>H', data[3:5])[0]


def number(value):
    if value is None:
        return '--'
    return '{:,.3f}'.format(value).rstrip('0').rstrip('.') if abs(value) < 1000000 else '{:,.1f}'.format(value)


def unit_labels(probe):
    if probe == 'UVC':
        return ('µW/cm²', 'µJ/cm²')
    if probe in ('UVA', 'UVALED'):
        return ('mW/cm²', 'mJ/cm²')
    return ('未指定', '未指定')


class LinkWorker(threading.Thread):
    """Owns the serial port. GUI never touches the port directly."""
    def __init__(self, commands, events, stop_event, port, baud, slave, mode, demo):
        threading.Thread.__init__(self, daemon=True)
        self.commands = commands
        self.events = events
        self.stop_event = stop_event
        self.port = port
        self.baud = baud
        self.slave = slave
        self.mode = mode
        self.demo = demo
        self.serial_port = None
        self.smoothing = 0
        self.sim_t0 = time.monotonic()
        self.sim_peak = 0.0
        self.sim_energy = 0.0
        self.sim_last = self.sim_t0
        self.random = random.Random(129)
        self.failures = 0

    def emit(self, kind, **kwargs):
        self.events.put(dict(kind=kind, **kwargs))

    def exchange(self, payload, func, register_count=None):
        tx = frame(payload)
        self.serial_port.reset_input_buffer()
        self.serial_port.write(tx)
        self.serial_port.flush()
        header = self.serial_port.read(3)
        if len(header) != 3:
            raise IOError('No response / timeout')
        if header[1] == (func | 0x80):
            rest = self.serial_port.read(2)
        elif func == 3:
            wanted = register_count * 2
            if header[2] != wanted:
                raise IOError('Unexpected byte count {}'.format(header[2]))
            rest = self.serial_port.read(wanted + 2)
        else:
            # FC06 response 8 bytes total.
            rest = self.serial_port.read(5)
        rx = header + rest
        validate_frame(rx, self.slave, func)
        self.emit('exchange', tx=as_hex(tx), rx=as_hex(rx))
        return rx

    def read_one(self, address):
        if self.demo:
            return self.smoothing
        req = struct.pack('>BBHH', self.slave, 3, address, 1)
        return parse_register(self.exchange(req, 3, 1), self.slave)

    def write_one(self, address, value):
        if self.demo:
            if address == 320:
                self.smoothing = value
            elif address == 50:
                now = time.monotonic()
                self.sim_peak = 0.0
                self.sim_energy = 0.0
                self.sim_last = now
                self.sim_t0 = now
            return
        req = struct.pack('>BBHH', self.slave, 6, address, value)
        rx = self.exchange(req, 6)
        if rx[:-2] != req:
            raise ValueError('Write echo mismatch')

    def poll(self):
        if self.demo:
            now = time.monotonic()
            t = now - self.sim_t0
            # UV lamp appears in repeated exposures, for visual debugging only.
            active = (t % 19.0) > 3.0 and (t % 19.0) < 14.0
            power = max(0, 170 + 58 * math.sin(t * 1.6) + 7 * self.random.random()) if active else 0.0
            interval = max(0, now - self.sim_last)
            self.sim_last = now
            self.sim_peak = max(self.sim_peak, power)
            self.sim_energy += power * interval
            values = (power, self.sim_peak, self.sim_energy)
            return values, 'DEMO (not a real Modbus frame)'
        address, count = ((101, 6) if self.mode == 'FLOAT' else (201, 4))
        req = struct.pack('>BBHH', self.slave, 3, address, count)
        reply = self.exchange(req, 3, count)
        return parse_measurement(reply, self.slave, self.mode), as_hex(reply)

    def handle(self, command):
        name = command[0]
        try:
            if name == 'start':
                self.write_one(50, 1)  # Reset *device* peak/energy counter.
                self.emit('started')
            elif name == 'stop':
                # Capture one last reading, then stop *PC* recording only.
                try:
                    values, raw = self.poll()
                    self.emit('sample', values=values, raw=raw, timestamp=time.time())
                except Exception as exc:
                    self.emit('warning', message='Final read failed: {}'.format(exc))
                self.emit('stopped')
            elif name == 'read_smoothing':
                self.emit('smoothing', value=self.read_one(320))
            elif name == 'write_smoothing':
                selected = command[1]
                self.write_one(320, selected)
                verified = self.read_one(320)
                if verified != selected:
                    raise ValueError('Read-back does not match written value')
                self.emit('smoothing', value=verified)
                self.emit('notice', message='平滑模式寫入及讀回驗證成功')
        except Exception as exc:
            self.emit('operation_error', operation=name, message=str(exc))

    def run(self):
        try:
            if not self.demo:
                try:
                    import serial
                except ImportError:
                    raise RuntimeError('找不到 pyserial。請先執行 python -m pip install pyserial==3.5')
                self.serial_port = serial.Serial(self.port, self.baud, bytesize=8,
                                                 parity='N', stopbits=1,
                                                 timeout=0.7, write_timeout=0.7)
            self.emit('online', demo=self.demo)
            next_poll = time.monotonic()
            while not self.stop_event.is_set():
                try:
                    command = self.commands.get_nowait()
                    self.handle(command)
                except queue.Empty:
                    pass
                now = time.monotonic()
                if now >= next_poll:
                    try:
                        values, raw = self.poll()
                        self.failures = 0
                        self.emit('sample', values=values, raw=raw, timestamp=time.time())
                    except Exception as exc:
                        self.failures += 1
                        if self.failures in (1, 3) or self.failures % 10 == 0:
                            self.emit('warning', message='讀取失敗 ({})：{}'.format(self.failures, exc))
                    next_poll = time.monotonic() + POLL_SECONDS
                self.stop_event.wait(0.025)
        except Exception as exc:
            self.emit('fatal', message=str(exc))
        finally:
            if self.serial_port:
                try:
                    self.serial_port.close()
                except Exception:
                    pass
            self.emit('offline')


class MonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title('LS129 UV Monitor - v{}'.format(VERSION))
        self.root.geometry('1120x770')
        self.root.minsize(900, 630)
        self.commands = queue.Queue()
        self.events = queue.Queue()
        self.stop_event = None
        self.worker = None
        self.connected = False
        self.demo = False
        self.recording = False
        self.start_pending = False
        self.stop_pending = False
        self.start_ts = None
        self.samples = []
        self.live_samples = deque(maxlen=500)
        self.last_values = (None, None, None)
        self.measurement_id = ''
        self.record_factor = 1.0
        self.last_frame = ''
        self.draw_at = 0
        self.log_count = 0
        self.smoothing_value = None

        self.port_var = tk.StringVar(value='COM3')
        self.baud_var = tk.StringVar(value='9600')
        self.id_var = tk.StringVar(value='1')
        self.demo_var = tk.BooleanVar(value=False)
        self.mode_var = tk.StringVar(value='INT')
        self.probe_var = tk.StringVar(value='未指定')
        self.status_var = tk.StringVar(value='尚未連線')
        self.power_var = tk.StringVar(value='--')
        self.peak_var = tk.StringVar(value='--')
        self.energy_var = tk.StringVar(value='--')
        self.time_var = tk.StringVar(value='00:00.0')
        self.power_unit_var = tk.StringVar(value='未指定')
        self.energy_unit_var = tk.StringVar(value='未指定')
        self.smooth_var = tk.StringVar(value='讀取中 / 未讀取')
        self.factor_var = tk.StringVar(value='1.000')
        self.enable_factor_var = tk.BooleanVar(value=False)
        self.file_var = tk.StringVar(value='尚無記錄')
        self.msg_var = tk.StringVar(value='先選擇串列埠，或使用模擬模式檢查介面。')

        self.configure_style()
        self.build()
        self.update_units()
        self.refresh_ports()
        self.root.after(80, self.process_events)
        self.root.protocol('WM_DELETE_WINDOW', self.close)

    def configure_style(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
        style.configure('TFrame', background='#f5f7fa')
        style.configure('TLabel', background='#f5f7fa', foreground='#26334a', font=('Microsoft JhengHei UI', 10))
        style.configure('Caption.TLabel', background='#f5f7fa', foreground='#68768b', font=('Microsoft JhengHei UI', 9))
        style.configure('Headline.TLabel', background='#f5f7fa', foreground='#13253e', font=('Microsoft JhengHei UI', 18, 'bold'))
        style.configure('Big.TLabel', background='white', foreground='#12375a', font=('Arial', 28, 'bold'))
        style.configure('SmallCard.TLabel', background='white', foreground='#718096', font=('Microsoft JhengHei UI', 9))
        style.configure('TButton', padding=(10, 6))
        style.configure('Accent.TButton', padding=(12, 8), foreground='white', background='#1768a5')
        style.configure('TNotebook', background='#f5f7fa')
        style.configure('TNotebook.Tab', padding=(16, 9))

    def build(self):
        top = ttk.Frame(self.root, padding=(18, 12))
        top.pack(fill='x')
        ttk.Label(top, text='LS129 UV Monitor', style='Headline.TLabel').pack(side='left')
        ttk.Label(top, text='  v{} | Modbus RTU / RS485'.format(VERSION), style='Caption.TLabel').pack(side='left', pady=8)
        ttk.Label(top, textvariable=self.status_var).pack(side='right')
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        self.main = ttk.Frame(self.tabs, padding=12)
        self.settings = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.main, text='即時監測 / 量測')
        self.tabs.add(self.settings, text='設備與軟體設定')
        self.build_main()
        self.build_settings()
        self.state_buttons()
        footer = ttk.Frame(self.root, padding=(14, 3, 14, 10))
        footer.pack(fill='x')
        ttk.Label(footer, textvariable=self.msg_var, style='Caption.TLabel').pack(anchor='w')
        ttk.Label(footer, textvariable=self.file_var, style='Caption.TLabel').pack(anchor='w')

    def build_main(self):
        connector = ttk.LabelFrame(self.main, text='連線', padding=9)
        connector.pack(fill='x', pady=(0, 9))
        ttk.Label(connector, text='COM').pack(side='left')
        self.port_box = ttk.Combobox(connector, width=9, textvariable=self.port_var)
        self.port_box.pack(side='left', padx=(5, 9))
        ttk.Button(connector, text='更新', width=5, command=self.refresh_ports).pack(side='left')
        ttk.Label(connector, text='Baud').pack(side='left', padx=(13, 5))
        self.baud_box = ttk.Combobox(connector, width=8, state='readonly', textvariable=self.baud_var,
                                      values=['4800', '9600', '19200', '38400'])
        self.baud_box.pack(side='left')
        ttk.Label(connector, text='站號').pack(side='left', padx=(13, 5))
        self.id_box = ttk.Entry(connector, width=5, textvariable=self.id_var)
        self.id_box.pack(side='left')
        self.demo_checkbox = ttk.Checkbutton(connector, text='模擬', variable=self.demo_var)
        self.demo_checkbox.pack(side='left', padx=(6, 8))
        ttk.Label(connector, text='探頭').pack(side='left', padx=(5, 3))
        self.probe_box = ttk.Combobox(connector, textvariable=self.probe_var, state='readonly', width=7,
                                     values=['未指定', 'UVALED', 'UVA', 'UVC'])
        self.probe_box.pack(side='left')
        self.probe_box.bind('<<ComboboxSelected>>', self.update_units)
        ttk.Label(connector, text='資料').pack(side='left', padx=(10, 3))
        self.mode_box = ttk.Combobox(connector, textvariable=self.mode_var, state='readonly', width=6,
                                    values=['INT', 'FLOAT'])
        self.mode_box.pack(side='left')
        self.link_button = ttk.Button(connector, text='連線', style='Accent.TButton', command=self.toggle_link)
        self.link_button.pack(side='right')

        metrics = ttk.Frame(self.main)
        metrics.pack(fill='x', pady=(0, 9))
        for col in range(3):
            metrics.columnconfigure(col, weight=1, uniform='metric')
        self.metric(metrics, 0, '即時 UV 功率', self.power_var, self.power_unit_var)
        self.metric(metrics, 1, '最大 UV 功率', self.peak_var, self.power_unit_var)
        self.metric(metrics, 2, '累積 UV 能量', self.energy_var, self.energy_unit_var)

        lower = ttk.Frame(self.main)
        lower.pack(fill='both', expand=True)
        lower.columnconfigure(0, weight=4)
        lower.columnconfigure(1, weight=1)
        lower.rowconfigure(0, weight=1)
        graph_box = ttk.LabelFrame(lower, text='UV 功率曲線（電腦讀取資料）', padding=9)
        graph_box.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.plot = tk.Canvas(graph_box, bg='white', highlightthickness=0, width=650, height=235)
        self.plot.pack(fill='both', expand=True)
        self.plot.bind('<Configure>', lambda _: self.draw_graph())
        bottom = ttk.Frame(graph_box, padding=(2, 6))
        bottom.pack(fill='x')
        ttk.Label(bottom, text='測試時間', style='Caption.TLabel').pack(side='left')
        ttk.Label(bottom, textvariable=self.time_var).pack(side='left', padx=(8, 15))
        ttk.Label(bottom, text='目標輪詢 250 ms；實際時間以電腦收到資料為準', style='Caption.TLabel').pack(side='right')

        control = ttk.LabelFrame(lower, text='量測控制', padding=10)
        control.grid(row=0, column=1, sticky='nsew')
        self.start_button = ttk.Button(control, text='開始量測', style='Accent.TButton', command=self.start_measurement)
        self.start_button.pack(fill='x', pady=(3, 8))
        self.stop_button = ttk.Button(control, text='結束並存檔', command=self.stop_measurement)
        self.stop_button.pack(fill='x', pady=(0, 12))
        ttk.Separator(control).pack(fill='x', pady=10)
        ttk.Label(control, text='讀值格式：INT 201–204\n或 FLOAT 101–106',
                  style='Caption.TLabel', justify='left').pack(anchor='w', pady=(2, 10))
        ttk.Separator(control).pack(fill='x', pady=9)
        ttk.Label(control, text='平滑模式').pack(anchor='w')
        ttk.Label(control, textvariable=self.smooth_var).pack(anchor='w', pady=(5, 0))
        ttk.Label(control, text='在設定頁面讀取或修改', style='Caption.TLabel').pack(anchor='w')


    def metric(self, parent, column, label, value, unit):
        outer = ttk.Frame(parent)
        outer.grid(row=0, column=column, sticky='ew', padx=(0 if column == 0 else 4, 4 if column < 2 else 0))
        card = tk.Frame(outer, bg='white', highlightbackground='#dfe6ef', highlightthickness=1)
        card.pack(fill='both')
        tk.Label(card, text=label, bg='white', fg='#68768b', font=('Microsoft JhengHei UI', 10)).pack(pady=(15, 2))
        ttk.Label(card, textvariable=value, style='Big.TLabel').pack(pady=(2, 1))
        ttk.Label(card, textvariable=unit, style='SmallCard.TLabel').pack(pady=(0, 16))

    def build_settings(self):
        container = ttk.Frame(self.settings)
        container.pack(fill='both', expand=True)
        left = ttk.Frame(container)
        right = ttk.Frame(container)
        left.pack(side='left', fill='both', expand=True, padx=(0, 8))
        right.pack(side='left', fill='both', expand=True, padx=(8, 0))
        group = ttk.LabelFrame(left, text='LS129 探頭設定', padding=15)
        group.pack(fill='x')
        ttk.Label(group, text='通訊參數由主畫面指定；目前不提供修改探頭站號和 Baud Rate。',
                  wraplength=360).pack(anchor='w', pady=(0, 15))
        ttk.Label(group, text='光源頻率平滑模式（Register 320）').pack(anchor='w')
        self.smooth_choice = tk.StringVar(value='0 - 不平滑 / DC')
        self.smooth_box = ttk.Combobox(group, textvariable=self.smooth_choice, state='readonly',
                          values=['0 - 不平滑 / DC', '1 - 50 Hz', '2 - 60 Hz'])
        self.smooth_box.pack(fill='x', pady=(6, 8))
        smooth_buttons = ttk.Frame(group)
        smooth_buttons.pack(fill='x')
        self.read_smooth_button = ttk.Button(smooth_buttons, text='讀取目前設定', command=self.read_smoothing)
        self.read_smooth_button.pack(side='left')
        self.write_smooth_button = ttk.Button(smooth_buttons, text='套用並讀回驗證', command=self.write_smoothing)
        self.write_smooth_button.pack(side='right')
        ttk.Label(group, text='僅此操作會修改探頭平滑設定；其餘維持唯讀。', style='Caption.TLabel',
                  wraplength=350).pack(anchor='w', pady=(12, 0))
        ttk.LabelFrame(left, text='外部校正係數（保留給後續驗證）', padding=15).pack(fill='x', pady=(16, 0))
        ttk.Label(left, text='Register 350：本版不讀取、不寫入。', style='Caption.TLabel').pack(anchor='w', padx=15)

        cal = ttk.LabelFrame(right, text='EIT 對照 / 電腦軟體修正', padding=15)
        cal.pack(fill='x')
        self.factor_checkbox = ttk.Checkbutton(cal, text='啟用軟體修正（預設 OFF）',
                                                variable=self.enable_factor_var, command=self.factor_changed)
        self.factor_checkbox.pack(anchor='w', pady=(0, 12))
        ttk.Label(cal, text='修正倍率 K（數值修正 = LS129 原始值 × K）').pack(anchor='w')
        self.factor_entry = ttk.Entry(cal, textvariable=self.factor_var)
        self.factor_entry.pack(anchor='w', pady=(6, 9))
        ttk.Button(cal, text='驗證倍率設定', command=self.factor_changed).pack(anchor='w')
        ttk.Label(cal, text='原始值永遠保留在 CSV；倍率僅作用於 PC 顯示與衍生欄位，絕不寫入 LS129。',
                  style='Caption.TLabel', wraplength=360).pack(anchor='w', pady=(10, 0))
        ttk.Separator(right).pack(fill='x', pady=18)
        ttk.Label(right, text='記錄資料來源', style='Headline.TLabel').pack(anchor='w')
        ttk.Label(right, text='讀取 201–204：2×UINT16 + UINT32。\n讀取 101–106：3×IEEE754 FLOAT。\n量測開始才會寫 Register 50 重新計數。\n結束量測只停止 PC 儲存，不停止探頭。',
                  justify='left', wraplength=340).pack(anchor='w', pady=12)

    def refresh_ports(self):
        ports = []
        try:
            from serial.tools import list_ports
            ports = [p.device for p in list_ports.comports()]
        except ImportError:
            pass
        self.port_box['values'] = ports
        if ports and self.port_var.get() not in ports:
            self.port_var.set(ports[0])

    def check_factor(self):
        factor = float(self.factor_var.get())
        if not (0 < factor <= 100 and math.isfinite(factor)):
            raise ValueError('修正倍率必須在 0～100 之間（不含 0）')
        return factor

    def get_active_factor(self):
        return self.check_factor() if self.enable_factor_var.get() else 1.0

    def factor_changed(self):
        if self.recording or self.start_pending or self.stop_pending:
            self.enable_factor_var.set(self.record_factor != 1.0)
            self.msg_var.set('量測期間不能修改修正參數，請結束量測後再設定。')
            return
        try:
            factor = self.get_active_factor()
        except (ValueError, TypeError) as exc:
            messagebox.showerror('修正倍率不正確', str(exc))
            self.enable_factor_var.set(False)
            return
        self.msg_var.set('目前 PC 軟體修正 K = {:.4f}；未寫入探頭。'.format(factor))
        self.update_display()

    def toggle_link(self):
        if self.connected or self.worker is not None:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        try:
            slave = int(self.id_var.get())
            if not 1 <= slave <= 247:
                raise ValueError('站號須介於 1～247')
            baud = int(self.baud_var.get())
        except ValueError as exc:
            messagebox.showerror('通訊設定不正確', str(exc))
            return
        self.demo = self.demo_var.get()
        if not self.demo and not self.port_var.get().strip():
            messagebox.showerror('COM 未選擇', '請選擇 COM Port')
            return
        self.commands = queue.Queue()
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = LinkWorker(self.commands, self.events, self.stop_event,
                                 self.port_var.get(), baud, slave, self.mode_var.get(), self.demo)
        self.status_var.set('正在連線...')
        self.worker.start()
        self.state_buttons()

    def disconnect(self):
        if self.recording or self.stop_pending or self.start_pending:
            messagebox.showwarning('請先結束量測', '請先按「結束並存檔」，再斷線。')
            return
        self.disconnect_force()

    def disconnect_force(self):
        if self.stop_event:
            self.stop_event.set()
        self.connected = False
        self.worker = None
        self.stop_event = None
        self.status_var.set('尚未連線')
        self.state_buttons()

    def start_measurement(self):
        if not self.connected or self.recording or self.start_pending:
            return
        try:
            factor = self.get_active_factor()
        except (TypeError, ValueError) as exc:
            messagebox.showerror('設定錯誤', str(exc))
            return
        if self.probe_var.get() == '未指定':
            if not messagebox.askyesno('探頭未指定', '未選擇 UVA/UVALED/UVC，資料單位將記為未指定。繼續嗎？'):
                return
        self.record_factor = factor
        self.start_pending = True
        self.recording = False
        self.commands.put(('start',))
        self.msg_var.set('正在重設 LS129 的最大功率及累積能量計數...')
        self.state_buttons()

    def stop_measurement(self):
        if not self.recording or self.stop_pending:
            return
        self.stop_pending = True
        self.commands.put(('stop',))
        self.msg_var.set('正在取得最後讀值...')
        self.state_buttons()

    def read_smoothing(self):
        if self.connected:
            self.commands.put(('read_smoothing',))
        else:
            messagebox.showwarning('尚未連線', '請先連線。')

    def write_smoothing(self):
        if not self.connected:
            messagebox.showwarning('尚未連線', '請先連線。')
            return
        if self.recording or self.start_pending or self.stop_pending:
            messagebox.showwarning('量測進行中', '量測期間不可修改平滑設定。')
            return
        value = int(self.smooth_choice.get().split(' ')[0])
        if messagebox.askyesno('確認寫入 LS129', '確定將探頭的平滑模式改為 {}？\n寫入後將再讀回驗證。'.format(self.smooth_choice.get())):
            self.commands.put(('write_smoothing', value))

    def state_buttons(self):
        online = self.connected
        self.link_button.config(text='斷線' if online else '連線')
        self.start_button.config(state='normal' if online and not self.recording and not self.start_pending else 'disabled')
        self.stop_button.config(state='normal' if self.recording and not self.stop_pending else 'disabled')
        busy = self.recording or self.start_pending or self.stop_pending
        state = 'disabled' if online or self.worker is not None else 'normal'
        for widget in (self.port_box, self.baud_box, self.id_box, self.demo_checkbox, self.mode_box):
            widget.config(state=state)
        self.probe_box.config(state='disabled' if busy else 'readonly')
        self.factor_entry.config(state='disabled' if busy else 'normal')
        self.factor_checkbox.config(state='disabled' if busy else 'normal')
        self.smooth_box.config(state='disabled' if busy else 'readonly')
        self.write_smooth_button.config(state='disabled' if busy or not online else 'normal')
        self.read_smooth_button.config(state='disabled' if not online else 'normal')

    def update_units(self, event=None):
        pu, eu = unit_labels(self.probe_var.get())
        self.power_unit_var.set(pu)
        self.energy_unit_var.set(eu)
        self.update_display()

    def update_display(self):
        if self.recording or self.stop_pending:
            factor = self.record_factor
        else:
            try:
                factor = self.get_active_factor()
            except (ValueError, TypeError):
                factor = 1.0
        power, peak, energy = self.last_values
        self.power_var.set(number(power * factor) if power is not None else '--')
        self.peak_var.set(number(peak * factor) if peak is not None else '--')
        self.energy_var.set(number(energy * factor) if energy is not None else '--')

    def process_events(self):
        try:
            for _ in range(120):
                try:
                    event = self.events.get_nowait()
                except queue.Empty:
                    break
                kind = event['kind']
                if kind == 'online':
                    self.connected = True
                    self.status_var.set('模擬連線' if event['demo'] else '已連線：{} / {}'.format(self.port_var.get(), self.baud_var.get()))
                    self.msg_var.set('連線成功，持續監測中；尚未正式錄製。')
                    self.state_buttons()
                    self.commands.put(('read_smoothing',))
                elif kind == 'offline':
                    self.connected = False
                    if self.recording:
                        self.recording = False
                        self.save_record('連線中斷')
                    self.worker = None
                    self.stop_event = None
                    self.start_pending = False
                    self.stop_pending = False
                    self.status_var.set('未連線')
                    self.state_buttons()
                elif kind == 'sample':
                    self.on_sample(event)
                elif kind == 'started':
                    self.start_ts = time.time()
                    self.measurement_id = dt.datetime.now().strftime('LS129_%Y%m%d_%H%M%S')
                    self.samples = []
                    self.start_pending = False
                    self.stop_pending = False
                    self.recording = True
                    self.msg_var.set('錄製中，開始時已透過 Register 50 重新計數。')
                    self.state_buttons()
                elif kind == 'stopped':
                    self.recording = False
                    self.stop_pending = False
                    self.save_record('正常結束')
                    self.state_buttons()
                elif kind == 'smoothing':
                    value = event['value']
                    if value in (0, 1, 2):
                        self.smooth_var.set({0: 'OFF / DC', 1: '50 Hz', 2: '60 Hz'}[value])
                        self.smooth_choice.set(['0 - 不平滑 / DC', '1 - 50 Hz', '2 - 60 Hz'][value])
                    else:
                        self.smooth_var.set('未知值 {}'.format(value))
                elif kind in ('warning', 'notice', 'fatal'):
                    self.msg_var.set(event['message'])
                    if kind == 'fatal':
                        messagebox.showerror('LS129 連線失敗', event['message'])
                elif kind == 'operation_error':
                    self.msg_var.set('操作失敗：{}'.format(event['message']))
                    if event['operation'] == 'start':
                        self.start_pending = False
                    if event['operation'] == 'stop':
                        self.stop_pending = False
                        self.recording = False
                        self.save_record('最後讀值失敗')
                    self.state_buttons()
                    messagebox.showerror('Modbus 操作失敗', event['message'])
                elif kind == 'exchange':
                    self.last_frame = event['rx']
        finally:
            if self.recording and self.start_ts:
                t = time.time() - self.start_ts
                self.time_var.set('{:02d}:{:04.1f}'.format(int(t // 60), t % 60))
            now = time.monotonic()
            if now - self.draw_at > 0.25:
                self.draw_graph()
                self.draw_at = now
            self.root.after(80, self.process_events)

    def on_sample(self, event):
        power, peak, energy = event['values']
        self.last_values = (power, peak, energy)
        if self.recording:
            row = {'ts': event['timestamp'], 'elapsed': max(0, event['timestamp'] - self.start_ts),
                   'power': power, 'peak': peak, 'energy': energy, 'raw': event['raw']}
            self.samples.append(row)
        self.live_samples.append((event['timestamp'], power))
        self.update_display()

    def draw_graph(self):
        canvas = self.plot
        if not canvas.winfo_exists():
            return
        width = max(100, canvas.winfo_width())
        height = max(100, canvas.winfo_height())
        canvas.delete('all')
        l, t, r, b = 55, 24, width - 18, height - 34
        canvas.create_rectangle(l, t, r, b, outline='#d5dce7')
        data = ([(s['elapsed'], s['power']) for s in self.samples]
                if (self.recording or self.stop_pending or self.samples) else
                [(stamp - self.live_samples[0][0], p) for stamp, p in self.live_samples] if self.live_samples else [])
        if not data:
            canvas.create_text((l + r) / 2, (t + b) / 2, text='等待即時量測數據...', fill='#8d98a8', font=('Arial', 12))
            return
        max_x = max(12.0, data[-1][0])
        min_x = max(0.0, max_x - 120.0)
        visible = [(x, y) for x, y in data if x >= min_x]
        max_y = max(1.0, max(y for _, y in visible) * 1.15)
        for i in range(5):
            yy = b - (b - t) * i / 4.0
            canvas.create_line(l, yy, r, yy, fill='#edf1f6')
            canvas.create_text(l - 8, yy, text=number(max_y * i / 4.0), anchor='e', fill='#718096', font=('Arial', 9))
        for i in range(5):
            xx = l + (r - l) * i / 4.0
            canvas.create_line(xx, t, xx, b, fill='#f0f3f8')
            canvas.create_text(xx, b + 17, text='{:.0f}s'.format(min_x + (max_x - min_x) * i / 4.0),
                               fill='#718096', font=('Arial', 9))
        if visible:
            coords = []
            for x, y in visible:
                px = l + (x - min_x) / (max_x - min_x) * (r - l)
                py = b - y / max_y * (b - t)
                coords.extend((px, py))
            if len(coords) >= 4:
                canvas.create_line(*coords, fill='#087bad', width=2, smooth=False)
            else:
                x, y = coords
                canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill='#087bad', outline='')
        canvas.create_text(l + 8, t + 8, anchor='nw', text='Raw LS129 (未修正)', fill='#087bad', font=('Arial', 10))

    def save_record(self, reason):
        if not self.samples:
            self.msg_var.set('未取得有效樣本，沒有建立檔案。')
            return
        folder = os.path.join(APP_DIR, 'Records')
        try:
            if not os.path.exists(folder):
                os.makedirs(folder)
        except OSError:
            folder = os.path.join(os.path.expanduser('~'), 'LS129_Records')
            if not os.path.exists(folder):
                os.makedirs(folder)
        path = os.path.join(folder, self.measurement_id + '.csv')
        power_unit, energy_unit = unit_labels(self.probe_var.get())
        columns = ['measurement_id', 'timestamp', 'elapsed_s', 'power_raw', 'peak_raw', 'energy_raw',
                   'power_pc', 'peak_pc', 'energy_pc', 'pc_factor', 'power_unit', 'energy_unit',
                   'probe_type', 'data_mode', 'slave_id', 'baud_rate', 'smoothing', 'end_reason', 'response_hex']
        try:
            with open(path, 'w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                for sample in self.samples:
                    ts = dt.datetime.fromtimestamp(sample['ts']).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    factor = self.record_factor
                    writer.writerow(dict(measurement_id=self.measurement_id, timestamp=ts,
                        elapsed_s='{:.3f}'.format(sample['elapsed']), power_raw=sample['power'],
                        peak_raw=sample['peak'], energy_raw=sample['energy'],
                        power_pc=sample['power'] * factor, peak_pc=sample['peak'] * factor,
                        energy_pc=sample['energy'] * factor, pc_factor=factor,
                        power_unit=power_unit, energy_unit=energy_unit, probe_type=self.probe_var.get(),
                        data_mode=self.mode_var.get(), slave_id=self.id_var.get(), baud_rate=self.baud_var.get(),
                        smoothing=self.smooth_var.get(), end_reason=reason, response_hex=sample['raw']))
            self.file_var.set(path)
            self.msg_var.set('已儲存 {} 筆資料：{}'.format(len(self.samples), path))
        except Exception as exc:
            self.msg_var.set('無法儲存：{}'.format(exc))
            messagebox.showerror('存檔失敗', str(exc))

    def close(self):
        if self.recording:
            if not messagebox.askyesno('結束程式', '正在量測，關閉時會先儲存已取得的數據。確定嗎？'):
                return
            self.recording = False
            self.save_record('程式關閉')
        if self.stop_event:
            self.stop_event.set()
        self.root.destroy()


def self_test():
    req = frame(bytes.fromhex('01 03 00 C9 00 04'))
    assert as_hex(req) == '01 03 00 C9 00 04 94 37'
    rx1 = bytes.fromhex('01 03 08 00 15 00 1D 00 00 0A AB 7A 0B')
    assert parse_measurement(rx1, 1, 'INT') == (21.0, 29.0, 2731.0)
    rx2 = bytes.fromhex('01 03 02 00 00 B8 44')
    assert parse_register(rx2, 1) == 0
    rx3 = bytes.fromhex('01 03 0C 42 12 80 22 42 2B 42 36 43 05 E9 6D E1 8C')
    f1, f2, f3 = parse_measurement(rx3, 1, 'FLOAT')
    assert abs(f1 - 36.625) < 0.1 and abs(f2 - 42.814) < 0.1 and abs(f3 - 133.91) < 0.1
    assert as_hex(frame(bytes.fromhex('01 06 00 32 00 01'))) == '01 06 00 32 00 01 E9 C5'
    print('SELF TEST OK: CRC16, INT/FLOAT decode, register 320, recount command')


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        self_test()
    else:
        root = tk.Tk()
        app = MonitorApp(root)
        root.mainloop()
