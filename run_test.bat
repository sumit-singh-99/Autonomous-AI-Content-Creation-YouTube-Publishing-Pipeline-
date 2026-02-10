@echo off
REM change to project directory
cd /d D:\MoneyPrinter\Main_YT_Automation

REM optional: create logs folder if missing
if not exist logs mkdir logs

REM enable UTF-8 mode for Python (to prevent UnicodeEncodeError)
set PYTHONUTF8=1

REM run python from the venv directly and append stdout/stderr to logfile
D:\MoneyPrinter\Main_YT_Automation\venv\Scripts\python.exe D:\MoneyPrinter\Main_YT_Automation\test.py >> logs\test.log 2>&1
