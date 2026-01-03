@echo off
echo Starting MediMind AI Backend...
cd /d "%~dp0"
call "..\..\.venv\Scripts\activate.bat"
python -B main.py
pause
