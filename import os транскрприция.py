import os
import glob
import zipfile
import tempfile
import shutil
import sys
import subprocess
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ── Пути ──────────────────────────────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
folder = os.path.dirname(current_dir) if os.path.basename(current_dir) == "нарезки" else current_dir
LOG_FILE_PATH = os.path.join(current_dir, "processed_files.log")

# ── ffmpeg (bundled) ───────────────────────────────────────────────────────────
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    print("Устанавливаю imageio-ffmpeg...")
    subprocess.run([sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "--quiet"])
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

AUDIO_EXTENSIONS = ('.mp3', '.m4a', '.wav', '.flac', '.wma', '.ogg', '.aac')
CHUNK_MINUTES = 20


# ── Лог ───────────────────────────────────────────────────────────────────────
def get_processed():
    if not os.path.exists(LOG_FILE_PATH):
        return set()
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        return set(l.strip() for l in f if l.strip())

def mark_processed(identity):
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(f"{identity}\n")


# ── Сбор файлов ───────────────────────────────────────────────────────────────
def collect_items():
    items = []
    seen = set()

    for ext in AUDIO_EXTENSIONS:
        for fp in glob.glob(os.path.join(folder, f"*{ext}")) + glob.glob(os.path.join(folder, f"*{ext.upper()}")):
            name = os.path.basename(fp)
            if name not in seen:
                seen.add(name)
                items.append({'type': 'local', 'identity': name, 'name': name,
                               'path': fp, 'size': os.path.getsize(fp)})

    for zp in glob.glob(os.path.join(folder, "*.zip")) + glob.glob(os.path.join(folder, "*.ZIP")):
        try:
            with zipfile.ZipFile(zp, 'r') as z:
                for zi in z.infolist():
                    if zi.filename.lower().endswith(AUDIO_EXTENSIONS):
                        identity = f"{os.path.basename(zp)}::{zi.filename}"
                        if identity not in seen:
                            seen.add(identity)
                            items.append({'type': 'zip', 'identity': identity,
                                          'name': f"[{os.path.basename(zp)}] {zi.filename}",
                                          'zip_path': zp, 'internal_name': zi.filename,
                                          'size': zi.file_size})
        except Exception as e:
            print(f"  Ошибка архива {os.path.basename(zp)}: {e}")
    return items


# ── ffmpeg: длительность ──────────────────────────────────────────────────────
def get_duration(path):
    r = subprocess.run(
        [FFMPEG, '-i', path],
        capture_output=True
    )
    for line in r.stderr.decode('utf-8', errors='replace').splitlines():
        if 'Duration:' in line:
            t = line.strip().split('Duration:')[1].split(',')[0].strip()
            h, m, s = t.split(':')
            return float(h) * 3600 + float(m) * 60 + float(s)
    return None


# ── ffmpeg: нарезка ───────────────────────────────────────────────────────────
def split_with_ffmpeg(input_path, output_folder, ext):
    duration = get_duration(input_path)
    if duration is None:
        print(f"  Не удалось определить длительность, копирую как есть...")
        out = os.path.join(output_folder, f"part_01_chunk{ext.lower()}")
        shutil.copy2(input_path, out)
        return [out]

    chunk_sec = CHUNK_MINUTES * 60
    parts = max(1, int(duration // chunk_sec) + (1 if duration % chunk_sec > 0 else 0))
    print(f"  Длительность: {duration/60:.1f} мин → {parts} частей по {CHUNK_MINUTES} мин")

    created = []
    if parts == 1:
        out = os.path.join(output_folder, f"part_01_chunk{ext.lower()}")
        r = subprocess.run(
            [FFMPEG, '-i', input_path, '-c', 'copy', '-movflags', '+faststart', out, '-y'],
            capture_output=True
        )
        if r.returncode == 0:
            created.append(out)
        else:
            # fallback: copy raw
            shutil.copy2(input_path, out)
            created.append(out)
    else:
        pattern = os.path.join(output_folder, f"part_%02d_chunk{ext.lower()}")
        r = subprocess.run(
            [FFMPEG, '-i', input_path,
             '-f', 'segment', '-segment_time', str(chunk_sec),
             '-c', 'copy', '-reset_timestamps', '1', '-movflags', '+faststart',
             pattern, '-y'],
            capture_output=True
        )
        if r.returncode != 0:
            print(f"  ffmpeg error: {r.stderr.decode('utf-8', errors='replace')[-200:]}")

        for f in sorted(glob.glob(os.path.join(output_folder, f"part_*_chunk{ext.lower()}"))):
            created.append(f)

    for f in created:
        print(f"  + {os.path.basename(f)}  ({os.path.getsize(f)/1024/1024:.1f} МБ)")
    return created


# ── ГЛАВНЫЙ ЦИКЛ ──────────────────────────────────────────────────────────────
print("=" * 65)
print("  КОНВЕЙЕР НАРЕЗКИ — аудио по 20 минут (ffmpeg)")
print("=" * 65)

all_items = collect_items()
processed = get_processed()
pending = [i for i in all_items if i['identity'] not in processed]

print(f"\n[ГОТОВО]   {len(processed)} файлов уже нарезаны")
print(f"[ОЖИДАЮТ]  {len(pending)} файлов в очереди:")
for item in pending:
    mb = item['size'] / 1024 / 1024
    print(f"  - {item['name']}  ({mb:.1f} МБ)")

if not pending:
    print("\nВсе файлы обработаны!")
    input("\nEnter для выхода...")
    sys.exit(0)

print(f"\nОбработать {len(pending)} файлов? (y/n):")
if sys.stdin.isatty():
    answer = input("> ").strip().lower()
else:
    answer = "y"
    print("> (авто-да)")
if answer not in ("y", "yes", "да", "д"):
    print("Отмена.")
    sys.exit(0)

print("=" * 65)

for idx, item in enumerate(pending, 1):
    print(f"\n[{idx}/{len(pending)}] {item['name']}")

    # Распаковка ZIP
    tmp_dir = None
    if item['type'] == 'zip':
        tmp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(item['zip_path'], 'r') as z:
            input_path = z.extract(item['internal_name'], tmp_dir)
    else:
        input_path = item['path']

    base_name, ext = os.path.splitext(os.path.basename(input_path))
    clean_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in base_name).strip()
    timestamp = datetime.now().strftime("%H-%M-%S")
    output_folder = os.path.join(current_dir, "готовые_нарезки", f"{timestamp}_{clean_name}")
    os.makedirs(output_folder, exist_ok=True)

    try:
        created = split_with_ffmpeg(input_path, output_folder, ext)
        print(f"  -> {len(created)} файл(ов) в {output_folder}")
        mark_processed(item['identity'])
    except Exception as e:
        print(f"  ОШИБКА: {e}")
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

print("\n=== Готово ===")
if sys.stdin.isatty():
    input("\nEnter для закрытия...")
