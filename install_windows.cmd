@echo off
setlocal EnableExtensions
set "SRC=%~dp0go_shx_stroke_text"
set "DEST=%APPDATA%\ingetrazo\plugins\go_shx_stroke_text"
set "BK=%LOCALAPPDATA%\GOEngineering\PluginBackups"
if not exist "%SRC%\__init__.py" (
  echo ERROR: The go_shx_stroke_text package must be next to this installer.
  exit /b 1
)
if exist "%DEST%" (
  if not exist "%BK%" mkdir "%BK%"
  if errorlevel 1 exit /b 1
  set "STAMP=%RANDOM%%RANDOM%"
  xcopy "%DEST%" "%BK%\go_shx_stroke_text_%STAMP%\" /E /I /Q /Y >nul
  if errorlevel 1 (
    echo ERROR: Backup failed. Installation aborted.
    exit /b 1
  )
  rmdir /S /Q "%DEST%"
  if errorlevel 1 exit /b 1
)
if not exist "%DEST%" mkdir "%DEST%"
if errorlevel 1 exit /b 1
xcopy "%SRC%" "%DEST%\" /E /I /Q /Y >nul
if errorlevel 1 (
  echo ERROR: Copy failed. Check permissions and the plugins folder.
  exit /b 1
)
echo Installed to: %DEST%
echo Restart IngeTrazo fully. Open Extensions - GO SHX Stroke Text.
pause
exit /b 0
