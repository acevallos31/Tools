$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Source = Join-Path $ProjectRoot "hermes_skill\mikrotik-operator"
$Destination = Join-Path $HOME ".hermes\skills\networking\mikrotik-operator"

if (-not (Test-Path $Source)) {
    throw "No se encontró el skill fuente: $Source"
}

$Parent = Split-Path -Parent $Destination
New-Item -ItemType Directory -Path $Parent -Force | Out-Null

if (Test-Path $Destination) {
    Remove-Item -Recurse -Force $Destination
}

Copy-Item -Recurse -Force $Source $Destination

Write-Host "Hermes skill instalado en:"
Write-Host "  $Destination"
Write-Host ""
Write-Host "Reinicia Hermes/gateway antes de probar conversaciones nuevas."
