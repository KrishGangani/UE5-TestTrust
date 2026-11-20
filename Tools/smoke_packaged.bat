@echo off
rem P03 TestTrust - smoke test of the packaged Development build: load the default map and quit.
rem Usage: smoke_packaged.bat [nullrhi|gpu]   nullrhi (default): no GPU; gpu: D3D12 on the real adapter, 960x540 windowed
rem The packaged game writes its log to ..\Build\Windows\TestTrust\Saved\Logs\TestTrust.log
setlocal
set "EXE=%~dp0..\Build\Windows\TestTrust.exe"
set "MODE=%~1"
if "%MODE%"=="" set "MODE=nullrhi"
if not exist "%EXE%" (
	echo smoke_packaged: %EXE% not found; run package.bat first
	exit /b 2
)
if /i "%MODE%"=="gpu" (
	"%EXE%" -windowed -ResX=960 -ResY=540 -nosound -unattended -traceautostart=0 -ExecCmds="quit" -log
) else (
	"%EXE%" -nullrhi -nosound -unattended -traceautostart=0 -ExecCmds="quit" -log
)
exit /b %ERRORLEVEL%
