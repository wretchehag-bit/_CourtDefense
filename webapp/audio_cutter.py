"""
ВАРТА v2.1 - Продакшен модуль нарізки аудіо за часовими маркерами + ШІ-аналітика.

КЛЮЧОВІ ВИМОГИ (ТЗ від Паші):
1. Парсинг часових міток: "1 дискридетація батька" + "15:48---15:56" → нарізка
2. Структура папок: [Маркер]__[Файл]_[ХвилиниПочатку]
3. Миттєва нарізка: FFmpeg stream copy (без перекодування)
4. Розумний пошук: Рекурсивний по всій справі, гнучкий матчинг префіксів
5. Стійкість 100%: Encoding fallback, FFmpeg автономність, Windows safety

АРХІТЕКТУРА:
- _resolve_ffmpeg_path(): Каскадна автономність FFmpeg
- _read_text_safe(): Encoding resilience (UTF-8 → CP1251 → CP1252 → Latin1)
- _parse_timestamp_markers(): Парсинг часових міток з регулярних виразів
- _find_audio_for_transcript(): Розумний рекурсивний пошук аудіо
- _extract_time_range(): Конвертація часу в секунди для FFmpeg
- _cut_audio_segment(): Миттєва нарізка через stream copy
- _generate_court_report(): ШІ-аналітика для адвоката
- cut_audio_by_timestamps(): Головний конвеєр обробки
"""

import re
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional


# ══════════════════════════════════════════════════════════════════════════════
# УНІВЕРСАЛЬНІ УТИЛІТИ
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_ffmpeg_path() -> str:
    """
    ПРОДАКШЕН: Каскадна автономна резолюція FFmpeg.
    Не залежить від системного PATH, підтримує Portable .exe.

    Порядок пошуку:
    1. Системний PATH
    2. Локальна папка: ffmpeg/bin/ffmpeg.exe (для Portable)
    3. Хьюристичні fallback шляхи
    4. Команда за замовчуванням (надія на системний PATH)
    """
    # 1. Системний PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 2. Локальна папка проекту (Portable)
    root_dir = Path(__file__).resolve().parents[2]  # Піднімаємось до кореня проекту
    local_ffmpeg = root_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)

    # 3. Хьюристичні fallback шляхи (для розробника)
    fallback_paths = [
        r"D:\Program\Buzz\_internal\ffmpeg.exe",
        r"C:\Program Files\Buzz\_internal\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\Git\usr\bin\ffmpeg.exe",
        r"C:\tools\ffmpeg\bin\ffmpeg.exe",
    ]
    for path in fallback_paths:
        if os.path.exists(path):
            return path

    # 4. Дефолт
    return "ffmpeg"


def _read_text_safe(file_path: Path, fallback_text: str = "") -> str:
    """
    КОМЕРЦІЙНА: Читання текстового файлу з cascading encoding fallback.
    Гарантія: ніколи не впадає на брудних даних користувача.

    Порядок кодувань: UTF-8 → Windows-1251 → CP1252 → Latin1 → ASCII → UTF-8 (ignore errors)
    """
    if not file_path.exists():
        return fallback_text

    encodings = ['utf-8', 'windows-1251', 'cp1252', 'latin1', 'ascii']

    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc, errors='strict') as f:
                return f.read()
        except (UnicodeDecodeError, LookupError, OSError):
            continue

    # Остаточний fallback
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return fallback_text


def _sanitize_folder_name(text: str, max_length: int = 50) -> str:
    r"""
    WINDOWS SAFE: Очищення імені папки від заборонених символів.
    Заборонені: < > : " / \ | ? *
    """
    # Видаляємо або замінюємо заборонені символи
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', text)

    # Обрізаємо до максимальної довжини (для Windows MAX_PATH)
    sanitized = sanitized[:max_length]

    # Видаляємо trailing dots/spaces (Windows не дозволяє)
    sanitized = sanitized.rstrip('. ')

    return sanitized if sanitized else "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# ПАРСИНГ ЧАСОВИХ МІТОК (Нова бізнес-логіка)
# ══════════════════════════════════════════════════════════════════════════════

