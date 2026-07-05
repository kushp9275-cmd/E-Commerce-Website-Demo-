@echo off
setlocal

:: Try system python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python "%~dp0deploy.py" %*
    goto :eof
)

:: Try user profile install path
if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" (
    "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0deploy.py" %*
    goto :eof
)

:: Try general python command anyway
python "%~dp0deploy.py" %*
