# Instalador de um comando para Windows.
#   Local:   powershell -ExecutionPolicy Bypass -File install.ps1
#   Remoto:  irm https://raw.githubusercontent.com/allannoliveira/Claude-Monitor-Usage/main/install.ps1 | iex
#   OpÃ§Ãµes:  -Source <pasta ou git+https://...>   -NoAutostart
param(
    [string]$Source = "",
    [switch]$NoAutostart
)
$ErrorActionPreference = "Stop"

# Quando roda via "irm | iex" nÃ£o existe pasta do script: defina aqui o repositÃ³rio.
$DefaultRepo = "git+https://github.com/allannoliveira/Claude-Monitor-Usage"
if (-not $Source) {
    if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml"))) { $Source = $PSScriptRoot }
    else { $Source = $DefaultRepo }
}

# 1. uv (gerenciador Python que tambÃ©m baixa o Python, se faltar)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Instalando uv..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2. Copia o boneco para a pasta do usuÃ¡rio (se estiver instalando de uma pasta local)
$ConfigDir = Join-Path $env:APPDATA "claude-monitor"
New-Item -ItemType Directory -Force $ConfigDir | Out-Null
foreach ($name in "boneco.gif", "boneco.png", "boneco.ico") {
    $src = if (Test-Path $Source) { Join-Path $Source $name } else { "" }
    if ($src -and (Test-Path $src)) { Copy-Item $src $ConfigDir -Force; Write-Host "Icone copiado: $ConfigDir\$name" }
}

# 3. Instala o app como ferramenta isolada (cria claude-monitor e claude-monitor-tray)
Write-Host "Instalando claude-monitor de $Source ..."
uv tool install --force $Source
uv tool update-shell | Out-Null

# 4. Iniciar com o Windows (atalho na pasta Inicializar)
$TrayExe = Join-Path (uv tool dir --bin) "claude-monitor-tray.exe"
if (-not $NoAutostart -and (Test-Path $TrayExe)) {
    $Startup = [Environment]::GetFolderPath("Startup")
    $Shell = New-Object -ComObject WScript.Shell
    $Lnk = $Shell.CreateShortcut((Join-Path $Startup "Claude Monitor.lnk"))
    $Lnk.TargetPath = $TrayExe
    $Lnk.Save()
    Write-Host "Atalho de inicializacao criado em $Startup"
}

Write-Host ""
Write-Host "Pronto! Abra um NOVO terminal e use:"
Write-Host "  claude-monitor            (bandeja)"
Write-Host "  claude-monitor cli        (terminal)"
Write-Host "  claude-monitor cli -w     (terminal ao vivo)"
if (Test-Path $TrayExe) { Start-Process $TrayExe }
