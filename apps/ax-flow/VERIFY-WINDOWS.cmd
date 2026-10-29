@echo off
setlocal
rem Native Windows 64-bit HAE+LA release check.
rem Checks packaged HTTP/SQLite/approval/audit and three real NTFS gates.
py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto USE_PY
python -c "import sys;sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto USE_PYTHON
echo [HAE] Python 3.11+ is required for native Windows verification.
set "STATUS=1"
goto FINISH

:USE_PY
py -3 "%~dp0windows_offline_acceptance.py"
set "STATUS=%errorlevel%"
goto FINISH

:USE_PYTHON
python "%~dp0windows_offline_acceptance.py"
set "STATUS=%errorlevel%"

:FINISH
echo.
if "%STATUS%"=="0" (
  echo [HAE] NATIVE WINDOWS ACCEPTANCE: PASS
) else (
  echo [HAE] NATIVE WINDOWS ACCEPTANCE: NOT VERIFIED OR FAILED
)
if /I not "%~1"=="--no-pause" pause
exit /b %STATUS%
