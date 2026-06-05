import os
import glob
import sys
import subprocess
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

current_dir = os.path.dirname(os.path.abspath(__file__))
ready_chunks_dir = os.path.join(current_dir, "готовые_нарезки")


# ── 0. ПРОВЕРКА И УСТАНОВКА ЗАВИСИМОСТЕЙ (CUDA + RTX 3070) ───────────────────

def check_nvidia() -> str | None:
    """Возвращает версию драйвера NVIDIA или None если не найден."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
             "--format=csv,noheader"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        return out
    except Exception:
        return None


def pip_install(packages: list[str], upgrade: bool = False) -> bool:
    print(f"  Устанавливаю: {' '.join(packages)}")
    flags = ["--quiet", "--upgrade"] if upgrade else ["--quiet"]
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install"] + flags + packages,
        capture_output=False
    )
    return result.returncode == 0


def check_and_setup_deps():
    print("=" * 65)
    print("  ПРОВЕРКА ЗАВИСИМОСТЕЙ")
    print("=" * 65)

    # — NVIDIA GPU —
    gpu_info = check_nvidia()
    if gpu_info:
        print(f"  GPU найден : {gpu_info}")
    else:
        print("  GPU        : nvidia-smi не ответил (драйвер не установлен или GPU отсутствует)")
        print("               Скачай драйвер для RTX 3070: https://www.nvidia.com/drivers")

    # — torch —
    torch_ok = False
    cuda_ok = False
    try:
        import torch
        torch_ok = True
        cuda_ok = torch.cuda.is_available()
        cuda_ver = torch.version.cuda or "нет"
        if cuda_ok:
            print(f"  torch      : {torch.__version__}  |  CUDA {cuda_ver}  |  GPU: {torch.cuda.get_device_name(0)}  OK")
        else:
            print(f"  torch      : {torch.__version__}  |  CUDA недоступна (установлена CPU-версия)")
    except ImportError:
        print("  torch      : не установлен")

    # — faster-whisper —
    import importlib.util
    whisper_ok = importlib.util.find_spec("faster_whisper") is not None
    if whisper_ok:
        print("  faster-whisper : установлен  OK")
    else:
        print("  faster-whisper : не установлен")

    if not torch_ok or (gpu_info and not cuda_ok):
        # RTX 3070, Python 3.13 — лучший доступный билд: torch 2.11.0+cu128
        print("\n  Устанавливаю torch с поддержкой CUDA 12.8 для RTX 3070 (Python 3.13)...")
        print("  (это займёт несколько минут, качается ~2.5 ГБ)")
        ok = pip_install([
            "torch==2.11.0+cu128",
            "--index-url", "https://download.pytorch.org/whl/cu128",
            "--force-reinstall",
        ])
        if ok:
            print("  torch+CUDA установлен. Перезапусти скрипт для применения.")
            input("\nEnter для выхода...")
            sys.exit(0)
        else:
            print("  Ошибка установки torch. Установи вручную:")
            print("  pip install torch==2.11.0+cu128 --index-url https://download.pytorch.org/whl/cu128 --force-reinstall")

    if not whisper_ok:
        print("\n  Устанавливаю faster-whisper...")
        ok = pip_install(["faster-whisper"])
        if ok:
            print("  faster-whisper установлен.")
        else:
            print("  Ошибка. Установи вручную: pip install faster-whisper")
            input("\nEnter для выхода...")
            sys.exit(1)

    print("=" * 65)


check_and_setup_deps()

if not os.path.exists(ready_chunks_dir):
    print(f"Папка с нарезками не найдена: {ready_chunks_dir}")
    input("\nEnter для выхода...")
    sys.exit(1)

# ── 1. АУДИТ (быстрый, без загрузки модели) ──────────────────────────────────

AUDIO_EXTENSIONS = ("*.mp3", "*.m4a", "*.wav", "*.flac", "*.aac", "*.wma")

done = []    # (audio_path, txt_path)
pending = [] # (audio_path, txt_path)

for root, dirs, files in os.walk(ready_chunks_dir):
    dirs.sort()
    for ext in AUDIO_EXTENSIONS:
        for audio_path in sorted(glob.glob(os.path.join(root, ext))):
            audio_path = os.path.abspath(audio_path)
            base, _ = os.path.splitext(audio_path)
            txt_path = base + ".txt"
            if os.path.exists(txt_path):
                done.append((audio_path, txt_path))
            else:
                pending.append((audio_path, txt_path))

# ── 2. ОТЧЁТ ─────────────────────────────────────────────────────────────────

print("=" * 65)
print("  АУДИТ ТРАНСКРИПЦИЙ — готовые_нарезки")
print("=" * 65)

print(f"\n[ГОТОВО]  {len(done)} файлов уже транскрибированы:")
for audio_path, txt_path in done:
    rel = os.path.relpath(audio_path, ready_chunks_dir)
    size_kb = os.path.getsize(txt_path) / 1024
    print(f"  + {rel}  ({size_kb:.0f} кБ txt)")

print(f"\n[ОЖИДАЮТ]  {len(pending)} файлов без транскрипции:")
if pending:
    for audio_path, txt_path in pending:
        rel = os.path.relpath(audio_path, ready_chunks_dir)
        size_mb = os.path.getsize(audio_path) / 1024 / 1024
        print(f"  - {rel}  ({size_mb:.1f} МБ)")
else:
    print("  (нет — все файлы обработаны)")

print(f"\nИтого: {len(done) + len(pending)} аудиофайлов, готово {len(done)}, осталось {len(pending)}")
print("=" * 65)

if not pending:
    print("\nВсе файлы уже транскрибированы. Нечего делать.")
    if sys.stdin.isatty():
        input("\nEnter для выхода...")
    sys.exit(0)

print(f"\nОбработать оставшиеся {len(pending)} файлов? (y/n):")
if sys.stdin.isatty():
    answer = input("> ").strip().lower()
else:
    answer = "y"
    print("> (авто-да)")
if answer not in ("y", "yes", "да", "д"):
    print("Отмена.")
    sys.exit(0)

# ── 3. ЗАГРУЗКА МОДЕЛИ (только если есть что обрабатывать) ───────────────────

try:
    from faster_whisper import WhisperModel
    import torch
except ImportError:
    print("Ошибка: не установлены библиотеки!")
    print("Выполните: pip install faster-whisper torch")
    input("\nEnter для выхода...")
    sys.exit(1)

if torch.cuda.is_available():
    device = "cuda"
    compute_type = "float16"
    print(f"\nGPU: {torch.cuda.get_device_name(0)} — запускаем на GPU")
else:
    device = "cpu"
    compute_type = "int8"
    print("\nGPU не найден — работаем на CPU (медленнее)")

print("Загрузка модели Whisper (small)...")
try:
    model = WhisperModel("small", device=device, compute_type=compute_type)
except Exception as e:
    print(f"Ошибка загрузки модели: {e}")
    input("\nEnter для выхода...")
    sys.exit(1)

# ── 4. ТРАНСКРИПЦИЯ ───────────────────────────────────────────────────────────

import shutil
import tempfile

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]"


def transcribe_safe(model, audio_path: str):
    """Копирует файл в ASCII-путь перед транскрипцией — обходит баг ffmpeg с кириллицей."""
    ext = os.path.splitext(audio_path)[1]
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.close()
    shutil.copy2(audio_path, tmp.name)
    try:
        return model.transcribe(tmp.name, beam_size=5, vad_filter=True)
    finally:
        os.unlink(tmp.name)


print(f"\n=== Транскрипция: {len(pending)} файлов ===\n")

for index, (audio_path, txt_path) in enumerate(pending, 1):
    folder_name = os.path.basename(os.path.dirname(audio_path))
    file_name = os.path.basename(audio_path)

    print(f"[{index}/{len(pending)}] {folder_name} / {file_name}")

    try:
        segments, info = transcribe_safe(model, audio_path)

        lines = [
            f"=== АУДИТ ТРАНСКРИПЦИИ ФАЙЛА: {file_name} ===",
            f"Дата обработки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Язык аудио: {info.language} (вероятность: {info.language_probability:.2f})",
            "-" * 60 + "\n",
        ]

        for segment in segments:
            line = f"{format_timestamp(segment.start)} {segment.text.strip()}"
            lines.append(line)
            print(f"  {line}")

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"  -> сохранено: {os.path.basename(txt_path)}\n")

    except Exception as e:
        print(f"  ОШИБКА: {e}\n")
        continue

print("=== Транскрипция завершена ===")
if sys.stdin.isatty():
    input("\nEnter для закрытия...")

