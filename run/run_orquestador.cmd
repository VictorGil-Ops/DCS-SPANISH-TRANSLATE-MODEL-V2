@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul

REM --- Ubicar directorio del proyecto (padre del directorio run) ---
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."

REM --- Resolver PowerShell (pwsh si existe; si no, Windows PowerShell) ---
set "PSH="
for %%P in (pwsh.exe) do if exist "%%~$PATH:P" set "PSH=%%~$PATH:P"
if not defined PSH (
  set "PSH=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
)
if not exist "%PSH%" (
  echo [ERROR] No se encontro PowerShell ni pwsh en el sistema.
  echo Instala PowerShell o ajusta la ruta en este .cmd.
  pause
  exit /b 1
)

REM --- Banner ---
echo == DCS Orquestador Traductor (Web) ==

REM --- Crear/actualizar acceso directo con icono personalizado ---
echo Generando acceso directo con icono personalizado...
"%PSH%" -NoProfile -ExecutionPolicy Bypass -Command "try { & '.\run\create_shortcut.ps1' -Silent } catch { Write-Host 'Info: Error creando acceso directo, continuando...' -ForegroundColor Yellow }" 2>nul

REM --- Lanzar el script (en esta misma ventana) ---
REM  -ExecutionPolicy Bypass evita bloqueos por politicas
REM  -NoProfile acelera el arranque
REM  -UseVenv usa/crea .venv; -PauseOnExit mantiene abierta la ventana si vienes de doble click
"%PSH%" -NoProfile -ExecutionPolicy Bypass -File ".\run\run_orquestador.ps1" -UseVenv -PauseOnExit
set "ERR=%ERRORLEVEL%"

popd >nul

REM --- Mantener visible si hubo error ---
if not "%ERR%"=="0" (
  echo.
  echo [ERROR] PowerShell devolvio codigo %ERR%.
  echo Revisa los mensajes anteriores y pulsa una tecla para cerrar.
  pause
)
endlocal
