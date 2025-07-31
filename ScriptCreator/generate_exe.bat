@echo off
set "DIST_DIR=C:\Users\valde\OneDrive\Escritorio\scriptcreator+glfess\ScriptCreator\dist"
set "SRC_DIR=C:\Users\valde\OneDrive\Escritorio\scriptcreator+glfess\ScriptCreator"



REM === ELIMINAR main.spec (si existe) ===
if exist "%SRC_DIR%\main.spec" del "%SRC_DIR%\main.spec"

REM === PARÁMETROS DE LICENCIA ===
set "LICENSE_KEY=%~1"
set "DAYS=%~2"
if "%DAYS%"=="" set "DAYS=30"

cd /d "%SRC_DIR%"

REM === GENERAR INFO DE LICENCIA ===
if not "%LICENSE_KEY%"=="" (
    python generate_build_info.py %DAYS% %LICENSE_KEY%
) else (
    python generate_build_info.py %DAYS%
)

REM === COMPILAR CON PYINSTALLER ===
pyinstaller main.py --noconfirm --clean --console --icon=ico.ico --name="Script Creator" --onefile --distpath "%DIST_DIR%"

REM === COPIAR ARCHIVOS DE LICENCIA A DIST ===
if exist licenses.json copy /Y licenses.json "%DIST_DIR%\licenses.json" >nul
if exist license_details.dat copy /Y license_details.dat "%DIST_DIR%\license_details.dat" >nul

REM === PAUSA FINAL PARA VERIFICACIÓN ===
echo.
echo =============================
echo Compilación finalizada.
echo =============================
pause
