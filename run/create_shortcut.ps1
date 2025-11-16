#!/usr/bin/env powershell
# Crear acceso directo al orquestador
# Este script crea automáticamente run_orquestador.lnk

param(
    [switch]$Silent
)

$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectDir = Split-Path -Parent $ScriptDir

# Configuración del acceso directo
$ShortcutPath = Join-Path $ProjectDir "Traductor - DCS.lnk"
$TargetPath = Join-Path $ScriptDir "run_orquestador.cmd"
$IconPath = Join-Path $ProjectDir "app\static\DCS_SPANISH.ico"

# Verificar que los archivos existen antes de crear el acceso directo
if (-not (Test-Path $TargetPath)) {
    Write-Host "❌ Error: No se encuentra $TargetPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $IconPath)) {
    Write-Host "⚠️ Advertencia: No se encuentra el icono $IconPath" -ForegroundColor Yellow
    $IconPath = ""  # Usar icono por defecto si no existe
}

# Crear el acceso directo
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Description = "Traductor - DCS World - Lanzador Web"
if ($IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Save()

# Solo mostrar mensajes detallados si se ejecuta directamente (no desde .bat o con -Silent)
if (-not $Silent -and ($MyInvocation.Line -notmatch "Traductor.*DCS\.bat")) {
    Write-Host "✅ Acceso directo creado: $ShortcutPath" -ForegroundColor Green
    Write-Host "   - Apunta a: $TargetPath" -ForegroundColor Cyan
    Write-Host "   - Icono: $IconPath" -ForegroundColor Cyan
}