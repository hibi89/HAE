@echo off
setlocal
rem Offline HAE + Lightning Azent synthetic MVP.
rem Requires Python 3.11+; no Git, pip or network needed at runtime.
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto RUN_PY
python -c "import sys;sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto RUN_PYTHON
echo [HAE] Python 3.11 or newer is required. Install Python and try again.
exit /b 1

:RUN_PY
py -3 "%~dp0launch_integrated.py" %*
exit /b %errorlevel%

:RUN_PYTHON
python "%~dp0launch_integrated.py" %*
exit /b %errorlevel%
