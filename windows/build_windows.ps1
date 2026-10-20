<#
.SYNOPSIS
  Builds dist\MLEE_Assessment_Setup.exe. Runs on GitHub Actions (windows-2025)
  or any Windows 10/11 PC with Python 3.13 on PATH; NSIS is installed if missing.

.DESCRIPTION
  1. Stages a portable runtime: python.org embeddable CPython (x64), the pinned
     packages from requirements.txt, an app-local copy of the Microsoft C++
     runtime, and the Tectonic TeX engine.
  2. Copies the project into staging\app and builds the report once with the
     staged runtime. That run is the first test of the runtime, and it also
     fills staging\texcache so the installed copy can typeset offline.
  3. Compiles the NSIS installer and writes its SHA-256 next to it.
#>
param(
    [string]$PythonVersion = "3.13.15",
    [string]$TectonicVersion = "0.17.0",
    [string]$Version = "1.0.0"
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is slow otherwise

$Root = Split-Path -Parent $PSScriptRoot
$Stage = Join-Path $Root "staging"
$Dist = Join-Path $Root "dist"
$Tmp = Join-Path ([IO.Path]::GetTempPath()) "mlee-build"
$Py = Join-Path $Stage "python"
$Site = Join-Path $Py "Lib\site-packages"
$App = Join-Path $Stage "app"

function Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Check([string]$What) { if ($LASTEXITCODE) { throw "$What failed (exit code $LASTEXITCODE)" } }

foreach ($dir in $Stage, $Dist, $Tmp) {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
    New-Item -ItemType Directory -Force $dir | Out-Null
}

Step "Python $PythonVersion (embeddable, x64)"
$zip = Join-Path $Tmp "python.zip"
Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -OutFile $zip
Expand-Archive $zip $Py
$pth = Get-ChildItem $Py -Filter "python3*._pth" | Select-Object -First 1
$stdlib = (Get-ChildItem $Py -Filter "python3*.zip" | Select-Object -First 1).Name
# Enable site-packages; the ._pth file also keeps PYTHONPATH and other
# installations out of the bundled interpreter.
Set-Content -Path $pth.FullName -Encoding ascii -Value @($stdlib, ".", "Lib\site-packages", "import site")

Step "Python packages pinned in requirements.txt (plus pip)"
python -m pip install --disable-pip-version-check --no-cache-dir --no-compile `
    --only-binary=:all: --target $Site -r (Join-Path $Root "requirements.txt") pip
Check "pip install"
Remove-Item -Recurse -Force (Join-Path $Site "bin") -ErrorAction SilentlyContinue
# Package test suites are never imported at run time; dropping them saves ~100 MB.
foreach ($pkg in "numpy", "scipy", "pandas", "sklearn", "matplotlib") {
    Get-ChildItem (Join-Path $Site $pkg) -Recurse -Directory -Filter "tests" -ErrorAction SilentlyContinue |
        Sort-Object { $_.FullName.Length } -Descending |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Step "Microsoft C++ runtime, app-local (no redistributable install needed)"
$crt = $null
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vswhere) {
    $vs = & $vswhere -latest -products * -property installationPath
    if ($vs) {
        $crt = Get-ChildItem "$vs\VC\Redist\MSVC\*\x64\Microsoft.VC14*.CRT" -Directory -ErrorAction SilentlyContinue |
            Sort-Object FullName | Select-Object -Last 1
    }
}
if ($crt) {
    Copy-Item (Join-Path $crt.FullName "*.dll") $Py -Force
    Write-Host "    from $($crt.FullName)"
} else {
    foreach ($dll in "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_atomic_wait.dll",
                     "msvcp140_codecvt_ids.dll", "concrt140.dll", "vcruntime140.dll", "vcruntime140_1.dll") {
        Copy-Item (Join-Path "$env:SystemRoot\System32" $dll) $Py -Force -ErrorAction SilentlyContinue
    }
    Write-Host "    from System32 (Visual Studio redist folder not found)"
}

Step "Tectonic $TectonicVersion"
$tz = Join-Path $Tmp "tectonic.zip"
Invoke-WebRequest "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40$TectonicVersion/tectonic-$TectonicVersion-x86_64-pc-windows-msvc.zip" -OutFile $tz
Expand-Archive $tz (Join-Path $Stage "tectonic")

Step "Project files"
New-Item -ItemType Directory -Force (Join-Path $App "report") | Out-Null
foreach ($f in "mlee_assessment.py", "qa_check.py", "build.py", "mlee_menu.py", "requirements.txt", "README.md") {
    Copy-Item (Join-Path $Root $f) $App
}
foreach ($d in "data", "fonts", "reference") {
    Copy-Item -Recurse (Join-Path $Root $d) (Join-Path $App $d)
}
Copy-Item (Join-Path $Root "report\main.tex"), (Join-Path $Root "report\meta.tex") (Join-Path $App "report")
Copy-Item (Join-Path $PSScriptRoot "launchers\*.cmd") $Stage
foreach ($f in "mlee.ico", "Staff Guide.html", "THIRD_PARTY_NOTICES.txt") {
    Copy-Item (Join-Path $PSScriptRoot $f) $Stage
}

Step "First run with the staged runtime (also fills the offline TeX cache)"
New-Item -ItemType Directory -Force (Join-Path $Stage "texcache") | Out-Null
& (Join-Path $Py "python.exe") -s -X utf8 (Join-Path $App "build.py") --online --compare
Check "staged build"

Step "Ship a clean project folder"
foreach ($p in "build", "output", "report\figures", "report\generated", "results.json") {
    Remove-Item -Recurse -Force (Join-Path $App $p) -ErrorAction SilentlyContinue
}
Get-ChildItem $App -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force

Step "NSIS installer"
$makensis = (Get-Command makensis -ErrorAction SilentlyContinue).Source
if (-not $makensis) { $makensis = "${env:ProgramFiles(x86)}\NSIS\makensis.exe" }
if (-not (Test-Path $makensis)) {
    choco install nsis -y --no-progress | Out-Null
    $makensis = "${env:ProgramFiles(x86)}\NSIS\makensis.exe"
}
$setup = Join-Path $Dist "MLEE_Assessment_Setup.exe"
& $makensis /V2 "/DSTAGE=$Stage" "/DOUTFILE=$setup" "/DVERSION=$Version" (Join-Path $PSScriptRoot "mlee_setup.nsi")
Check "makensis"
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()
Set-Content -Path "$setup.sha256" -Encoding ascii -Value "$hash  MLEE_Assessment_Setup.exe"
$stagedMB = (Get-ChildItem $Stage -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("Built {0}: {1:N0} MB (installs {2:N0} MB), SHA-256 {3}" -f $setup, ((Get-Item $setup).Length / 1MB), $stagedMB, $hash)
