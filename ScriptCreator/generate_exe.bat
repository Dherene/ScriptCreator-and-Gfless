@echo off
REM ====== Movernos a la carpeta donde está este BAT ======
cd /d "%~dp0"

REM ====== Paths base ======
set "ROOT=%cd%"
set "BUILD=%ROOT%\build"
set "DIST=%ROOT%\dist"
set "SRC_DIR=%ROOT%"

echo ==============================
echo   LIMPIEZA PREVIA DE BUILD/DIST
echo ==============================

REM 1) Borrar carpeta build si existe
if exist "%BUILD%" (
  echo - Eliminando carpeta: "%BUILD%"
  rmdir /s /q "%BUILD%"
) else (
  echo - No existe carpeta build. OK
)

REM 2) Borrar archivos específicos en dist si existen
if not exist "%DIST%" (
  echo - No existe carpeta dist. OK
) else (
  for %%F in ("license_details.dat" "licenses.json" "Script Creator.exe") do (
    if exist "%DIST%\%%~F" (
      echo - Eliminando "%DIST%\%%~F"
      del /q "%DIST%\%%~F"
    ) else (
      echo - No existe "%DIST%\%%~F". OK
    )
  )
)

REM 3) Asegurar carpeta dist
if not exist "%DIST%" (
  mkdir "%DIST%"
)

echo ==============================
echo   LIMPIEZA COMPLETA
echo ==============================


REM ====== PARÁMETROS DE LICENCIA ======
set "LICENSE_KEY=%~1"
set "DAYS=%~2"
if "%DAYS%"=="" set "DAYS=30"

REM ====== Opcional: nombre de la DLL a incluir ======
REM Define DLL_NAME antes de llamar al BAT o acá. Si no está definido, no se usa --add-binary.
REM set "DLL_NAME=GflessDLL.dll"

if defined DLL_NAME (
  set "ADDDLL=--add-binary \"%SRC_DIR%\%DLL_NAME%;.\""
) else (
  set "ADDDLL="
)

REM ====== Entrar al SRC ======
cd /d "%SRC_DIR%"

REM ====== ELIMINAR main.spec (si existe) ======
if exist "%SRC_DIR%\main.spec" del /q "%SRC_DIR%\main.spec"

REM ====== GENERAR INFO DE LICENCIA ======
if not "%LICENSE_KEY%"=="" (
    py -3.9-32 -u generate_build_info.py %DAYS% %LICENSE_KEY%
) else (
    py -3.9-32 -u generate_build_info.py %DAYS%
)

echo ==============================
echo   COMPILANDO (PyInstaller)
echo ==============================

REM ====== COMPILAR CON PYINSTALLER ======
py -3.9-32 -m PyInstaller main.py --noconfirm --clean --console --icon=ico.ico ^
  --name="Script Creator" --onefile --distpath "%DIST%" %ADDDLL% ^
  --hidden-import=PIL --hidden-import=PIL.Image --hidden-import=PIL.PngImagePlugin --hidden-import=PIL._imaging ^
  --hidden-import=requests --hidden-import=urllib3 --hidden-import=certifi --hidden-import=idna --hidden-import=charset_normalizer

REM ====== COPIAR ARCHIVOS DE LICENCIA A DIST ======
if exist "%SRC_DIR%\licenses.json" copy /Y "%SRC_DIR%\licenses.json" "%DIST%\licenses.json" >nul
if exist "%SRC_DIR%\license_details.dat" copy /Y "%SRC_DIR%\license_details.dat" "%DIST%\license_details.dat" >nul

echo.
echo =============================
echo   Compilación finalizada.
echo   Dist: "%DIST%"
echo =============================
pause
