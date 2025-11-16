# ========================================================
# Script para instalación automática de Python y pip
# Gestiona todo el proceso de primer arranque sin dependencias
# ========================================================

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Error($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Write-Success($msg) { Write-Host "[SUCCESS] $msg" -ForegroundColor Green }

# Verificar si Python ya está instalado
function Test-PythonInstalled {
    $pythonCommands = @("python", "py", "python3")
    foreach ($cmd in $pythonCommands) {
        try {
            $version = & $cmd --version 2>$null
            if ($version -match "Python (\d+\.\d+\.\d+)") {
                Write-Success "Python detectado: $version usando comando '$cmd'"
                return $cmd
            }
        } catch {
            # Continuar con el siguiente comando
        }
    }
    return $null
}

# Verificar si pip está disponible
function Test-PipInstalled($pythonCmd) {
    try {
        $pipVersion = & $pythonCmd -m pip --version 2>$null
        if ($pipVersion) {
            Write-Success "pip detectado: $pipVersion"
            return $true
        }
    } catch {
        return $false
    }
    return $false
}

# Descargar e instalar Python automáticamente
function Install-Python {
    Write-Info "Descargando e instalando Python automáticamente..."
    
    # Determinar la URL de descarga más reciente
    $pythonVersion = "3.11.9"  # Versión estable conocida
    $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "win32" }
    $installer = "python-${pythonVersion}-${arch}.exe"
    $downloadUrl = "https://www.python.org/ftp/python/${pythonVersion}/${installer}"
    
    # Crear directorio temporal
    $tempDir = Join-Path $env:TEMP "python_installer"
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
    $installerPath = Join-Path $tempDir $installer
    
    try {
        Write-Info "Descargando Python desde: $downloadUrl"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath -UseBasicParsing
        
        Write-Info "Instalando Python silenciosamente..."
        Write-Warn "Esto puede tardar 2-3 minutos. No cierres esta ventana."
        
        # Instalación silenciosa con opciones óptimas
        $installArgs = @(
            "/quiet",
            "InstallAllUsers=0",
            "TargetDir=${env:LOCALAPPDATA}\Programs\Python\Python311",
            "Include_doc=0",
            "Include_debug=0", 
            "Include_dev=1",
            "Include_exe=1",
            "Include_launcher=1",
            "InstallLauncherAllUsers=0",
            "Include_lib=1",
            "Include_pip=1",
            "Include_symbols=0",
            "Include_tcltk=1",
            "Include_test=0",
            "Include_tools=0",
            "LauncherOnly=0",
            "SimpleInstall=1",
            "SimpleInstallDescription=Instalacion Python para DCS Traductor",
            "PrependPath=1",
            "Shortcuts=0",
            "AssociateFiles=0"
        )
        
        $process = Start-Process -FilePath $installerPath -ArgumentList $installArgs -Wait -PassThru -NoNewWindow
        
        if ($process.ExitCode -eq 0) {
            Write-Success "Python instalado correctamente"
            
            # Actualizar las variables de entorno para esta sesión
            $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "User") + ";" + [Environment]::GetEnvironmentVariable("PATH", "Machine")
            
            # Esperar un momento y verificar
            Start-Sleep -Seconds 3
            
            $installedPython = Test-PythonInstalled
            if ($installedPython) {
                Write-Success "Verificación exitosa: Python funcional"
                return $installedPython
            } else {
                Write-Warn "Python instalado pero requiere reiniciar la terminal"
                Write-Info "Por favor, cierra esta ventana y vuelve a ejecutar el lanzador"
                return $null
            }
        } else {
            Write-Error "La instalación falló con código: $($process.ExitCode)"
            return $null
        }
        
    } catch {
        Write-Error "Error durante la instalación: $($_.Exception.Message)"
        return $null
    } finally {
        # Limpiar archivos temporales
        if (Test-Path $installerPath) {
            Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
        }
    }
}

# Función para reparar pip si está roto
function Repair-Pip($pythonCmd) {
    Write-Info "Reparando/actualizando pip..."
    try {
        # Método 1: Upgrade pip
        & $pythonCmd -m pip install --upgrade pip --user 2>$null
        
        # Verificar si funcionó
        if (Test-PipInstalled $pythonCmd) {
            Write-Success "pip reparado correctamente"
            return $true
        }
        
        # Método 2: Reinstalar pip con ensurepip
        Write-Info "Intentando reinstalar pip con ensurepip..."
        & $pythonCmd -m ensurepip --upgrade --user 2>$null
        & $pythonCmd -m pip install --upgrade pip --user 2>$null
        
        if (Test-PipInstalled $pythonCmd) {
            Write-Success "pip reinstalado correctamente"
            return $true
        }
        
        Write-Error "No se pudo reparar pip automáticamente"
        return $false
        
    } catch {
        Write-Error "Error reparando pip: $($_.Exception.Message)"
        return $false
    }
}

# Función principal de verificación/instalación
function Ensure-PythonEnvironment {
    param(
        [switch]$AutoInstall = $false,
        [switch]$Interactive = $true
    )
    
    Write-Info "Verificando entorno Python..."
    
    # 1. Verificar Python
    $pythonCmd = Test-PythonInstalled
    if (-not $pythonCmd) {
        if ($Interactive) {
            Write-Warn "Python no está instalado en este sistema"
            $response = Read-Host "¿Deseas instalarlo automáticamente? [S/n]"
            if ($response -match '^(s|si|sí|y|yes|)$') {
                $AutoInstall = $true
            }
        }
        
        if ($AutoInstall) {
            $pythonCmd = Install-Python
            if (-not $pythonCmd) {
                Write-Error "No se pudo instalar Python automáticamente"
                if ($Interactive) {
                    Write-Info "Opciones manuales:"
                    Write-Info "1. Visita https://www.python.org/downloads/"
                    Write-Info "2. Descarga Python 3.11+ para Windows"
                    Write-Info "3. Durante la instalación, marca 'Add Python to PATH'"
                    Write-Info "4. Reinicia esta aplicación"
                    Read-Host "Presiona ENTER para abrir la página de descarga"
                    Start-Process "https://www.python.org/downloads/"
                }
                return $null
            }
        } else {
            Write-Error "Python es requerido para ejecutar esta aplicación"
            return $null
        }
    }
    
    # 2. Verificar pip
    if (-not (Test-PipInstalled $pythonCmd)) {
        Write-Warn "pip no está disponible o está corrupto"
        if (-not (Repair-Pip $pythonCmd)) {
            Write-Error "No se pudo configurar pip correctamente"
            return $null
        }
    }
    
    Write-Success "Entorno Python completamente configurado"
    return $pythonCmd
}

# Funciones disponibles: Ensure-PythonEnvironment, Test-PythonInstalled, Test-PipInstalled