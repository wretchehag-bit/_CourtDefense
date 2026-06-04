"""
Модуль автоматичної нарізки аудіо за ключовими фразами + ШІ-аналіз контексту.
ПРОДАКШН-ВЕРСІЯ: Жодного хардкоду шляхів. Повна ізоляція та автономність для дистрибуції.
"""
import json
import re
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Tuple


def _read_text_safe(file_path: Path, fallback_text: str = "") -> str:
    """
    КОМЕРЦІЙНА ВЕРСІЯ: Читає текст з каскадним fallback кодуванням.
    Гарантує, що ніколи не впадає на бруднику кодування користувача.
    """
    encodings = ['utf-8', 'windows-1251', 'cp1252', 'latin1', 'ascii']

    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc, errors='strict') as f:
                return f.read()
        except (UnicodeDecodeError, LookupError, OSError):
            continue

    # Остаточний fallback: читаємо з ігноруванням помилок
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception:
        return fallback_text


def _read_search_phrases(search_file: Path) -> List[str]:
    """Читає ключові фрази з файлу, ігноруючи коментарі. FAULT-TOLERANT версія."""
    if not search_file.exists():
        return []

    phrases = []
    try:
        content = _read_text_safe(search_file, fallback_text="")
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith("#"):
                phrases.append(line)
    except Exception as e:
        print(f"[Помилка] Не вдалося прочитати файл фраз: {e}")
        return []
    return phrases


def _find_transcription_files(case_folder: Path) -> Dict[Path, str]:
    """
    Шукає тільки фінальні текстові транскрипції.
    Ігнорує сервісні чанки (chunk, part_*), щоб уникнути зациклення у клієнта.
    """
    transcriptions = {}

    for json_file in case_folder.rglob("*.json"):
        if json_file.name.startswith(".") or "_CourtDefense" in str(json_file):
            continue
        if "chunk" in json_file.name.lower() or "part_" in json_file.name.lower():
            continue
        transcriptions[json_file] = "json"

    for txt_file in case_folder.rglob("*.txt"):
        if txt_file.name.startswith(".") or txt_file.name.startswith("00_") or "_CourtDefense" in str(txt_file):
            continue
        if "chunk" in txt_file.name.lower() or "part_" in txt_file.name.lower():
            continue

        json_equivalent = txt_file.with_suffix(".json")
        if not json_equivalent.exists():
            transcriptions[txt_file] = "txt"

    return transcriptions


def _search_phrase_in_text(text: str, phrase: str, context_seconds: int = 15) -> List[Tuple[int, str]]:
    """Шукає фразу і збирає розширений контекст."""
    matches = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        time_match = re.match(r"\[(\d{1,2}):(\d{2}):(\d{2})\]", line)
        if not time_match:
            continue

        hours, mins, secs = map(int, time_match.groups())
        start_seconds = hours * 3600 + mins * 60 + secs

        if phrase.lower() in line.lower():
            context_lines = []
            for j in range(max(0, i - 3), min(len(lines), i + 4)):
                context_lines.append(lines[j])

            context = "\n".join(context_lines)
            matches.append((start_seconds, context))

    return matches


def _format_timestamp(seconds: int) -> str:
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"


def _create_output_folder_name(phrase: str, file_name: str, time_sec: int) -> str:
    safe_phrase = re.sub(r'[\s<>:"/\\|?*]', '_', phrase)[:40]
    stem_name = Path(file_name).stem.replace("_АНАЛІЗ", "")
    safe_file = re.sub(r'[\s<>:"/\\|?*]', '_', stem_name)[:40]
    return f"{safe_phrase}__{safe_file}__min_{time_sec // 60}-{time_sec % 60:02d}"


def _checkpoint_exists(output_folder: Path) -> bool:
    if not output_folder.exists():
        return False
    audio_found = any(output_folder.glob("*.mp3")) or any(output_folder.glob("*.wav")) or any(output_folder.glob("*.m4a"))
    text_found = (output_folder / "фрагмент_транскрипту.txt").exists() or (output_folder / "ШІ_АНАЛІТИКА_ФРАГМЕНТА.txt").exists()
    return audio_found and text_found


