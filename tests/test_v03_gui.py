import os, sys, tempfile, shutil, pathlib, json, time, csv
import tkinter as tk
p=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as t:
    for file in ['LS129_Monitor.py','ls129_i18n.py']:
        shutil.copy(str(p/file),os.path.join(t,file))
    sys.path.insert(0,t)
    import LS129_Monitor as m
    r=tk.Tk(); app=m.MonitorApp(r)
    assert app.language_code == 'zh-TW'
    app.port_var.set('COM88')
    app.probe_var.set('UVALED')
    app.poll_rate_var.set('0.2')
    assert app.rate_changed()
    assert app._last_valid_hz==0.2
    assert app.smooth_choice.get().startswith('0 ')
    app.smooth_choice.set('2 - 60 Hz');app.smoothing_preference_changed()
    app.language_var.set('English');app.language_changed()
    assert app.tabs.tab(0,'text')=='Live monitor / Record',app.tabs.tab(0,'text')
    assert app.link_button.cget('text')=='Connect',app.link_button.cget('text')
    assert app.smooth_choice.get()=='2 - 60 Hz'
    app.save_preferences()
    assert json.load(open(os.path.join(t,'settings.json'),encoding='utf-8')) == {
      'baud_rate':'9600','com_port':'COM88','data_mode':'INT','language':'en','poll_hz':0.2,
      'probe_type':'UVALED','slave_id':'1','smoothing_mode':2}
    app.close();r.update()
    r=tk.Tk();app=m.MonitorApp(r)
    assert app.language_code=='en'
    assert app.language_var.get()=='English'
    assert app.poll_rate_var.get()=='0.2'
    assert app.smooth_choice.get()=='2 - 60 Hz'
    assert app.probe_var.get()=='UVALED'
    assert app.link_button.cget('text')=='Connect'
    app.language_var.set('简体中文');app.language_changed()
    assert app.language_code=='zh-CN'
    assert app.tabs.tab(0,'text')=='即时监测 / 测量', app.tabs.tab(0,'text')
    app.poll_rate_var.set('32');app.rate_changed()
    assert app._last_valid_hz==32.0
    assert m.fixed_poll_interval(.2)==5.0 and m.fixed_poll_interval(32)==.03125
    app.demo_var.set(True)
    app.connect()
    deadline=time.time()+2
    while not app.connected and time.time()<deadline:
        r.update();time.sleep(.015)
    assert app.connected, 'demo failed'
    app.start_measurement()
    deadline=time.time()+2
    while not app.recording and time.time()<deadline:
        r.update();time.sleep(.02)
    assert app.recording
    begin=time.time()
    while time.time()-begin<0.6:
        r.update();time.sleep(.01)
    app.stop_measurement()
    deadline=time.time()+3
    while (app.stop_pending or app.recording) and time.time()<deadline:
        r.update();time.sleep(.01)
    assert not app.recording
    records=list(pathlib.Path(t,'Records').glob('*.csv'))
    assert len(records)==1,records
    data=list(csv.DictReader(open(records[0],encoding='utf-8-sig')))
    assert data and all(float(row['target_poll_hz'])==32.0 for row in data)
    app.disconnect_force()
    r.update();app.close()
    r=tk.Tk();app=m.MonitorApp(r)
    assert app.language_code=='zh-CN'
    assert app.poll_rate_var.get()=='32'
    assert app.smooth_choice.get().startswith('0 '), 'demo sensor read updated PC smoothing preference 0 instead of 2'
    app.close()
print('V0.3 GUI PASS: locale toggle, preferences, .2/32 Hz, demo recording, CSV, relaunch')
