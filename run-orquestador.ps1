<# 
  run-orquestador.ps1
  - Verifica/instala Python (opcional, usando winget)
  - Crea venv .venv e instala dependencias (flask, requests)
  - Arranca app.py y abre el navegador en http://localhost:5000

  Consejos:
  - Para ejecutar con doble clic, botón derecho → "Run with PowerShell".
  - Si tu política de ejecución bloquea scripts, puedes hacer temporalmente:
      Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
#>

# --- Utilidades ---
function Test-Exists([string]$cmd) {
  try { return [bool](Get-Command $cmd -ErrorAction Stop) } catch { return $false }
}

function Ask-YesNo($prompt, $defaultYes=$true) {
  $suffix = if ($defaultYes) { "[S/n]" } else { "[s/N]" }
  while ($true) {
    $ans = Read-Host "$prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($ans)) { return $defaultYes }
    switch ($ans.ToLower()) {
      "s" { return $true }
      "y" { return $true }
      "n" { return $false }
      default { Write-Host "Responde 's' o 'n'." -ForegroundColor Yellow }
    }
  }
}

# --- Ir a la carpeta del script ---
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

# --- Detectar Python ---
$pythonCmd = $null
if (Test-Exists "py")      { $pythonCmd = "py" }
elseif (Test-Exists "python") { $pythonCmd = "python" }

if (-not $pythonCmd) {
  Write-Host "No se ha encontrado Python." -ForegroundColor Yellow
  if (Ask-YesNo "¿Quieres instalar Python 3 ahora (usando winget)?") {
    if (-not (Test-Exists "winget")) {
      Write-Host "No se encontró 'winget'. Instálalo desde Microsoft Store o instala Python manualmente desde https://www.python.org/downloads/." -ForegroundColor Red
      Read-Host "Pulsa Enter para salir"
      exit 1
    }
    Write-Host "Instalando Python 3 con winget..." -ForegroundColor Cyan
    # Nota: el ID puede variar; Python.Python.3 suele ser correcto
    winget install -e --id Python.Python.3 --source winget
    # Re-detectar
    if (Test-Exists "py") { $pythonCmd = "py" }
    elseif (Test-Exists "python") { $pythonCmd = "python" }
    else {
      Write-Host "Python no se detecta tras la instalación. Reinicia la terminal o instala manualmente." -ForegroundColor Red
      Read-Host "Pulsa Enter para salir"
      exit 1
    }
  } else {
    Write-Host "Python es necesario para ejecutar la app. Cancelo." -ForegroundColor Red
    exit 1
  }
}

# --- Resolver binario Python 3 concreto ---
try {
  # Preferimos el lanzador 'py -3' en Windows; si no, 'python'
  if ($pythonCmd -eq "py") {
    $pythonExe = (& py -3 -c "import sys,os;print(sys.executable)" 2>$null)
    if (-not $pythonExe) { $pythonExe = (& py -c "import sys;print(sys.executable)") }
  } else {
    $pythonExe = (& python -c "import sys;print(sys.executable)")
  }
} catch { $pythonExe = $null }

if (-not $pythonExe) {
  Write-Host "No se pudo resolver la ruta de Python. Intentando usar 'python' directamente..." -ForegroundColor Yellow
  $pythonExe = "python"
}

Write-Host "Usando Python en: $pythonExe" -ForegroundColor Green

# --- Crear/usar venv ---
$venvDir = Join-Path (Get-Location) ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
  Write-Host "Creando entorno virtual en .venv ..." -ForegroundColor Cyan
  & $pythonExe -m venv ".venv"
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
    Write-Host "No se pudo crear el entorno virtual. Intento continuar sin venv..." -ForegroundColor Yellow
    $venvPython = $pythonExe
  }
} else {
  Write-Host "Entorno virtual .venv detectado." -ForegroundColor Green
}

# --- Actualizar pip e instalar dependencias ---
function PipInstall([string[]]$packages) {
  Write-Host "Actualizando pip..." -ForegroundColor Cyan
  & $venvPython -m pip install --upgrade pip
  if ($LASTEXITCODE -ne 0) { Write-Host "Advertencia: no se pudo actualizar pip." -ForegroundColor Yellow }

  if (Test-Path "requirements.txt") {
    Write-Host "Instalando dependencias desde requirements.txt..." -ForegroundColor Cyan
    & $venvPython -m pip install -r requirements.txt
  } else {
    Write-Host "Instalando dependencias básicas (flask, requests)..." -ForegroundColor Cyan
    & $venvPython -m pip install flask requests
  }
}

PipInstall @("flask","requests")

# --- Comprobar que app.py existe ---
if (-not (Test-Path ".\app.py")) {
  Write-Host "No se encontró 'app.py' en la carpeta actual." -ForegroundColor Red
  Write-Host "Asegúrate de ejecutar este script en el mismo directorio donde está app.py." -ForegroundColor Yellow
  Read-Host "Pulsa Enter para salir"
  exit 1
}

# --- Lanzar app y abrir navegador ---
$port = 5000
$url  = "http://localhost:$port"

Write-Host "Arrancando app.py ..." -ForegroundColor Cyan
# Iniciamos la app en una ventana aparte para no bloquear el script
# Si prefieres en la misma consola, cambia a Start-Process -NoNewWindow y elimina el bucle de espera.
$proc = Start-Process -FilePath $venvPython -ArgumentList "app.py" -PassThru

# Esperar a que escuche y abrir navegador
Write-Host "Esperando a que el servidor esté listo en $url ..." -ForegroundColor Cyan
$ready = $false
for ($i=0; $i -lt 30; $i++) {
  try {
    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
    if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) { $ready = $true; break }
  } catch { Start-Sleep -Milliseconds 500 }
}
if ($ready) {
  Write-Host "Servidor listo. Abriendo el navegador..." -ForegroundColor Green
  Start-Process $url
} else {
  Write-Host "No se pudo verificar el arranque del servidor, abriendo el navegador igualmente..." -ForegroundColor Yellow
  Start-Process $url
}

Write-Host "Logs en: .\log_orquestador" -ForegroundColor DarkGray
Write-Host "Para detener, cierra la ventana de la app o termina el proceso." -ForegroundColor DarkGray
