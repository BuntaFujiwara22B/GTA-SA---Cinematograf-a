param([switch]$Ligero)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot '.maintenance/pyinstaller'
$pythonBuild = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonBuild)) {
    python -m venv --system-site-packages .venv-build
}
& $pythonBuild -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las herramientas de empaquetado.' }
if ($Ligero) {
    $env:MMS_BUILD_LIGHT = '1'
    & $pythonBuild tools/preparar_distribucion.py --sin-clip
} else {
    Remove-Item Env:MMS_BUILD_LIGHT -ErrorAction SilentlyContinue
    & $pythonBuild tools/preparar_distribucion.py
}
if ($LASTEXITCODE -ne 0) { throw 'Fallo al preparar recursos.' }
& $pythonBuild -m PyInstaller --noconfirm MMS-Director.spec
if ($LASTEXITCODE -ne 0) { throw 'Fallo al crear el ejecutable.' }
Copy-Item -LiteralPath README.md -Destination dist/MMS-Director
Copy-Item -LiteralPath docs -Destination dist/MMS-Director -Recurse -Force
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($iscc) {
    & $iscc.Source installer/MMS-Director.iss
}
Write-Host 'Paquete disponible en dist\MMS-Director. No copies solo el .exe: conserva sus archivos adjuntos.'
