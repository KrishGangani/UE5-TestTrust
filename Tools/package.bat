@echo off
rem P03 TestTrust - package a standalone Win64 build (BuildCookRun). Flags as in UE5-UpdateBudget (its 01b section 4).
rem Usage: package.bat [Configuration]   Configuration: Development (default; perf-gate runs) | Shipping (no CSV profiler; not used)
rem Note: the launcher (installed) engine cannot build the Test configuration.
rem Output: ..\Build\Windows\TestTrust.exe   (Build\ is git-ignored)
setlocal
set "UE_ROOT=C:\Program Files\Epic Games\UE_5.8"
set "PROJECT=%~dp0..\TestTrust\TestTrust.uproject"
set "ARCHIVE=%~dp0..\Build"
set "CONFIG=%~1"
if "%CONFIG%"=="" set "CONFIG=Development"

call "%UE_ROOT%\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun -project="%PROJECT%" -noP4 -utf8output -unattended -platform=Win64 -clientconfig=%CONFIG% -build -cook -stage -pak -archive -archivedirectory="%ARCHIVE%"
exit /b %ERRORLEVEL%
