@echo off
setlocal
rem One-click native Windows check from the HAE source checkout.
rem Uses already-checked-in HAE+LA .pyz; no LA branch checkout, pip or Git.
set "BUNDLE=%TEMP%\HAE-acceptance-%RANDOM%-%RANDOM%"
pushd "%~dp0..\.." || exit /b 1

py -3 -c "import sys;sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto USE_PY
python -c "import sys;sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not errorlevel 1 goto USE_PYTHON
echo [HAE] Python 3.11 or newer is required.
set "STATUS=1"
goto AFTER_REPACK

:USE_PY
py -3 tools\repack_hae_windows_release.py --output-dir "%BUNDLE%"
set "STATUS=%errorlevel%"
goto AFTER_REPACK

:USE_PYTHON
python tools\repack_hae_windows_release.py --output-dir "%BUNDLE%"
set "STATUS=%errorlevel%"

:AFTER_REPACK
popd
if not "%STATUS%"=="0" goto DONE
call "%BUNDLE%\VERIFY-WINDOWS.cmd" --no-pause
set "STATUS=%errorlevel%"

:DONE
echo.
if "%STATUS%"=="0" (
  echo [HAE] Native Windows release verification PASS.
) else (
  echo [HAE] Native Windows release verification NOT PASSED.
)
pause
exit /b %STATUS%
