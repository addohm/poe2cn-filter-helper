@echo off
REM Convert every filter in filters\input -> filters\output (and copy to the game folder).
REM Runs the Python tool inside WSL. Just double-click after dropping in new filters.
setlocal
pushd "%~dp0"
wsl -e bash -lc "cd \"$(wslpath '%CD%')\" && python3 -m poe2cn convert"
popd
echo.
pause
