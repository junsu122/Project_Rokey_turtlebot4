@echo off
REM ============================================================
REM  ALFRED one-click kiosk launcher
REM    build  ->  preview server  ->  Chrome kiosk (fullscreen)
REM  Exit the kiosk window with  Alt + F4  (server auto-cleaned up).
REM  (Messages are ASCII so cmd.exe parses correctly on any code page.)
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PORT=4173"
set "URL=http://localhost:%PORT%"

echo.
echo [1/4] Checking dependencies...
if not exist "node_modules" (
  echo       node_modules missing - running npm install
  call npm install || ( echo [ERROR] npm install failed & pause & exit /b 1 )
)

echo [2/4] Building...
call npm run build || ( echo [ERROR] build failed & pause & exit /b 1 )

echo [3/4] Starting preview server on port %PORT% ...
start "ALFRED_PREVIEW_SERVER" /min cmd /c "npx vite preview --host --port %PORT% --strictPort"

REM --- wait until the server answers (max ~60s) ---
set /a tries=0
:waitloop
set /a tries+=1
curl -s -o nul "%URL%"
if not errorlevel 1 goto serverup
if !tries! geq 60 ( echo [ERROR] server did not start & goto cleanup )
ping -n 2 127.0.0.1 >nul
goto waitloop
:serverup
echo       Server ready.

echo [4/4] Launching kiosk. Press Alt+F4 in the kiosk window to exit.
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "!CHROME!" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "!CHROME!" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "!CHROME!" ( echo [ERROR] chrome.exe not found & goto cleanup )

REM Start from a clean kiosk profile (avoids stale Chrome singleton locks
REM from a previous run that can make a new launch exit immediately).
rmdir /s /q "%TEMP%\alfred-kiosk-profile" >nul 2>&1

REM Fresh temp profile -> new instance so kiosk flags apply and the user's
REM normal tabs/bookmarks are not shown.
start "" "!CHROME!" --kiosk "%URL%" --user-data-dir="%TEMP%\alfred-kiosk-profile" --start-fullscreen --disable-pinch --overscroll-history-navigation=0 --disable-features=TranslateUI --no-first-run --no-default-browser-check --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required

echo       Kiosk running. Close it with Alt+F4 to stop the server.
REM NOTE: 'start /wait' does not work for Chrome (it forks and returns instantly).
REM So we block here until the kiosk profile's Chrome processes are all gone.
powershell -NoProfile -Command "$d=(Get-Date).AddSeconds(30); while((Get-Date) -lt $d -and -not (Get-CimInstance Win32_Process | ?{$_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*alfred-kiosk-profile*'})){Start-Sleep -Milliseconds 500}; while(Get-CimInstance Win32_Process | ?{$_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*alfred-kiosk-profile*'}){Start-Sleep -Seconds 1}"

:cleanup
echo.
echo Cleaning up: stopping preview server...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr LISTENING ^| findstr ":%PORT%"') do taskkill /f /t /pid %%p >nul 2>&1
endlocal
exit /b 0
