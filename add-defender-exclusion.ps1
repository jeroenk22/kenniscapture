# Voegt de projectmap toe als Windows Defender-uitzondering.
#
# Nodig omdat Defender op deze server scripts zoals start.sh soms
# quarantaineert/verwijdert, waardoor ./start.sh na een git pull kan
# verdwijnen. Draai dit EENMALIG, als Administrator.
#
# Gebruik (PowerShell als Administrator):
#   .\add-defender-exclusion.ps1

$ErrorActionPreference = "Stop"

$projectPath = (Get-Item $PSScriptRoot).FullName

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Dit script moet als Administrator draaien. Sluit dit venster en start PowerShell opnieuw via 'Als administrator uitvoeren'." -ForegroundColor Red
    exit 1
}

Write-Host "Windows Defender-uitzondering toevoegen voor: $projectPath"
Add-MpPreference -ExclusionPath $projectPath

Write-Host "Klaar. Controleren..."
$exclusions = (Get-MpPreference).ExclusionPath
if ($exclusions -contains $projectPath) {
    Write-Host "Bevestigd: $projectPath staat in de Defender-uitsluitingslijst." -ForegroundColor Green
} else {
    Write-Host "Kon niet bevestigen dat de uitsluiting is toegevoegd - controleer handmatig via Windows Beveiliging." -ForegroundColor Yellow
}
