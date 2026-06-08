@echo off
REM ============================================================
REM  ALFRED kiosk launcher (Chrome only)
REM  Opens Chrome fullscreen (no tab/title/omnibox/bookmark bar,
REM  covers the Windows taskbar). The dev/preview server must
REM  already be running.
REM    kiosk.bat                          -> http://localhost:5173 (npm run dev)
REM    kiosk.bat http://localhost:4173    -> custom URL (e.g. npm run kiosk)
REM  Exit:  Alt + F4
REM ============================================================
setlocal

set "URL=%~1"
if "%URL%"=="" set "URL=http://localhost:5173"

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo [ERROR] chrome.exe not found. Set the CHROME path in this file.
  pause
  exit /b 1
)

REM Start from a clean kiosk profile (avoids stale Chrome singleton locks).
rmdir /s /q "%TEMP%\alfred-kiosk-profile" >nul 2>&1

REM Fresh temp profile -> new instance so kiosk flags apply and the user's
REM normal tabs/bookmarks are not shown.
start "" "%CHROME%" --kiosk "%URL%" --user-data-dir="%TEMP%\alfred-kiosk-profile" --start-fullscreen --disable-pinch --overscroll-history-navigation=0 --disable-features=TranslateUI --no-first-run --no-default-browser-check --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required

endlocal
