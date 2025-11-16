Param(
  [switch]$UseVenv = $true,
  [switch]$PauseOnExit = $false
)

# ========================
# Utilidades
# ========================
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Pause-IfNeeded(){ if($PauseOnExit){ Write-Host ""; Read-Host "Pulsa ENTER para cerrar" > $null } }

# Funciones de versión eliminadas para optimización

# ========================
# Mensaje de paciencia
# ========================
Write-Host "==============================================="
Write-Host "  DCS Orquestador Traductor (Web) - Lanzando…  "
Write-Host "==============================================="
Write-Host "Nota: la primera apertura del navegador puede tardar ~90s." -ForegroundColor Yellow
Write-Host ""

# ========================
# Validación de versiones removida para optimización
# ========================

# ========================
# Python + venv + deps
# ========================

# Importar funciones de instalación
. (Join-Path $ScriptDir "install_python.ps1")

# Asegurar que Python esté disponible
Write-Info "Verificando entorno Python..."
$Python = Ensure-PythonEnvironment -Interactive

if (-not $Python) {
  Write-Err "No se pudo configurar Python. La aplicación no puede continuar."
  Write-Host ""
  Write-Host "SOLUCIONES MANUALES:"
  Write-Host "1. Visita https://www.python.org/downloads/"
  Write-Host "2. Descarga Python 3.11+ para Windows"  
  Write-Host "3. Durante la instalación, marca 'Add Python to PATH'"
  Write-Host "4. Reinicia esta aplicación"
  Write-Host ""
  $ans = Read-Host "¿Abrir página de descarga ahora? [S/n]"
  if ($ans -match '^(s|si|sí|y|yes|)$') {
    Start-Process "https://www.python.org/downloads/"
  }
  Pause-IfNeeded
  exit 1
}

Write-Info "Python detectado: $Python"
$VenvDir = Join-Path $ProjectDir ".venv"
$ActivatePs1 = (Join-Path $VenvDir "Scripts\Activate.ps1") # Windows layout

if ($UseVenv) {
  if (-not (Test-Path $ActivatePs1)) {
    Write-Info "Creando entorno virtual: $VenvDir"
    iex "& $Python -m venv `"$VenvDir`""
  }
  if (-not (Test-Path $ActivatePs1)) {
    Write-Err "No se encontró el activador de venv: $ActivatePs1"
    Pause-IfNeeded; exit 1
  }
  Write-Info "Activando entorno virtual…"
  . $ActivatePs1
}

# Instalar dependencias
$Req = Join-Path $ScriptDir "requirements.txt"
if (Test-Path $Req) {
  Write-Info "Instalando dependencias desde run/requirements.txt…"
  pip install -r "$Req"
} else {
  # fallback básico
  pip install flask requests | Out-Null
}

# ========================
# Lanzar app y abrir navegador
# ========================
$Url = "http://127.0.0.1:5000/orchestrator"

Write-Info "Lanzando servidor Flask… ($Url)"
# Lanzar sin bloquear, esperando a que responda para abrir navegador
$FlaskAppPath = Join-Path $ScriptDir "run_flask_app.py"
$proc = Start-Process -PassThru -NoNewWindow powershell -ArgumentList @(
  "-NoProfile","-ExecutionPolicy","Bypass","-Command",
  "Set-Location '$ProjectDir'; python '$FlaskAppPath'"
)

# Intentar ping a /status hasta OK o tiempo máx (~90s)
$ok = $false
for ($i=0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 1
  try {
    $status = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri ($Url + "api/status")
    if ($status.StatusCode -ge 200 -and $status.StatusCode -lt 500) { $ok = $true; break }
  } catch { }
}
Start-Process $Url | Out-Null
if (-not $ok) {
  Write-Host "[WARN] El servidor puede tardar un poco mas en estar listo. Se abrio la URL igualmente." -ForegroundColor DarkYellow
}

Write-Info "Servidor iniciado. Cierra esta ventana cuando no la necesites."
Pause-IfNeeded