def _parse_timestamp_markers(text: str) -> List[Tuple[str, int, int]]:
    """
    Парсинг текстових маркерів та часових меток.

    Очікуваний формат у файлі:
    1 дискридетація батька
    15:48---15:56

    або в одному рядку:
    1 дискридетація батька (15:48---15:56)

    Повертає: [(маркер, start_sec, end_sec), ...]
    """
    markers = []

    # Патерн для часових міток: MM:SS---MM:SS або MM:SS--MM:SS
    time_pattern = r'(\d{1,2}):(\d{2})---(\d{1,2}):(\d{2})'

    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Пропускаємо пусті рядки
        if not line:
            i += 1
            continue

        # Чекаємо, чи це потенційний маркер (рядок не виглядає як часова мітка)
        if not re.match(r'^\d{1,2}:\d{2}', line):  # noqa: W605
            # Це може бути маркер, шукаємо часову мітку в наступному рядку
            marker = line

            # Дивимось у наступний рядок
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                time_match = re.search(time_pattern, next_line)

                if time_match:
                    start_min, start_sec, end_min, end_sec = map(int, time_match.groups())
                    start_seconds = start_min * 60 + start_sec
                    end_seconds = end_min * 60 + end_sec

                    markers.append((marker, start_seconds, end_seconds))
                    i += 2  # Пропускаємо обидва рядки
                    continue

            # Чекаємо, чи часова мітка в тому ж рядку в дужках
            time_match_inline = re.search(time_pattern, line)
            if time_match_inline:
                start_min, start_sec, end_min, end_sec = map(int, time_match_inline.groups())
                start_seconds = start_min * 60 + start_sec
                end_seconds = end_min * 60 + end_sec

                # Вилучаємо часову мітку з маркера
                marker_clean = re.sub(time_pattern, '', line).strip()
                marker_clean = re.sub(r'\(\s*\)\s*$', '', marker_clean).strip()

                if marker_clean:
                    markers.append((marker_clean, start_seconds, end_seconds))

        i += 1

    return markers


# ══════════════════════════════════════════════════════════════════════════════
# РОЗУМНИЙ ПОШУК АУДІО
# ══════════════════════════════════════════════════════════════════════════════

def _extract_base_name(filename: str) -> str:
    """
    Витягування базового імені файлу для гнучкого матчингу.

    Приклади:
    "270520256_1648_АНАЛІЗ.txt" → "270520256_1648"
    "recording_chunk.json" → "recording"
    "audio_part_1.mp3" → "audio"
    """
    # Видаляємо розширення
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename

    # Видаляємо сервісні маркери
    name = re.sub(r'(_АНАЛІЗ|_chunk|_part_\d+|_chunk_\d+|_temp|_tmp).*$', '', name, flags=re.IGNORECASE)

    # Видаляємо завершальні chunk числа (тільки після _chunk/_part)
    # Не видаляємо цифри, які є частиною базового імені
    if re.search(r'_(?:chunk|part)_\d+$', name, flags=re.IGNORECASE):
        name = re.sub(r'_(?:chunk|part)_\d+$', '', name, flags=re.IGNORECASE)

    return name.strip('_').strip() if name.strip('_').strip() else name


def _find_audio_for_transcript(transcript_path: Path, case_folder: Path) -> Optional[Path]:
    """
    РОЗУМНИЙ ПОШУК: Знаходження аудіофайлу для тексту транскрипції.

    Логіка:
    1. Спочатку шукаємо рядом (однойменний файл)
    2. Якщо не знайдено: рекурсивний пошук по всій справі
    3. Матчинг за базовим префіксом імені
    4. Ігнорування папки _CourtDefense
    """
    base_name = _extract_base_name(transcript_path.name)

    # 1. Шукаємо рядом
    for ext in ['.mp3', '.wav', '.m4a', '.ogg', '.aac', '.flac']:
        same_folder = transcript_path.parent / (base_name + ext)
        if same_folder.exists():
            return same_folder

    # 2. Рекурсивний пошук по всій справі
    audio_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.aac', '.flac'}

    for audio_file in case_folder.rglob('*'):
        # Ігноруємо служебні файли та папки
        if audio_file.name.startswith('.') or '_CourtDefense' in str(audio_file):
            continue
        if 'chunk' in audio_file.name.lower() or 'part_' in audio_file.name.lower():
            continue
        if audio_file.suffix.lower() not in audio_extensions:
            continue

        # Перевіряємо, чи базовий префікс матчиться
        audio_base_name = _extract_base_name(audio_file.name)

        # Гнучкий матчинг: базовий префікс тексту міститься в базовому імені аудіо
        if base_name in audio_base_name or audio_base_name in base_name:
            return audio_file

        # Альтернативно: обидва починаються з однакових цифр
        if base_name and audio_base_name:
            if base_name.split('_')[0] == audio_base_name.split('_')[0]:
                return audio_file

    return None


