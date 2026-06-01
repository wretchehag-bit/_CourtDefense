"""
pipeline.py — Мастер-конвейер
Этапы: Обнаружение → Нарезка (ffmpeg) → Транскрипция (Whisper) → Сортировка → Анализ (Claude)
"""
import os, sys, glob, zipfile, tempfile, shutil, subprocess, re
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(SCRIPT_DIR)
CHUNKS_DIR   = os.path.join(SCRIPT_DIR, "готовые_нарезки")
SORTED_DIR   = os.path.join(SCRIPT_DIR, "Отсортированные_данные_для_суда")
LOG_FILE     = os.path.join(SCRIPT_DIR, "processed_files.log")  # общий с нарезчиком

AUDIO_EXTS   = ('.mp3', '.m4a', '.wav', '.flac', '.wma', '.ogg', '.aac')
CHUNK_MIN    = 20
SKIP_ZIP_KW  = ("buzz", "whisper", "ilovepdf")
SKIP_DIRS    = {"нарезки", "Buzz-1.4.4-Windows-X64", "Whisper-master",
                "ilovepdf_extracted-pages (1)", "ilovepdf_extracted-pages"}
SEP          = "=" * 70


# ── ЗАВИСИМОСТИ ──────────────────────────────────────────────────────────────

def setup():
    print(SEP)
    print("  ЗАВИСИМОСТИ")
    print(SEP)

    # imageio-ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"  ffmpeg     : {ffmpeg}  OK")
    except ImportError:
        print("  Устанавливаю imageio-ffmpeg...")
        subprocess.run([sys.executable, "-m", "pip", "install", "imageio-ffmpeg", "--quiet"], check=True)
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"  ffmpeg     : установлен  OK")

    # GPU/CUDA
    cuda_ok = False
    device, compute = "cpu", "int8"
    try:
        import torch
        if torch.cuda.is_available():
            cuda_ok = True
            device, compute = "cuda", "float16"
            print(f"  torch/GPU  : {torch.cuda.get_device_name(0)}  OK")
        else:
            print(f"  torch      : {torch.__version__}, CUDA недоступна — работаем на CPU")
    except ImportError:
        print("  torch      : не установлен — будет CPU")

    # faster-whisper
    import importlib.util
    if importlib.util.find_spec("faster_whisper") is None:
        print("  Устанавливаю faster-whisper...")
        subprocess.run([sys.executable, "-m", "pip", "install", "faster-whisper", "--quiet"], check=True)
    print("  faster-whisper : OK")

    print(SEP + "\n")
    return ffmpeg, device, compute


# ── ЛОГ ──────────────────────────────────────────────────────────────────────

def get_processed():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}

def mark_processed(identity):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(identity + "\n")


# ── ОБНАРУЖЕНИЕ ИСТОЧНИКОВ ───────────────────────────────────────────────────

