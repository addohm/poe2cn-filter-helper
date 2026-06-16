@echo off
REM MAINTAINER ONLY: re-extract the 国服 item database after a game patch, then reconvert.
REM Needs the bundled Node (maintainer\node) + the game installed. End users don't run this.
setlocal
pushd "%~dp0"
wsl -e bash -lc "cd \"$(wslpath '%CD%')\" && python3 -m poe2cn datamine && python3 -m poe2cn convert"
popd
echo.
pause