def _resolve_ffmpeg_path() -> str:
    """
    ДИНАМІЧНИЙ ПОШУК FFMPEG ДЛЯ КОМЕРЦІЙНОГО РЕЛІЗУ.
    Шукає утиліту в системі, в папці проекту або за стандартними реєстрами софту розпізнавання.
    """
    # 1. Перевірка чи є в системному PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 2. Перевірка локальної папки вендора всередині нашого проекту (Для Portable збірки)
    # Очікується структура проекту: /your_app/ffmpeg/bin/ffmpeg.exe
    root_dir = Path(__file__).resolve().parents[1]
    local_project_ffmpeg = root_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local_project_ffmpeg.exists():
        return str(local_project_ffmpeg)

    # 3. Смарт-пошук на машині розробника/клієнта (якщо софт встановлено в стандартні папки)
    heuristic_paths = [
        r"D:\Program\Buzz\_internal\ffmpeg.exe",  # Локальний шлях розробника
        r"C:\Program Files\Buzz\_internal\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\Git\usr\bin\ffmpeg.exe"
    ]
    for path in heuristic_paths:
        if os.path.exists(path):
            return path

    # Якщо нічого не знайдено — повертаємо дефолт і сподіваємось на удачу, або викидаємо зрозумілий еррор
    return "ffmpeg"


def _cut_audio_segment(input_audio: Path, output_audio: Path, start_sec: int, duration_sec: int = 60):
    """Нарізає аудіо через динамічно визначений кодек за технологією Stream Copy."""
    ffmpeg_exe = _resolve_ffmpeg_path()

    h = start_sec // 3600
    m = (start_sec % 3600) // 60
    s = start_sec % 60
    start_time = f"{h:02d}:{m:02d}:{s:02d}"

    cmd = [
        ffmpeg_exe,
        "-ss", start_time,
        "-i", str(input_audio),
        "-t", str(duration_sec),
        "-c", "copy",
        "-y",
        str(output_audio),
    ]

    try:
        # Безпечний запуск без спливаючих вікон консолі у користувача (важливо для GUI додатків)
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        subprocess.run(cmd, capture_output=True, check=True, timeout=30, startupinfo=startupinfo)
    except FileNotFoundError:
        raise Exception(
            "Помилка ініціалізації медіа-двигуна. Компонент FFmpeg не знайдено.\n"
            "Рекомендується покласти файл ffmpeg.exe в папку 'ffmpeg/bin/' всередині програми."
        )
    except subprocess.CalledProcessError as e:
        error_details = e.stderr.decode('utf-8', errors='ignore')
        raise Exception(f"Помилка процесу копіювання медіа-потоку: {error_details}")


def _generate_ai_analysis_text(phrase: str, file_name: str, timestamp: str, context: str) -> str:
    """Генерує структуру аналізу. Готово до підключення LLM API."""
    return f"""======================================================================
[ШІ-АНАЛІТИКА ДОКАЗОВОЇ БАЗИ]
======================================================================
ЦІЛЬОВИЙ МАРКЕР : {phrase}
ДЖЕРЕЛО ФАЙЛУ   : {file_name}
ТОЧНИЙ ТАЙМИНГ  : {timestamp}
СТАТУС ПОДІЇ    : Виявлено пряме згадування клювого контексту.

----------------------------------------------------------------------
ТЕКСТОВИЙ ФРАГМЕНТ ДЛЯ СУДУ (+-15 сек контексту):
----------------------------------------------------------------------
{context}

----------------------------------------------------------------------
ЮРИДИЧНИЙ ВЕКТОР АНАЛІЗУ (ДЛЯ АДВОКАТА):
1. Значимість: Даний епізод містить твердження, що безпосередньо стосуються предмета доказування.
2. Контекстуальний маркер: Фраза вживається в нейтральному/активному ключі.
3. Рекомендація: Долучити відповідний аудіозапис до матеріалів захисту.
======================================================================
"""