def discover_sources():
    """Собирает все аудиофайлы: корень + подпапки + ZIP-архивы."""
    items = []
    seen_ids  = set()
    seen_names = set()  # дедупликация одинаковых файлов из разных ZIP

    def add(item):
        if item["identity"] not in seen_ids:
            seen_ids.add(item["identity"])
            items.append(item)

    # 1. Файлы прямо в корне
    for fname in sorted(os.listdir(ROOT_DIR)):
        fpath = os.path.join(ROOT_DIR, fname)
        if os.path.isfile(fpath) and fname.lower().endswith(AUDIO_EXTS):
            seen_names.add(fname)
            add({"identity": fname, "label": fname,           # совместимо с processed_files.log
                 "type": "local", "path": fpath,
                 "size": os.path.getsize(fpath)})

    # 2. Подпапки корня (01.06.2026 и другие, кроме служебных)
    for dname in sorted(os.listdir(ROOT_DIR)):
        dpath = os.path.join(ROOT_DIR, dname)
        if not os.path.isdir(dpath) or dname in SKIP_DIRS:
            continue
        for fname in sorted(os.listdir(dpath)):
            fpath = os.path.join(dpath, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(AUDIO_EXTS):
                if fname in seen_names:          # тот же файл уже есть в корне
                    continue
                seen_names.add(fname)
                identity = f"{dname}/{fname}"
                add({"identity": identity, "label": f"{dname}/{fname}",
                     "type": "local", "path": fpath,
                     "size": os.path.getsize(fpath)})

    # 3. ZIP-архивы в корне
    for zpath in sorted(glob.glob(os.path.join(ROOT_DIR, "*.zip"))):
        zname = os.path.basename(zpath)
        if any(kw in zname.lower() for kw in SKIP_ZIP_KW):
            continue
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                for zi in zf.infolist():
                    if not zi.filename.lower().endswith(AUDIO_EXTS):
                        continue
                    inner_name = os.path.basename(zi.filename)
                    if inner_name in seen_names:     # дубликат из другого ZIP или корня
                        continue
                    seen_names.add(inner_name)
                    identity = f"{zname}::{zi.filename}"   # совместимо с processed_files.log
                    add({"identity": identity,
                         "label": f"[{zname}] {zi.filename}",
                         "type": "zip",
                         "zip_path": zpath,
                         "internal_name": zi.filename,
                         "size": zi.file_size})
        except Exception as e:
            print(f"  Ошибка чтения {zname}: {e}")

    return items


# ── ФАЗА 1: НАРЕЗКА (ffmpeg) ─────────────────────────────────────────────────

def get_duration(ffmpeg, path):
    r = subprocess.run([ffmpeg, "-i", path], capture_output=True)
    for line in r.stderr.decode("utf-8", errors="replace").splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    return None


def split_audio(ffmpeg, input_path, out_dir, ext):
    dur = get_duration(ffmpeg, input_path)
    chunk_sec = CHUNK_MIN * 60

    if dur is None:
        print("    Длительность неизвестна — копирую как один файл")
        out = os.path.join(out_dir, f"part_00_chunk{ext}")
        shutil.copy2(input_path, out)
        return [out]

    parts = max(1, int(dur // chunk_sec) + (1 if dur % chunk_sec > 0 else 0))
    print(f"    Длительность: {dur/60:.1f} мин → {parts} часть(ей) по {CHUNK_MIN} мин")

    if parts == 1:
        out = os.path.join(out_dir, f"part_00_chunk{ext}")
        r = subprocess.run(
            [ffmpeg, "-i", input_path, "-c", "copy", "-movflags", "+faststart", out, "-y"],
            capture_output=True)
        if r.returncode != 0:
            shutil.copy2(input_path, out)
        return [out]

    pattern = os.path.join(out_dir, f"part_%02d_chunk{ext}")
    r = subprocess.run(
        [ffmpeg, "-i", input_path,
         "-f", "segment", "-segment_time", str(chunk_sec),
         "-c", "copy", "-reset_timestamps", "1", "-movflags", "+faststart",
         pattern, "-y"],
        capture_output=True)
    if r.returncode != 0:
        print(f"    ffmpeg ошибка: {r.stderr.decode('utf-8', errors='replace')[-300:]}")

    created = sorted(glob.glob(os.path.join(out_dir, f"part_*_chunk{ext}")))
    for f in created:
        print(f"    + {os.path.basename(f)}  ({os.path.getsize(f)/1024/1024:.1f} МБ)")
    return created


def phase_split(ffmpeg, pending):
    print(f"\n{'─'*70}")
    print(f"  ФАЗА 1 — НАРЕЗКА: {len(pending)} новых файлов")
    print(f"{'─'*70}")

    os.makedirs(CHUNKS_DIR, exist_ok=True)

    for idx, item in enumerate(pending, 1):
        print(f"\n  [{idx}/{len(pending)}] {item['label']}")
        tmp_dir = None
        try:
            if item["type"] == "zip":
                tmp_dir = tempfile.mkdtemp()
                input_path = zipfile.ZipFile(item["zip_path"]).extract(
                    item["internal_name"], tmp_dir)
            else:
                input_path = item["path"]

            base, ext = os.path.splitext(os.path.basename(input_path))
            safe = re.sub(r'[^\w\s\-]', '_', base).strip()
            ts = datetime.now().strftime("%H-%M-%S")
            out_dir = os.path.join(CHUNKS_DIR, f"{ts}_{safe}")
            os.makedirs(out_dir, exist_ok=True)

            created = split_audio(ffmpeg, input_path, out_dir, ext.lower())
            if created:
                mark_processed(item["identity"])
                print(f"    -> {len(created)} файл(ов) в {os.path.basename(out_dir)}")
            else:
                print("    ОШИБКА: файлы не созданы")

        except Exception as e:
            print(f"    ОШИБКА: {e}")
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)


# ── ФАЗА 2: ТРАНСКРИПЦИЯ (Whisper) ───────────────────────────────────────────

def fmt_ts(sec):
    return f"[{int(sec//3600):02d}:{int((sec%3600)//60):02d}:{int(sec%60):02d}]"


def transcribe_safe(model, audio_path):
    ext = os.path.splitext(audio_path)[1]
    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.close()
    shutil.copy2(audio_path, tmp.name)
    try:
        return model.transcribe(tmp.name, beam_size=5, vad_filter=True)
    finally:
        os.unlink(tmp.name)


def phase_transcribe(device, compute):
    print(f"\n{'─'*70}")
    print(f"  ФАЗА 2 — ТРАНСКРИПЦИЯ (Whisper)")
    print(f"{'─'*70}")

    pending = []
    for root, dirs, files in os.walk(CHUNKS_DIR):
        dirs.sort()
        for fname in sorted(files):
            if fname.lower().endswith(AUDIO_EXTS):
                audio = os.path.abspath(os.path.join(root, fname))
                txt   = os.path.splitext(audio)[0] + ".txt"
                if not os.path.exists(txt):
                    pending.append((audio, txt))

    if not pending:
        print("  Все файлы уже транскрибированы.")
        return

    print(f"  Без транскрипции: {len(pending)} файлов")
    print(f"  Устройство: {device.upper()}, compute_type: {compute}")
    print("  Загрузка модели Whisper (small)...")

    from faster_whisper import WhisperModel
    model = WhisperModel("small", device=device, compute_type=compute)

    for idx, (audio, txt) in enumerate(pending, 1):
        folder_name = os.path.basename(os.path.dirname(audio))
        print(f"\n  [{idx}/{len(pending)}] {folder_name}/{os.path.basename(audio)}")
        try:
            segments, info = transcribe_safe(model, audio)
            lines = [
                f"=== ТРАНСКРИПЦИЯ: {os.path.basename(audio)} ===",
                f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Язык: {info.language} (вероятность: {info.language_probability:.2f})",
                "-" * 60, "",
            ]
            for seg in segments:
                line = f"{fmt_ts(seg.start)} {seg.text.strip()}"
                lines.append(line)
                print(f"    {line}")
            with open(txt, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"    -> сохранено: {os.path.basename(txt)}")
        except Exception as e:
            print(f"    ОШИБКА: {e}")


# ── ФАЗА 3: СОРТИРОВКА ───────────────────────────────────────────────────────

def extract_date(s):
    m = re.search(r'\d{8}_\d{6}', s)
    return m.group(0) if m else None

def clean_str(s):
    return re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁіІїЇєЄ]', '', s).lower()


def phase_organize():
    print(f"\n{'─'*70}")
    print(f"  ФАЗА 3 — СОРТИРОВКА")
    print(f"{'─'*70}")

    os.makedirs(SORTED_DIR, exist_ok=True)

    # Индекс оригиналов: дата → путь
    orig_by_date = {}
    orig_by_name = {}
    for entry in os.scandir(ROOT_DIR):
        if entry.is_file() and entry.name.lower().endswith(AUDIO_EXTS):
            d = extract_date(entry.name)
            if d:
                orig_by_date[d] = entry.path
            orig_by_name[clean_str(os.path.splitext(entry.name)[0])] = entry.path
    # Файлы из подпапок
    for dname in os.listdir(ROOT_DIR):
        dpath = os.path.join(ROOT_DIR, dname)
        if os.path.isdir(dpath) and dname not in SKIP_DIRS:
            for fname in os.listdir(dpath):
                fpath = os.path.join(dpath, fname)
                if os.path.isfile(fpath) and fname.lower().endswith(AUDIO_EXTS):
                    d = extract_date(fname)
                    if d:
                        orig_by_date[d] = fpath
                    orig_by_name[clean_str(os.path.splitext(fname)[0])] = fpath

    subfolders = sorted([
        d for d in os.listdir(CHUNKS_DIR)
        if os.path.isdir(os.path.join(CHUNKS_DIR, d))
    ])

    moved, skipped = 0, 0
    for sf in subfolders:
        # убираем временной префикс вида "HH-MM-SS_"
        parts = sf.split("_", 1)
        case_name = parts[1] if len(parts) > 1 and parts[0].replace("-","").isdigit() and len(parts[0]) == 6 else sf

        case_dir   = os.path.join(SORTED_DIR, case_name)
        chunks_sub = os.path.join(case_dir, "папка_с_нарезками")
        transc_sub = os.path.join(case_dir, "папка_с_транскрипцией")
        os.makedirs(chunks_sub, exist_ok=True)
        os.makedirs(transc_sub, exist_ok=True)

        # Копируем оригинал если найден
        date = extract_date(case_name)
        orig = orig_by_date.get(date) or orig_by_name.get(clean_str(case_name))
        if orig:
            dest = os.path.join(case_dir, os.path.basename(orig))
            if not os.path.exists(dest):
                shutil.copy2(orig, dest)

        # Копируем чанки и транскрипции
        sf_path = os.path.join(CHUNKS_DIR, sf)
        for item in os.listdir(sf_path):
            if os.path.isdir(os.path.join(sf_path, item)):
                continue
            src = os.path.join(sf_path, item)
            if item.lower().endswith(".txt"):
                dst = os.path.join(transc_sub, item)
            elif item.lower().endswith(AUDIO_EXTS):
                dst = os.path.join(chunks_sub, item)
            else:
                continue
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                moved += 1
            else:
                skipped += 1

    print(f"  Скопировано файлов: {moved} | Уже были: {skipped}")
    print(f"  Папок в архиве: {len(subfolders)}")


# ── ФАЗА 4: АНАЛИЗ (Claude) ──────────────────────────────────────────────────

def phase_analyze():
    analyze_script = os.path.join(SCRIPT_DIR, "analyze_defense.py")
    if not os.path.exists(analyze_script):
        print("  analyze_defense.py не найден — пропускаю.")
        return
    print("  Запускаю analyze_defense.py...")
    subprocess.run([sys.executable, analyze_script])


# ── ГЛАВНЫЙ ЦИКЛ ─────────────────────────────────────────────────────────────

def main():
    print(SEP)
    print("  МАСТЕР-КОНВЕЙЕР")
    print(SEP)
    print(f"  Корень    : {ROOT_DIR}")
    print(f"  Нарезки   : {CHUNKS_DIR}")
    print(f"  Архив     : {SORTED_DIR}")
    print()

    ffmpeg, device, compute = setup()

    # Обнаружение
    print(f"{'─'*70}")
    print("  ОБНАРУЖЕНИЕ ИСТОЧНИКОВ")
    print(f"{'─'*70}")
    all_sources = discover_sources()
    processed   = get_processed()
    pending     = [s for s in all_sources if s["identity"] not in processed]

    print(f"\n  Всего источников : {len(all_sources)}")
    print(f"  Уже нарезано     : {len(processed)}")
    print(f"  Новых в очереди  : {len(pending)}")

    if pending:
        print(f"\n  Новые файлы:")
        for s in pending:
            mb = s["size"] / 1024 / 1024
            print(f"    - {s['label']}  ({mb:.1f} МБ)")

    # Подтверждение
    print()
    total_mb = sum(s["size"] for s in pending) / 1024 / 1024
    if pending:
        print(f"  Суммарный объём для нарезки: {total_mb:.0f} МБ")
    print("  Запустить полный конвейер? (y/n)  [Enter = y]:")
    answer = input("  > ").strip().lower() or "y"
    if answer not in ("y", "yes", "да", "д"):
        print("  Отмена.")
        return

    # Фазы
    if pending:
        phase_split(ffmpeg, pending)
    else:
        print("\n  [ФАЗА 1] Нарезка — всё уже обработано, пропускаю.")

    phase_transcribe(device, compute)
    phase_organize()

    # Анализ — опционально
    print(f"\n{'─'*70}")
    print("  ФАЗА 4 — ЮРИДИЧЕСКИЙ АНАЛИЗ (Claude Opus)")
    print(f"{'─'*70}")
    print("  Запустить analyze_defense.py? (y/n)  [Enter = n]:")
    if (input("  > ").strip().lower() or "n") in ("y", "yes", "да", "д"):
        phase_analyze()
    else:
        print("  Анализ пропущен.")

    print(f"\n{SEP}")
    print("  КОНВЕЙЕР ЗАВЕРШЁН")
    print(SEP)
    print(f"  Нарезки   : {CHUNKS_DIR}")
    print(f"  Архив     : {SORTED_DIR}")
    if os.path.exists(os.path.join(SCRIPT_DIR, "DEFENSE_ANALYSIS.txt")):
        print(f"  Анализ    : {os.path.join(SCRIPT_DIR, 'DEFENSE_ANALYSIS.txt')}")

    if sys.stdin.isatty():
        input("\n  Enter для закрытия...")


if __name__ == "__main__":
    main()
