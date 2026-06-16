@echo off
REM Open the local web UI (served by Python inside WSL) in your browser.
REM Keep this window open while using it; close it to stop the server.
setlocal
pushd "%~dp0"
start "" http://localhost:8753
wsl -e bash -lc "cd \"$(wslpath '%CD%')\" && python3 -m poe2cn serve"
popd
pause
