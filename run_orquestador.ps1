param(
  [int]$Port = 5000,
  [string]$HostIP = "127.0.0.1",
  [int]$WaitSeconds = 180,
  [switch]$UseVenv,
  [switch]$PauseOnExit
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {
  $ppid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
  $parentName = (Get-Process -Id $ppid -ErrorAction SilentlyContinue).ProcessName
  if ($parentName -and $parentName -ieq 'explorer') { $PauseOnExit = $true }
} catch {}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogPath   = Join-Path $ScriptDir "run_orquestador_ps.log"
try { Start-Transcript -Path $LogPath -Append -ErrorAction SilentlyContinue | Out-Null } catch {}

function Write-Info($msg){ Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg){ Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err ($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Test-Command($name){ $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

function Get-PythonCmd(){
  if (Test-Command "python") { return "python" }
  if (Test-Command "py")     { return "py -3" }
  return $null
}

function Ensure-Python(){
  $py = Get-PythonCmd
  if ($py) {
    Write-Info "Python detectado: $($py) ($(& $py --version))"
    return $py
  }
  Write-Warn "Python no está instalado."
  $r = Read-Host "¿Quieres instalar Python ahora con winget? (s/N)"
  if ($r -match '^(s|si|sí|y|yes)$'){
    if (-not (Test-Command "winget")) {
      Write-Err "winget no está disponible. Instala Python manualmente y vuelve a ejecutar."
      throw "Python no disponible"
    }
    Write-Info "Instalando Python 3.x con winget..."
    winget install -e --id Python.Python.3 --source winget --accept-package-agreements --accept-source-agreements
    $py = Get-PythonCmd
    if (-not $py) { throw "No se pudo instalar/detectar Python automáticamente." }
    Write-Info "Python instalado: $(& $py --version)"
    return $py
  } else {
    throw "Python requerido. Aborta."
  }
}

# == NUEVO: crear/usar venv y devolver la ruta *exacta* del python de la venv ==
function Ensure-VenvAndGetPython($py){
  $venvPath = Join-Path $ScriptDir ".venv"
  if (-not $UseVenv -and -not (Test-Path $venvPath)) {
    return $py  # no usar venv
  }

  if (-not (Test-Path $venvPath)) {
    Write-Info "Creando entorno virtual en .venv ..."
    & $py -m venv $venvPath
  }

  # Rutas candidatas al ejecutable de python dentro de la venv
  $pyWin = Join-Path $venvPath "Scripts\python.exe"
  $pyNix = Join-Path $venvPath "bin/python"
  $pyCmd = $null

  if (Test-Path $pyWin) { $pyCmd = $pyWin }
  elseif (Test-Path $pyNix) { $pyCmd = $pyNix }

  if (-not $pyCmd) {
    Write-Warn "No se localizó el ejecutable de Python dentro de .venv. Intento activar (mejor esfuerzo)."
    $actPSWin = Join-Path $venvPath "Scripts\Activate.ps1"
    $actPSNix = Join-Path $venvPath "bin\Activate.ps1"
    if (Test-Path $actPSWin) { . $actPSWin; $pyCmd = "python" }
    elseif (Test-Path $actPSNix) { . $actPSNix; $pyCmd = "python" }
  }

  if (-not $pyCmd) { throw "No se pudo preparar la venv (.venv). Falta python dentro del entorno." }

  Write-Info "Usando Python de la venv: $pyCmd ($(& $pyCmd --version))"
  return $pyCmd
}

function Ensure-Requirements($pyCmd){
  $req = Join-Path $ScriptDir "requirements.txt"
  Write-Info "Actualizando pip y dependencias..."
  & $pyCmd -m pip install --upgrade pip
  if (Test-Path $req) {
    & $pyCmd -m pip install -r $req
  } else {
    Write-Warn "requirements.txt no encontrado. Instalando dependencias mínimas."
    & $pyCmd -m pip install flask requests
  }
}

function Test-PortReady($ip, $port){
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect($ip, $port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(300)
    $client.Close()
    return $ok
  } catch { return $false }
}

function Open-Browser($url){
  Write-Info "Abriendo navegador: $url"
  Start-Process $url | Out-Null
}

try {
  Write-Host "== DCS Orquestador Traductor (Web) ==" -ForegroundColor Green
  $verFile = Join-Path $ScriptDir "VERSION"
  if (Test-Path $verFile) {
    $ver = (Get-Content $verFile -Raw).Trim()
    if ($ver) { Write-Host "Versión: $ver" -ForegroundColor DarkCyan }
  }

  $py = Ensure-Python
  $py = Ensure-VenvAndGetPython $py
  Ensure-Requirements $py

  $app = Join-Path $ScriptDir "app.py"
  if (-not (Test-Path $app)) { throw "No se encuentra app.py en $ScriptDir" }

  Write-Host ""
  Write-Info "Lanzando servidor Flask en http://$HostIP`:$Port"
  Write-Host "Esto puede tardar ~1-2 minutos la primera vez. Ten paciencia… abriré la pestaña cuando el puerto responda." -ForegroundColor Yellow
  Write-Host ""

  # Lanzar app.py en nueva ventana
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName  = "powershell"
  $psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -Command `"& '$py' '$app'`""
  $psi.WorkingDirectory = $ScriptDir
  $psi.UseShellExecute = $true
  $psi.CreateNoWindow  = $false
  [void][System.Diagnostics.Process]::Start($psi)

  # Espera activa al puerto con spinner
  $url = "http://$HostIP`:$Port"
  $sp = "|/-\"
  $i = 0
  $deadline = (Get-Date).AddSeconds($WaitSeconds)
  while ((Get-Date) -lt $deadline) {
    $c = $sp[$i % $sp.Length]
    Write-Host -NoNewline "`rEsperando al servidor $c "
    if (Test-PortReady $HostIP $Port) {
      Write-Host "`rServidor disponible.               "
      Open-Browser $url
      break
    }
    Start-Sleep -Milliseconds 500
    $i++
  }
  if (-not (Test-PortReady $HostIP $Port)) {
    Write-Warn "No se detectó el puerto $Port a tiempo. Abre manualmente $url cuando esté listo."
  }

  Write-Info "Para detener el servidor usa el botón '✖ Cancelar' de la UI o cierra su ventana."
}
catch {
  Write-Err $_.Exception.Message
  Write-Err "Stack:`n$($_.Exception.StackTrace)"
}
finally {
  try { Stop-Transcript | Out-Null } catch {}
  if ($PauseOnExit) {
    Write-Host ""
    Write-Host "Log de esta sesión: $LogPath" -ForegroundColor DarkGray
    Read-Host "Pulsa ENTER para cerrar esta ventana"
  }
}
