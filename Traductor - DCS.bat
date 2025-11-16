@echo off
chcp 65001 >nul
title Traductor DCS - Lanzando...

REM ==========================================
REM  LANZADOR DIRECTO DEL TRADUCTOR DCS
REM  Portable - Funciona desde cualquier ubicacion
REM ==========================================

echo.
echo ==========================================
echo   TRADUCTOR DCS - LANZANDO APLICACION
echo ==========================================
echo.

REM Cambiar al directorio del proyecto (donde esta este script)
cd /d "%~dp0"

REM Verificar que existe el script principal
if not exist "run\run_orquestador.cmd" (
    echo [ERROR] No se encuentra run\run_orquestador.cmd
    echo    Asegurate de que este archivo esta en la carpeta raiz del proyecto
    echo.
    echo Presiona cualquier tecla para cerrar...
    pause >nul
    exit /b 1
)

REM Verificar que Python esta instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no esta en PATH
    echo.
    echo INSTALACION AUTOMATICA DISPONIBLE:
    echo    1. Se abrira PowerShell para instalar Python automaticamente
    echo    2. Si prefieres instalacion manual: https://www.python.org/downloads/
    echo       Asegurate de marcar "Add Python to PATH" durante la instalacion
    echo.
    set /p choice="Intentar instalacion automatica? [S/n]: "
    if /i "%choice%"=="n" (
        echo Abriendo pagina de descarga manual...
        start https://www.python.org/downloads/
        echo.
        echo Despues de instalar Python, ejecuta este archivo nuevamente.
        pause
        exit /b 1
    )
    echo.
    echo [INFO] Iniciando instalacion automatica de Python...
    echo    Esto puede tardar 2-3 minutos. No cierres la ventana.
    echo.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& '.\run\install_python.ps1'; Ensure-PythonEnvironment -AutoInstall"
    
    REM Verificar nuevamente despues de la instalacion
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] La instalacion automatica no fue exitosa
        echo    Por favor instala Python manualmente desde python.org
        echo    Asegurate de reiniciar esta aplicacion despues de instalar
        pause
        exit /b 1
    )
    echo [SUCCESS] Python instalado correctamente!
    echo.
)

REM Mostrar version de Python
echo [INFO] Verificando Python...
python --version

REM Crear/actualizar acceso directo con icono personalizado
echo [INFO] Generando acceso directo con icono personalizado...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { & '.\run\create_shortcut.ps1' } catch { Write-Host 'Error creando acceso directo, continuando...' -ForegroundColor Yellow }" 2>nul
if exist "Traductor - DCS.lnk" (
    echo [OK] Acceso directo generado exitosamente
    echo    Tambien puedes usar "Traductor - DCS.lnk" directamente
) else (
    echo [WARN] No se pudo crear acceso directo, pero continuando...
)
echo.

REM Actualizar pip antes de lanzar la aplicacion
echo [INFO] Actualizando pip...
python.exe -m pip install --upgrade pip >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] pip actualizado correctamente
) else (
    echo [WARN] No se pudo actualizar pip, continuando...
)
echo.

echo [INFO] Iniciando Traductor DCS...
echo    Si hay un error, la ventana se mantendra abierta para que puedas verlo
echo.

REM Ejecutar el orquestador
call "run\run_orquestador.cmd"

REM Si hay error, mostrar informacion util
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] La aplicacion se cerro con error %errorlevel%
    echo.
    echo POSIBLES SOLUCIONES:
    echo    1. Ejecuta este .bat como administrador
    echo    2. Verifica que tienes acceso a internet para descargar dependencias
    echo    3. Reinicia el equipo e intenta de nuevo
    echo    4. Desactiva temporalmente el antivirus
    echo.
    echo Para mas informacion tecnica, abre una terminal (cmd) en esta carpeta
    echo y ejecuta: run\run_orquestador.cmd
    echo.
    echo Presiona cualquier tecla para cerrar...
    pause >nul
)