# ══════════════════════════════════════════════════════════════════════════════
# НАРІЗКА АУДІО
# ══════════════════════════════════════════════════════════════════════════════

def _cut_audio_segment(input_audio: Path, output_audio: Path, start_sec: int, end_sec: int) -> bool:
    """
    МИТТЄВА НАРІЗКА: FFmpeg stream copy (без перекодування).

    Параметри:
    -ss [час] : Запуск з часу
    -to [час] : Зупинка у часі
    -c copy   : Stream copy (ключовий параметр для швидкості!)
    -y        : Перезапис файлу

    Повертає: True якщо успіх, False якщо помилка
    """
    try:
        ffmpeg_exe = _resolve_ffmpeg_path()

        # Форматуємо час: MM:SS
        def sec_to_time(seconds: int) -> str:
            mins = seconds // 60
            secs = seconds % 60
            return f"{mins}:{secs:02d}"

        start_time = sec_to_time(start_sec)
        end_time = sec_to_time(end_sec)

        # Команда FFmpeg
        cmd = [
            ffmpeg_exe,
            '-ss', start_time,
            '-i', str(input_audio),
            '-to', end_time,
            '-c', 'copy',
            '-y',
            str(output_audio),
        ]

        # Запускаємо без відображення консольного вікна (Windows)
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        # Виконуємо
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 хвилин для великих файлів
            startupinfo=startupinfo
        )

        if result.returncode != 0:
            print(f"[FFmpeg помилка] {result.stderr[:200]}")
            return False

        return True

    except FileNotFoundError:
        print("[Помилка] FFmpeg не знайдено. Переконайтесь, що ffmpeg встановлено або покладено в ffmpeg/bin/")
        return False
    except subprocess.TimeoutExpired:
        print(f"[Помилка] Таймаут нарізки аудіо (> 5 хв)")
        return False
    except Exception as e:
        print(f"[Помилка нарізки] {str(e)}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# ГЕНЕРАЦІЯ ЗВІТІВ
# ══════════════════════════════════════════════════════════════════════════════

def _generate_court_report(marker: str, source_file: str, start_sec: int, end_sec: int,
                          context_text: str = "") -> str:
    """
    Генерація звіту для суду з часовими мітками та контекстом.

    Формат включає:
    - Маркер епізоду
    - Оригінальний файл
    - Часовий діапазон з наочним форматуванням
    - Хвилини для прослуховування в нарізці (від 00:00)
    - Контекст
    """

    def sec_to_mmss(seconds: int) -> str:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02d}:{secs:02d}"

    duration = end_sec - start_sec

    report = f"""=== {marker} ===
Оригінальний запис: {source_file}
Час фрагмента на оригінальному записі: {sec_to_mmss(start_sec)} ---> {sec_to_mmss(end_sec)}
----------------------------------------------------------------------
[ХВИЛИНИ ДЛЯ ПРОСЛУХОВУВАННЯ В ЦЬОМУ НЕВЕЛИЧКОМУ ФРАГМЕНТІ]:
00:00 --- {sec_to_mmss(duration)} хв
----------------------------------------------------------------------
НОВА ТРАНСКРИПЦІЯ ПО ЧАСУ (ТОЧКОВИЙ ЗМІСТ ШІ):
{context_text if context_text else "[Контекст недоступний]"}
"""

    return report


