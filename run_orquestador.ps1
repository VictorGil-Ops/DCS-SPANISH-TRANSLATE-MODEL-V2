Param(
  [switch]$UseVenv = $true,
  [switch]$PauseOnExit = $false,
  [switch]$CheckForUpdates = $true
)

# ========================
# Configuración del repo
# ========================
# TODO: PON TUS URLs AQUI:
$RepoRawVersionUrl = 'https://raw.githubusercontent.com/VictorGil-Ops/DCS-SPANISH-TRANSLATE-MODEL-V2/main/VERSION'   # <-- EDITA
$RepoWebUrl        = 'https://github.com/VictorGil-Ops/DCS-SPANISH-TRANSLATE-MODEL-V2'                               # <-- EDITA

# ========================
# Utilidades
# ========================
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $PSCommandPath
Set-Location $ScriptDir

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }
function Pause-IfNeeded(){ if($PauseOnExit){ Write-Host ""; Read-Host "Pulsa ENTER para cerrar" > $null } }

function Get-LocalVersion {
  $v = $env:ORQ_VERSION
  if (![string]::IsNullOrWhiteSpace($v)) { return $v.Trim() }
  $file = Join-Path $ScriptDir 'VERSION'
  if (Test-Path $file) { return (Get-Content -LiteralPath $file -Raw).Trim() }
  return 'dev'
}

function Get-RemoteVersion {
  param([string]$Url)
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 10
    return ($resp.Content.Trim())
  } catch {
    return $null
  }
}

function VersionToInt {
  param([string]$v)
  if ([string]::IsNullOrWhiteSpace($v)) { return 0 }
  $digits = ($v -replace '[^\d]','')
  if ([string]::IsNullOrWhiteSpace($digits)) { return 0 }
  return [int64]$digits
}

function Save-UpdateInfoJson {
  param([string]$local,[string]$latest,[bool]$isNewer)
  $obj = [ordered]@{
    local_version  = $local
    latest_version = $latest
    is_newer       = $isNewer
    ts             = (Get-Date).ToString('s')
  }
  $json = ($obj | ConvertTo-Json -Depth 5)
  Set-Content -LiteralPath (Join-Path $ScriptDir '.update_info.json') -Value $json -Encoding UTF8
}

function Clear-UpdateInfoJson {
  if (Test-Path (Join-Path $ScriptDir '.update_info.json')) {
    Remove-Item -LiteralPath (Join-Path $ScriptDir '.update_info.json') -Force -ErrorAction SilentlyContinue
  }
}

# ========================
# Mensaje de paciencia
# ========================
Write-Host "==============================================="
Write-Host "  DCS Orquestador Traductor (Web) - Lanzando…  "
Write-Host "==============================================="
Write-Host "Nota: la primera apertura del navegador puede tardar ~90s." -ForegroundColor Yellow
Write-Host ""

# ========================
# Comprobar actualizaciones (opcional)
# ========================
$LocalVer  = Get-LocalVersion
$LatestVer = $null
$IsNewer   = $false

if ($CheckForUpdates) {
  Write-Info "Versión local: $LocalVer"
  $LatestVer = Get-RemoteVersion -Url $RepoRawVersionUrl
  if ($LatestVer) {
    Write-Info "Versión remota: $LatestVer"
    $IsNewer = (VersionToInt $LatestVer) -gt (VersionToInt $LocalVer)
    if ($IsNewer) {
      Write-Host ""
      $ans = Read-Host "Hay una version nueva ($LatestVer) - Quieres actualizar el repo ahora? [S/n]"
      if ($ans -match '^(s|si|sí|y|yes|)$') {
        # Actualizar usando git si es un clon
        if (Test-Path (Join-Path $ScriptDir '.git')) {
          $git = (Get-Command git -ErrorAction SilentlyContinue)
          if ($git) {
            try {
              Write-Info "Actualizando desde git…"
              git fetch --all
              git pull --rebase --autostash
              Write-Info "Repositorio actualizado. (Las carpetas no trackeadas como campaings/ y log_orquestador/ no se tocan)"
              # Releer versión y limpiar aviso
              $LocalVer = Get-LocalVersion
              Clear-UpdateInfoJson
            } catch {
              Write-Err "git pull fallo: $($_.Exception.Message)"
              Save-UpdateInfoJson -local $LocalVer -latest $LatestVer -isNewer $true
            }
          } else {
            Write-Err "No se encontro 'git' en PATH. Abre $RepoWebUrl para actualizar manualmente."
            Save-UpdateInfoJson -local $LocalVer -latest $LatestVer -isNewer $true
          }
        } else {
          Write-Err "Este directorio no parece un clon git (.git no existe). Abre $RepoWebUrl y descarga la última version."
          Save-UpdateInfoJson -local $LocalVer -latest $LatestVer -isNewer $true
        }
      } else {
        # No actualizar: avisar en UI
        Save-UpdateInfoJson -local $LocalVer -latest $LatestVer -isNewer $true
      }
    } else {
      Clear-UpdateInfoJson
    }
  } else {
    Write-Host "[WARN] No se pudo consultar la versión remota. Continuando…" -ForegroundColor DarkYellow
  }
}

# ========================
# Python + venv + deps
# ========================
function Ensure-Python {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if ($py) { return "python" }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return "py -3" }
  return $null
}

$Python = Ensure-Python
if (-not $Python) {
  $ans = Read-Host "No se detecto Python. ¿Deseas instalarlo desde python.org? [S/n]"
  if ($ans -match '^(s|si|sí|y|yes|)$') {
    Start-Process "https://www.python.org/downloads/" -WindowStyle Normal
    Write-Host "Instala Python y vuelve a ejecutar este script." -ForegroundColor Yellow
  }
  Pause-IfNeeded
  exit
}

Write-Info "Python detectado: $Python"
$VenvDir = Join-Path $ScriptDir ".venv"
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
  Write-Info "Instalando dependencias desde requirements.txt…"
  pip install -r "$Req"
} else {
  # fallback básico
  pip install flask requests | Out-Null
}

# ========================
# Lanzar app y abrir navegador
# ========================
$env:ORQ_VERSION = $LocalVer
$Url = "http://127.0.0.1:5000/"

Write-Info "Lanzando servidor Flask… ($Url)"
# Lanzar sin bloquear, esperando a que responda para abrir navegador
$proc = Start-Process -PassThru -NoNewWindow powershell -ArgumentList @(
  "-NoProfile","-ExecutionPolicy","Bypass","-Command",
  "python '$ScriptDir\app.py'"
)

# Intentar ping a /status hasta OK o tiempo máx (~90s)
$ok = $false
for ($i=0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 1
  try {
    $status = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri ($Url + "status")
    if ($status.StatusCode -ge 200 -and $status.StatusCode -lt 500) { $ok = $true; break }
  } catch { }
}
Start-Process $Url | Out-Null
if (-not $ok) {
  Write-Host "[WARN] El servidor puede tardar un poco mas en estar listo. Se abrio la URL igualmente." -ForegroundColor DarkYellow
}

Write-Info "Servidor iniciado. Cierra esta ventana cuando no la necesites."
Pause-IfNeeded
