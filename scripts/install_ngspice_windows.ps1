<#
.SYNOPSIS
  Installs a real ngspice binary for simulation/ngspice.py on Windows,
  without Administrator rights.

.DESCRIPTION
  ngspice ships no Windows installer -- the official Windows 64-bit release
  is a 7z-compressed portable folder (see ngspice.sourceforge.io/download.html).
  Windows has no built-in .7z reader (tar.exe's bsdtar cannot read this
  archive; Compress-Archive/Expand-Archive are .zip-only) and a system
  package manager needs elevation (`choco install ngspice` fails outright
  under a non-Administrator shell with an ACCESS DENIED error on
  C:\ProgramData\chocolatey\lib-bad). This script instead:
    1. Downloads the pinned ngspice-47 Windows 64-bit build.
    2. Verifies its SHA-256 against the exact copy this repo already ran
       end to end through simulation/ngspice.py's real-binary validation
       (see that module's HONEST CAVEAT / CONFIRMED note) -- not just
       "whatever the URL currently serves."
    3. Extracts it with py7zr, via a throwaway `uv run --with py7zr`
       environment (uv itself needs no elevation; the py7zr install is
       ephemeral and touches nothing outside uv's own cache).
    4. Confirms the extracted ngspice_con.exe actually runs.
    5. Prints the NGSPICE_BIN value to add to .env.

  Re-running this script is safe: it skips the download/extract steps if
  the target binary is already present and reports the right version.

.EXAMPLE
  pwsh scripts/install_ngspice_windows.ps1
#>

$ErrorActionPreference = "Stop"

$Version = "47"
$ArchiveName = "ngspice-${Version}_64.7z"
$DownloadUrl = "https://sourceforge.net/projects/ngspice/files/ng-spice-rework/$Version/$ArchiveName/download"
# SHA-256 of the exact archive this repo downloaded and validated
# simulation/ngspice.py against (RC-filter .AC sweep, real binary, 2026-09-04).
# A mismatch means SourceForge is serving something other than that verified
# file -- treat that as a reason to stop, not a reason to relax the check.
$ExpectedSha256 = "59225971BD68CDD1199443649AA4615A9E6D684933F205AB49006A3942518F5A"

$InstallRoot = Join-Path $env:LOCALAPPDATA "principal-rf-engineer\tools\ngspice-$Version"
$Spice64Dir = Join-Path $InstallRoot "Spice64"
$ConsoleExe = Join-Path $Spice64Dir "bin\ngspice_con.exe"

function Test-ExistingInstall {
    if (-not (Test-Path $ConsoleExe)) {
        return $false
    }
    $versionOutput = & $ConsoleExe -v 2>&1 | Out-String
    return $versionOutput -match "ngspice-$Version"
}

if (Test-ExistingInstall) {
    Write-Host "ngspice-$Version already installed at $ConsoleExe -- skipping download." -ForegroundColor Green
} else {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv is required to extract the .7z archive (via a throwaway py7zr environment) " +
              "and was not found on PATH. Install it first: https://docs.astral.sh/uv/getting-started/installation/"
    }

    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    $archivePath = Join-Path $InstallRoot $ArchiveName

    # Invoke-WebRequest does NOT reliably follow SourceForge's mirror-selection
    # redirect for this URL shape -- confirmed during this script's own
    # validation: it silently saved a 131KB "your download will begin
    # shortly" HTML interstitial page instead of the 13.8MB binary, with no
    # error. curl.exe (shipped with Windows 10 1803+) follows it correctly.
    if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
        throw "curl.exe is required (ships with Windows 10 1803+ / Windows 11) and was not found on PATH."
    }
    Write-Host "Downloading $DownloadUrl ..." -ForegroundColor Cyan
    & curl.exe -L --fail -o $archivePath $DownloadUrl
    if ($LASTEXITCODE -ne 0) {
        throw "curl.exe exited with code $LASTEXITCODE downloading $DownloadUrl"
    }

    $actualHash = (Get-FileHash -Path $archivePath -Algorithm SHA256).Hash
    if ($actualHash -ne $ExpectedSha256) {
        Remove-Item $archivePath -Force
        throw "SHA-256 mismatch for $ArchiveName`nExpected: $ExpectedSha256`nActual:   $actualHash`n" +
              "The download does not match the archive this repo validated -- refusing to extract it."
    }
    Write-Host "SHA-256 verified." -ForegroundColor Green

    Write-Host "Extracting with py7zr (via a throwaway uv environment) ..." -ForegroundColor Cyan
    $pythonScript = @"
import py7zr
with py7zr.SevenZipFile(r'$archivePath', mode='r') as z:
    z.extractall(path=r'$InstallRoot')
"@
    uv run --no-project --with py7zr python -c $pythonScript

    Remove-Item $archivePath -Force

    if (-not (Test-ExistingInstall)) {
        throw "Extraction completed but $ConsoleExe did not report ngspice-$Version -- something is wrong."
    }
    Write-Host "ngspice-$Version installed and verified at $ConsoleExe" -ForegroundColor Green
}

Write-Host ""
Write-Host "Add this to your .env:" -ForegroundColor Yellow
Write-Host "NGSPICE_BIN=$($ConsoleExe -replace '\\', '/')"
