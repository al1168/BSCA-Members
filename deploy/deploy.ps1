# Build Care Manager and publish it.
#
# From the dev machine (not on the office network):
#   .\deploy\deploy.ps1                     -> build + create GitHub release
#   .\deploy\deploy.ps1 -NoRelease          -> build only (exe in dist\)
# From a machine that CAN see the shared folder:
#   .\deploy\deploy.ps1 -ShareDir "\\SERVER\Share\CareManagerApp"
#
# The version (build date + git commit) is stamped into the exe and shown in
# the app's title bar.
param(
    [string]$ShareDir = "",
    [switch]$NoRelease
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$hash = (git rev-parse --short HEAD).Trim()
$dirty = ""
git diff --quiet; if ($LASTEXITCODE -ne 0) { $dirty = "*" }
$stamp = Get-Date -Format "yyyy.MM.dd-HHmm"
$version = "$stamp-$hash$dirty"

Set-Content -Path "_build_info.py" -Encoding utf8 -Value "APP_VERSION = `"$version`""
Write-Output "Building Care Manager $version ..."
& .venv\Scripts\pyinstaller CareManager.spec --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
$exe = Join-Path $repo "dist\Care Manager.exe"
Write-Output "Built: $exe"

if ($ShareDir) {
    if (-not (Test-Path $ShareDir)) { New-Item -ItemType Directory -Force $ShareDir | Out-Null }
    Copy-Item $exe (Join-Path $ShareDir "Care Manager.exe") -Force
    Set-Content -Path (Join-Path $ShareDir "version.txt") -Encoding utf8 -Value $version
    Write-Output "Copied to $ShareDir — office PCs get it on next launch."
} elseif (-not $NoRelease) {
    if ($dirty) { Write-Warning "Working tree has uncommitted changes; release is tagged $version" }
    $tag = "v$stamp"
    gh release create $tag $exe --title "Care Manager $version" `
        --notes "Automated build of $hash. Office side: run deploy\update-share.ps1 to publish to the shared folder."
    if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }
    Write-Output "Release $tag published. On an office PC, run deploy\update-share.ps1."
}