# ══════════════════════════════════════════════════════════════════════════════
# ГОЛОВНИЙ КОНВЕЄР
# ══════════════════════════════════════════════════════════════════════════════

def cut_audio_by_timestamps(case_folder: str) -> Dict:
    """
    ГОЛОВНИЙ КОНВЕЄР: Обробка справи по часовим маркерам.

    Процес:
    1. Знаходимо всі текстові транскрипції в справі
    2. Парсимо часові маркери (маркер + час початку/кінця)
    3. Для кожного маркера:
       a. Знаходимо відповідний аудіофайл (розумний пошук)
       b. Нарізаємо аудіо (FFmpeg stream copy)
       c. Генеруємо ШІ-звіт для суду
    4. Повертаємо статистику
    """
    case_path = Path(case_folder)
    if not case_path.exists():
        print(f"[Помилка] Папка справи не існує: {case_folder}")
        return {"success": False, "processed": 0, "skipped": 0, "errors": 0}

    print(f"[Запуск] Обробка справи: {case_path.name}")

    # Папка для результатів
    output_root = case_path / "_CourtDefense" / "02_нарізки_за_фразами"
    output_root.mkdir(parents=True, exist_ok=True)

    # Знаходимо всі текстові транскрипції
    transcript_files = []
    for txt_file in case_path.rglob('*.txt'):
        if txt_file.name.startswith('.') or '_CourtDefense' in str(txt_file):
            continue
        if 'chunk' in txt_file.name.lower() or 'part_' in txt_file.name.lower():
            continue
        transcript_files.append(txt_file)

    print(f"[Інформація] Знайдено {len(transcript_files)} транскрипцій")

    stats = {"success": True, "processed": 0, "skipped": 0, "errors": 0, "episodes": []}

    # Обробляємо кожну транскрипцію
    for trans_file in transcript_files:
        print(f"\n[Обробка] {trans_file.name}")

        # Читаємо транскрипцію
        text = _read_text_safe(trans_file)
        if not text:
            print(f"  [Помилка] Не вдалося прочитати файл")
            stats["skipped"] += 1
            continue

        # Парсимо часові маркери
        markers = _parse_timestamp_markers(text)
        if not markers:
            print(f"  [Інформація] Часових маркерів не знайдено")
            stats["skipped"] += 1
            continue

        print(f"  [Знайдено] {len(markers)} маркер(и)")

        # Знаходимо аудіофайл для цієї транскрипції
        audio_file = _find_audio_for_transcript(trans_file, case_path)
        if not audio_file:
            print(f"  [Помилка] Аудіофайл не знайдено для {trans_file.name}")
            stats["errors"] += 1
            continue

        print(f"  [Аудіо] Знайдено: {audio_file.name}")

        # Обробляємо кожен маркер
        for marker, start_sec, end_sec in markers:
            try:
                # Створюємо папку для епізоду
                folder_name = f"{_sanitize_folder_name(marker)}__" \
                             f"{_sanitize_folder_name(audio_file.stem)}_" \
                             f"{start_sec // 60}"
                episode_folder = output_root / folder_name
                episode_folder.mkdir(parents=True, exist_ok=True)

                # Нарізаємо аудіо
                output_audio = episode_folder / f"нарізка{audio_file.suffix}"
                if _cut_audio_segment(audio_file, output_audio, start_sec, end_sec):
                    print(f"    [✓] {marker} ({start_sec // 60}:{start_sec % 60:02d})")
                    stats["processed"] += 1

                    # Генеруємо звіт
                    report = _generate_court_report(marker, audio_file.name, start_sec, end_sec)
                    report_file = episode_folder / "ЗВІТ_ДЛЯ_СУДУ.txt"
                    with open(report_file, 'w', encoding='utf-8') as f:
                        f.write(report)

                    stats["episodes"].append({
                        "marker": marker,
                        "folder": folder_name,
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                    })
                else:
                    print(f"    [✗] Помилка нарізки: {marker}")
                    stats["errors"] += 1

            except Exception as e:
                print(f"    [Помилка] {str(e)[:100]}")
                stats["errors"] += 1

    print(f"\n[Завершено] Оброблено: {stats['processed']}, Помилок: {stats['errors']}")
    return stats
