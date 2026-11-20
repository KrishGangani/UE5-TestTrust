@echo off
rem P03 TestTrust - run automation tests headless in the editor and exit with their result.
rem Usage: run_tests.bat [Filter]   (default: StartsWith:TestTrust, every test of this project)
rem Exit code 0 = all passed; non-zero = a failure (AutomationCommandline.cpp:503-504 prints "TEST COMPLETE. EXIT CODE").
rem The JSON report goes to TestTrust\Saved\Automation\Reports\index.json (-ReportExportPath, AutomationControllerManager.cpp:233).
rem Needs the Development editor target (build.bat). Run it through the machine-wide queue.
setlocal
set "UE_ROOT=C:\Program Files\Epic Games\UE_5.8"
set "PROJECT=%~dp0..\TestTrust\TestTrust.uproject"
set "FILTER=%~1"
if "%FILTER%"=="" set "FILTER=StartsWith:TestTrust"
set "REPORT=%~dp0..\TestTrust\Saved\Automation\Reports"
set "LOG=%~dp0..\TestTrust\Saved\Logs\Tests.log"

"%UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "%PROJECT%" -ExecCmds="Automation RunTests %FILTER%;Quit" -unattended -nullrhi -nosound -nosplash -nopause -traceautostart=0 -log -abslog="%LOG%" -ReportExportPath="%REPORT%"
exit /b %ERRORLEVEL%
