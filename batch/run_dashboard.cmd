@echo off
chcp 65001 >NUL

REM Anpassa dessa sökvägar till ditt system:
set "CONDA_ROOT=C:\Users\CD\anaconda3"
set "ENV_NAME=frostvakt"
set "PROJ=C:\Users\CD\python_2\frostvakt"

echo Startar Frostvakt Dashboard...
echo Öppnar webbläsaren på http://localhost:8501

call "%CONDA_ROOT%\condabin\conda.bat" activate %ENV_NAME%

cd /d "%PROJ%"
streamlit run dashboard.py

pause