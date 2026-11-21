@echo off
rem P03 TestTrust - every Phase 4 foundation check in one run, so the machine-wide queue is entered only once.
rem F-1 editor build, F-2 game build, F-3 uncooked smoke, F-4 tests in the editor, F-5 package, F-6 packaged smoke (no GPU),
rem F-7 packaged smoke (GPU). Stops at the first failure and returns its exit code. Results: Explanation\09_Testing_And_Benchmarks.md.
rem Each step is followed by "if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%", never "|| exit /b": run as "cmd /c script.bat"
rem (how the queue starts it), "call :step ... || exit /b" stops the chain but exits with 0 (portfolio brief rule 12;
rem reproduced in 09). The explicit form also passes negative crash codes through.
rem Usage (through the queue): python -I -u tools\ue_queue.py run --project P03 --label "..." -- "<this script>"
setlocal
set "HERE=%~dp0"

call :step F-1 "%HERE%build.bat" TestTrustEditor Development
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
call :step F-2 "%HERE%build.bat" TestTrust Development
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
call :step F-3 "%HERE%smoke_game.bat"
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
call :step F-4 "%HERE%run_tests.bat" StartsWith:TestTrust
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
call :step F-5 "%HERE%package.bat" Development
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
call :step F-6 "%HERE%smoke_packaged.bat" nullrhi
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
call :step F-7 "%HERE%smoke_packaged.bat" gpu
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
echo [phase4] all checks passed
exit /b 0

:step
echo [phase4] %1 start %DATE% %TIME%
call %2 %3 %4
set "RC=%ERRORLEVEL%"
echo [phase4] %1 end %DATE% %TIME% exit=%RC%
exit /b %RC%
