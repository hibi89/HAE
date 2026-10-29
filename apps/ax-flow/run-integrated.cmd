@echo off
setlocal
where python >nul 2>nul
if errorlevel 1 (
  echo [HAE] Python 3.11+ not found on PATH.
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-integrated.ps1" %*
exit /b %ERRORLEVEL%
