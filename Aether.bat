@echo off
cd /d "%~dp0"
pythonw "%~dp0main.py" 2>nul
if errorlevel 1 python "%~dp0main.py"
