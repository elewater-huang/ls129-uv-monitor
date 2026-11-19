@echo off
chcp 65001 >nul
cd /d "%~dp0"
python LS129_Monitor.py
if errorlevel 1 pause
