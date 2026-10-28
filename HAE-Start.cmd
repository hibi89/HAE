@echo off
setlocal
cd /d "%~dp0"
if defined PYTHONPATH (
  set "PYTHONPATH=%~dp0apps\ax-flow;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%~dp0apps\ax-flow"
)

where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if errorlevel 1 goto missing_python
goto use_python

:use_py
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto use_python
set "HAE_LAUNCH_ARGS="
if /I "%HAE_NO_BROWSER%"=="1" set "HAE_LAUNCH_ARGS=--no-browser"
py -3 -m axflow.desktop_launcher %HAE_LAUNCH_ARGS%
goto finished

:use_python
where python >nul 2>&1
if errorlevel 1 goto missing_python
python -c "import sys; raise SystemExit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto missing_python
set "HAE_LAUNCH_ARGS="
if /I "%HAE_NO_BROWSER%"=="1" set "HAE_LAUNCH_ARGS=--no-browser"
python -m axflow.desktop_launcher %HAE_LAUNCH_ARGS%
goto finished

:missing_python
echo HAE needs Python 3.11 or newer. Install Python and run HAE-Start.cmd again.
set "HAE_EXIT=2"
goto failed

:finished
set "HAE_EXIT=%ERRORLEVEL%"
if "%HAE_EXIT%"=="0" exit /b 0
echo HAE could not start. See the message above; no workflow was executed.

:failed
pause
exit /b %HAE_EXIT%
