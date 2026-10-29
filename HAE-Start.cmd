@echo off
setlocal
cd /d "%~dp0"
set "HAE_ENTRY=%~dp0apps\ax-flow\start_hae.py"
if not exist "%HAE_ENTRY%" (
  echo HAE startup dispatcher is missing. No workflow was executed.
  set "HAE_EXIT=2"
  goto failed
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import sys;raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
  if not errorlevel 1 goto use_py
)
where python >nul 2>&1
if not errorlevel 1 (
  python -c "import sys;raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
  if not errorlevel 1 goto use_python
)
echo HAE needs Python 3.11 or newer.
set "HAE_EXIT=2"
goto failed

:use_py
py -3 "%HAE_ENTRY%"
set "HAE_EXIT=%errorlevel%"
goto finished

:use_python
python "%HAE_ENTRY%"
set "HAE_EXIT=%errorlevel%"
goto finished

:finished
if "%HAE_EXIT%"=="0" exit /b 0
echo HAE could not start. See the error above. No workflow was executed.

:failed
pause
exit /b %HAE_EXIT%
