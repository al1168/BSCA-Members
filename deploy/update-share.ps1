# Pull the newest Care Manager release from GitHub into the shared folder.
# Run on any office computer that can see the share. One-time setup on that
# PC: install GitHub CLI (winget install GitHub.cli) and `gh auth login`.
#
#   .\update-share.ps1 -ShareDir "\\SERVER\Share\CareManagerApp"
#
# Can also be a Windows scheduled task (e.g. daily) for fully automatic
# updates: office PCs' launchers copy from the share on every app start.
param(
    [Parameter(Mandatory = $true)][string]$ShareDir,
    [string]$Repo = "al1168/BSCA-Members"
)
$ErrorActionPreference = "Stop"

$tmp = Join-Path $env:TEMP "care-manager-update"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
New-Item -ItemType Directory -Force $tmp | Out-Null

$tag = (gh release view --repo $Repo --json tagName -q .tagName)
if (-not $tag) { throw "No releases found in $Repo" }
Write-Output "Latest release: $tag — downloading..."
gh release download $tag --repo $Repo --pattern "*.exe" --dir $tmp
if ($LASTEXITCODE -ne 0) { throw "Download failed" }

$exe = Get-ChildItem $tmp -Filter "*.exe" | Select-Object -First 1
if (-not (Test-Path $ShareDir)) { New-Item -ItemType Directory -Force $ShareDir | Out-Null }
Copy-Item $exe.FullName (Join-Path $ShareDir "Care Manager.exe") -Force
Set-Content -Path (Join-Path $ShareDir "version.txt") -Encoding utf8 -Value $tag
Write-Output "Shared folder updated to $tag. PCs pick it up on next launch."
