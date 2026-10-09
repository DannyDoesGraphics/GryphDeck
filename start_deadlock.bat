@echo off
setlocal

rem Builds and installs the GryphDeck spectator mod, starts Deadlock, and keeps GryphDeck's
rem team sides in step with the match. Options: see tools\deadlock\spectator.py --help.
cd /d "%~dp0"
set "VENV_PYTHON=%CD%\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo GryphDeck has not been set up yet. Run setup.bat first.
    exit /b 1
)

"%VENV_PYTHON%" tools\deadlock\spectator.py %*
exit /b %errorlevel%