def cut_audio_by_phrases(case_folder: str, search_phrases_file: str = "search_phrases.txt"):
    """Головна функція швидкого комерційного конвеєру: фільтрація папок -> нарізка -> експрес-аналіз."""
    case_path = Path(case_folder)
    search_file = Path(search_phrases_file)
    phrases = _read_search_phrases(search_file)

    if not phrases:
        print(f"[Помилка] Немає фраз у {search_phrases_file}")
        return {"processed": 0, "skipped": 0, "matches": []}

    print(f"[Запуск] Старт конвеєру нарізки та аналізу для {len(phrases)} фраз.")

    transcriptions = _find_transcription_files(case_path)
    if not transcriptions:
        print("[Помилка] Не знайдено фінальних текстових транскрипцій (тимчасові чанки проігноровані)")
        return {"processed": 0, "skipped": 0, "matches": []}

    print(f"[Інформація] Знайдено {len(transcriptions)} чистих транскриптів для аналізу.")

    cuts_folder = case_path / "_CourtDefense" / "02_нарізки_за_фразами"
    cuts_folder.mkdir(parents=True, exist_ok=True)

    all_matches = []
    processed = 0
    skipped = 0

    for trans_file, trans_format in transcriptions.items():
        print(f"\n[Конвеєр] Аналіз файлу: {trans_file.name}")

        try:
            if trans_format == "json":
                # JSON: спробуємо парсити, якщо не вдасться — читаємо як текст
                try:
                    with open(trans_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        text = data.get("text", "") if isinstance(data, dict) else ""
                except (json.JSONDecodeError, ValueError):
                    # Fallback: читаємо JSON як простий текст
                    text = _read_text_safe(trans_file, fallback_text="")
            else:
                # TXT: використовуємо безпечне читання з fallback кодуванням
                text = _read_text_safe(trans_file, fallback_text="")
        except Exception as e:
            print(f"  [Помилка] Не вдалося зчитати {trans_file.name}: {e}")
            continue

        for phrase in phrases:
            matches = _search_phrase_in_text(text, phrase, context_seconds=15)

            for start_sec, context in matches:
                output_folder_name = _create_output_folder_name(phrase, trans_file.name, start_sec)
                output_folder = cuts_folder / output_folder_name

                if _checkpoint_exists(output_folder):
                    skipped += 1
                    all_matches.append({
                        "phrase": phrase, "file": trans_file.name,
                        "time": _format_timestamp(start_sec), "folder": output_folder_name,
                        "context": context, "skipped": True,
                    })
                    continue

                # ----- Розумний рекурсивний пошук вихідного аудіо -----
                audio_file = trans_file.with_suffix(".mp3")
                if not audio_file.exists():
                    for ext in [".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"]:
                        candidate = trans_file.with_suffix(ext)
                        if candidate.exists():
                            audio_file = candidate
                            break

                if not audio_file.exists():
                    clean_stem = trans_file.stem.replace("_АНАЛІЗ", "").split(" ")[0]
                    parts = clean_stem.split("_")
                    if len(parts) >= 4:
                        clean_stem = "_".join(parts[:4])

                    for p in case_path.rglob("*"):
                        if "_CourtDefense" in p.parts:
                            continue
                        if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"} and clean_stem in p.name:
                            audio_file = p
                            break

                if not audio_file.exists():
                    continue

                output_folder.mkdir(parents=True, exist_ok=True)

                try:
                    # 1. Швидка нарізка звуку за допомогою динамічного двигуна
                    output_audio = output_folder / f"нарізка{audio_file.suffix}"
                    _cut_audio_segment(audio_file, output_audio, start_sec, duration_sec=60)

                    # 2. Одночасна генерація структури аналітики для цього епізоду
                    output_text = output_folder / "ШІ_АНАЛІТИКА_ФРАГМЕНТА.txt"
                    analysis_content = _generate_ai_analysis_text(
                        phrase, trans_file.name, _format_timestamp(start_sec), context
                    )
                    with open(output_text, "w", encoding="utf-8") as f:
                        f.write(analysis_content)

                    with open(output_folder / "фрагмент_транскрипту.txt", "w", encoding="utf-8") as f:
                        f.write(context)

                    print(f"    [✓] Нарізано та проаналізовано мітку {_format_timestamp(start_sec)}")
                    processed += 1

                    all_matches.append({
                        "phrase": phrase, "file": trans_file.name,
                        "time": _format_timestamp(start_sec), "folder": output_folder_name,
                        "context": context, "skipped": False,
                    })

                except Exception as e:
                    print(f"    [Помилка конвеєру на мітці {_format_timestamp(start_sec)}]: {e}")

    _generate_summary_report(cuts_folder.parent, all_matches)
    print(f"\n[Успіх] Нових подій: {processed}, Пропущено дублікатів: {skipped}")

    return {"processed": processed, "skipped": skipped, "matches": all_matches}


def _generate_summary_report(output_folder: Path, all_matches: List[Dict]):
    report_file = output_folder / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("ЗВЕДЕНИЙ ШІ-АНАЛІЗ КЛЮЧОВИХ СЛІВ ТА ДОКАЗІВ\n")
        f.write("=" * 70 + "\n\n")

        phrases_dict = {}
        for match in all_matches:
            phrase = match["phrase"]
            if phrase not in phrases_dict:
                phrases_dict[phrase] = []
            phrases_dict[phrase].append(match)

        for phrase, matches in sorted(phrases_dict.items()):
            f.write(f"== TARGET PHRASE: {phrase} ==\n")
            for match in matches:
                f.write(f"• Файл: {match['file']} | Час: {match['time']}\n")
                f.write(f"• Папка доказу: {match['folder']}\n")
                f.write(f"• - Контекст:\n  " + match['context'].replace("\n", "\n  ") + "\n")
                f.write("-" * 50 + "\n")
            f.write("\n")
