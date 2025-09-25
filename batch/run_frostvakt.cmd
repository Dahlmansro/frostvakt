@echo off
chcp 65001 >NUL

REM Anpassa dessa sökvägar till ditt system:
set "CONDA_ROOT=C:\Users\CD\anaconda3"
set "ENV_NAME=frostvakt"
set "PROJ=C:\Users\CD\python_2\frostvakt"

call "%CONDA_ROOT%\condabin\conda.bat" activate %ENV_NAME%

cd /d "%PROJ%"
python -u "%PROJ%\src\main.py"

exit /b %ERRORLEVEL%