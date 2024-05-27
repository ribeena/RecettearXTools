@echo off

REM Check if a file was dropped
if "%~1"=="" (
    echo No file dropped.
    pause
    exit /b 1
)

REM Run the Python script with the dropped file as an argument
python "%~dp0\main.py" "%~1"

REM Leave the window open to see the output
echo.
pause