# ─────────────────────────────────────────────────────────────────────────────
# build.ps1 — Збирає CourtDefense.exe
# Запуск: .\build.ps1
# Результат: dist\CourtDefense\CourtDefense.exe  + всі файли поряд
# ─────────────────────────────────────────────────────────────────────────────

Set-StrictMode -Off
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Court Defense AI — Збірка exe                     ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Перевірка Python ───────────────────────────────────────────────────
$python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $python) {
    Write-Host "[!] Python не знайдено. Встанови Python 3.10+ і повтори." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $python" -ForegroundColor Green

# ── 2. Встановлення PyInstaller якщо потрібно ────────────────────────────
$pi = python -m pyinstaller --version 2>$null
if (-not $pi) {
    Write-Host "Встановлюю PyInstaller..." -ForegroundColor Yellow
    python -m pip install pyinstaller --quiet
}
Write-Host "PyInstaller: OK" -ForegroundColor Green

# ── 3. Збірка ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Збираю exe..." -ForegroundColor Yellow

$distPath = Join-Path $Root "dist\CourtDefense"

python -m pyinstaller `
    --name "CourtDefense" `
    --onedir `
    --windowed `
    --clean `
    --noconfirm `
    --distpath "$Root\dist" `
    --workpath "$Root\build_tmp" `
    --specpath "$Root" `
    --hidden-import "tkinter" `
    --hidden-import "tkinter.ttk" `
    --hidden-import "tkinter.scrolledtext" `
    --hidden-import "tkinter.messagebox" `
    --collect-submodules "tkinter" `
    "$Root\launcher.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] PyInstaller завершився з помилкою." -ForegroundColor Red
    exit 1
}
Write-Host "exe зібрано." -ForegroundColor Green

# ── 4. Копіюємо файли додатку поруч з exe ────────────────────────────────
Write-Host ""
Write-Host "Копіюю файли додатку..." -ForegroundColor Yellow

$copy_items = @(
    "webapp",
    "requirements.txt",
    "case_config_example.py",
    "advocate_agent.py",
    "defense_master.py",
    "lawyer_analyzer.py",
    "orchestrator.py",
    "pipeline.py",
    "transcribe.py",
    "extract_pdf.py",
    "analyze_defense_v2.py",
    "import os.py",
    "import os транскрприция.py",
    "start_app.py"
)

foreach ($item in $copy_items) {
    $src = Join-Path $Root $item
    if (Test-Path $src) {
        $dst = Join-Path $distPath $item
        if (Test-Path $src -PathType Container) {
            Copy-Item $src $dst -Recurse -Force
        } else {
            Copy-Item $src $dst -Force
        }
        Write-Host "  + $item" -ForegroundColor DarkGray
    }
}

# ── 5. Копіюємо README ───────────────────────────────────────────────────
$readmeSrc = Join-Path $Root "README.txt"
if (Test-Path $readmeSrc) {
    Copy-Item $readmeSrc (Join-Path $distPath "README.txt") -Force
    Write-Host "  + README.txt" -ForegroundColor DarkGray
}

# ── 6. Підсумок ───────────────────────────────────────────────────────────
Write-Host ""
$size = (Get-ChildItem $distPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
Write-Host "╔══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║   ГОТОВО!                                           ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host ("║   Розмір: {0:N0} MB{1}║" -f [int]$size, "".PadRight(43 - "$([int]$size) MB".Length)) -ForegroundColor Green
Write-Host "║   Папка:  dist\CourtDefense\                        ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Запусти: dist\CourtDefense\CourtDefense.exe" -ForegroundColor Cyan
