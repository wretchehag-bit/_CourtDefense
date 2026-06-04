"""
Модуль автоматической нарезки аудио по ключевым фразам.
Поддерживает чекпоинты (идемпотентность): пропускает уже обработанные совпадения.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
import shutil


def _read_search_phrases(search_file: Path) -> List[str]:
    """
    Читает ключевые фразы из файла поиска.
    Формат: одна фраза на строку, пустые строки и комментарии (# ...) игнорируются.
    """
    if not search_file.exists():
        return []

    phrases = []
    with open(search_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Пропускаем пустые строки и комментарии
            if line and not line.startswith("#"):
                phrases.append(line)
    return phrases


def _find_transcription_files(case_folder: Path) -> Dict[Path, str]:
    """
    Рекурсивно ищет файлы транскрипций (JSON от Whisper и TXT) в case_folder.
    Возвращает словарь {путь_файла: формат (json|txt)}.

    ВАЖНО: пропускает папку _CourtDefense, чтобы не обрабатывать сгенерированные файлы.
    """
    transcriptions = {}

    # Ищем JSON файлы от Whisper
    for json_file in case_folder.rglob("*.json"):
        # Пропускаем служебные JSON файлы
        if json_file.name.startswith("."):
            continue
        # Пропускаем файлы в папке _CourtDefense
        if "_CourtDefense" in str(json_file):
            continue
        transcriptions[json_file] = "json"

    # Ищем TXT транскрипции (но не служебные)
    for txt_file in case_folder.rglob("*.txt"):
        # Пропускаем служебные файлы
        if txt_file.name.startswith(".") or txt_file.name.startswith("00_"):
            continue
        # Пропускаем файлы в папке _CourtDefense
        if "_CourtDefense" in str(txt_file):
            continue
        # Ищем рядом JSON версию
        json_equivalent = txt_file.with_suffix(".json")
        if not json_equivalent.exists():
            transcriptions[txt_file] = "txt"

    return transcriptions


def _search_phrase_in_text(text: str, phrase: str, context_seconds: int = 10) -> List[Tuple[int, str]]:
    """
    Ищет фразу в тексте с временными метками (от Whisper).
    Возвращает список кортежей (время_начала_в_сек, контекст).

    Текст ожидается в формате: "[HH:MM:SS] Спикер: текст"
    """
    matches = []

    # Разбиваем текст на строки
    lines = text.split("\n")

    for i, line in enumerate(lines):
        # Извлекаем временную метку
        time_match = re.match(r"\[(\d{1,2}):(\d{2}):(\d{2})\]", line)
        if not time_match:
            continue

        hours, mins, secs = map(int, time_match.groups())
        start_seconds = hours * 3600 + mins * 60 + secs

        # Ищем фразу в строке (case-insensitive)
        if phrase.lower() in line.lower():
            # Собираем контекст (+-context_seconds)
            context_lines = []
            for j in range(max(0, i - 2), min(len(lines), i + 3)):
                context_lines.append(lines[j])

            context = "\n".join(context_lines)
            matches.append((start_seconds, context))

    return matches


def _format_timestamp(seconds: int) -> str:
    """Форматирует секунды в формат Мин:Сек."""
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}:{secs:02d}"


def _create_output_folder_name(phrase: str, file_name: str, time_sec: int) -> str:
    """
    Создает имя выходной папки в формате:
    [Фраза]__[Имя_Файла]__min_[Мин-Сек]

    На Windows двоеточие заменяется дефисом.
    """
    # Очищаем фразу от спецсимволов для использования в имени папки
    safe_phrase = re.sub(r'[\s<>:"/\\|?*]', '_', phrase)[:50]

    # Очищаем имя файла
    safe_file = Path(file_name).stem[:40]

    # Форматируем время (заменяем : на -)
    mins = time_sec // 60
    secs = time_sec % 60
    timestamp = f"{mins}-{secs:02d}"

    return f"{safe_phrase}__{safe_file}__min_{timestamp}"


def _checkpoint_exists(output_folder: Path) -> bool:
    """
    Проверяет, что папка существует и содержит необходимые файлы:
    - Аудиофайл (.mp3 или .wav)
    - Текстовый фрагмент (фрагмент_транскрипту.txt или подобное)
    """
    if not output_folder.exists():
        return False

    # Ищем аудиофайл
    audio_found = any(output_folder.glob("*.mp3")) or any(output_folder.glob("*.wav"))

    # Ищем текстовый файл
    text_found = any(output_folder.glob("*транскрип*.txt")) or \
                 any(output_folder.glob("*fragment*.txt")) or \
                 (output_folder / "фрагмент_транскрипту.txt").exists()

    return audio_found and text_found


def _cut_audio_segment(input_audio: Path, output_audio: Path, start_sec: int, duration_sec: int = 60):
    """
    Нарезает аудиофайл от start_sec на duration_sec секунд.
    Поддерживает MP3, WAV и другие форматы через pydub.

    Args:
        input_audio: Путь к исходному аудиофайлу
        output_audio: Путь к выходному файлу
        start_sec: Начало в секундах
        duration_sec: Длительность в секундах
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        # Fallback: используем ffmpeg через subprocess
        import subprocess
        import os

        # Форматируем время
        start_time = _format_timestamp(start_sec)
        duration_time = _format_timestamp(duration_sec)

        cmd = [
            "ffmpeg",
            "-i", str(input_audio),
            "-ss", start_time,
            "-t", duration_time,
            "-c", "copy",
            "-y",
            str(output_audio),
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
            return
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise Exception(f"Не вдалося нарізати аудіо: {e}")

    # Используем pydub если доступно
    try:
        audio = AudioSegment.from_file(str(input_audio))
        start_ms = start_sec * 1000
        end_ms = (start_sec + duration_sec) * 1000

        segment = audio[start_ms:end_ms]

        # Определяем формат по расширению выходного файла
        format_ext = output_audio.suffix.lstrip(".")
        segment.export(str(output_audio), format=format_ext)
    except Exception as e:
        raise Exception(f"Ошибка pydub: {e}")


def cut_audio_by_phrases(case_folder: str, search_phrases_file: str = "search_phrases.txt"):
    """
    Основная функция: нарезает аудиофайлы по ключевым фразам с поддержкой чекпоинтов.

    Args:
        case_folder: Путь к папке дела
        search_phrases_file: Путь к файлу со списком фраз (одна на строку)

    Возвращает:
        Словарь с результатами: {
            "processed": количество обработанных совпадений,
            "skipped": количество пропущенных (уже существуют),
            "matches": список всех найденных совпадений
        }
    """
    case_path = Path(case_folder)
    if not case_path.exists():
        raise ValueError(f"Папка не существует: {case_folder}")

    # Читаем фразы
    search_file = Path(search_phrases_file)
    phrases = _read_search_phrases(search_file)
    if not phrases:
        print(f"[Помилка] Немає фраз у {search_phrases_file}")
        return {"processed": 0, "skipped": 0, "matches": []}

    print(f"[Запуск] Шукаю {len(phrases)} фраз(и) у {case_folder}")

    # Ищем файлы транскрипций
    transcriptions = _find_transcription_files(case_path)
    if not transcriptions:
        print("[Помилка] Не знайдено файлів транскрипції у папці")
        return {"processed": 0, "skipped": 0, "matches": []}

    print(f"[Інформація] Знайдено {len(transcriptions)} файл(и) транскрипції")

    # Папка для нарізок
    cuts_folder = case_path / "_CourtDefense" / "02_нарізки_за_фразами"
    cuts_folder.mkdir(parents=True, exist_ok=True)

    all_matches = []
    processed = 0
    skipped = 0

    # Обрабатываем каждый файл транскрипции
    for trans_file, trans_format in transcriptions.items():
        print(f"\n[Обробка] {trans_file.name}")

        # Читаем текст из транскрипции
        if trans_format == "json":
            try:
                with open(trans_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    text = data.get("text", "")
            except Exception as e:
                print(f"  [Помилка] Не вдалося прочитати JSON: {e}")
                continue
        else:  # txt
            try:
                with open(trans_file, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception as e:
                print(f"  [Помилка] Не вдалося прочитати TXT: {e}")
                continue

        # Ищем каждую фразу в тексте
        for phrase in phrases:
            matches = _search_phrase_in_text(text, phrase, context_seconds=10)

            for start_sec, context in matches:
                # Создаем имя выходной папки
                output_folder_name = _create_output_folder_name(
                    phrase,
                    trans_file.name,
                    start_sec
                )
                output_folder = cuts_folder / output_folder_name

                # КРИТИЧЕСКИ: Проверяем чекпоинт
                if _checkpoint_exists(output_folder):
                    print(f"  [ЧЕКПОІНТ] Фрагмент вже існує, пропускаємо нарізку для: " +
                          f"{trans_file.name} на {_format_timestamp(start_sec)}")
                    skipped += 1
                    all_matches.append({
                        "phrase": phrase,
                        "file": trans_file.name,
                        "time": _format_timestamp(start_sec),
                        "folder": output_folder_name,
                        "context": context,
                        "skipped": True,
                    })
                    continue

                # Создаем папку для нарізки
                output_folder.mkdir(parents=True, exist_ok=True)

                # Ищем исходный аудиофайл (в той же папке что и транскрипция)
                audio_file = trans_file.parent / trans_file.stem
                if not audio_file.exists():
                    # Пробуем другие расширения
                    for ext in [".mp3", ".wav", ".m4a", ".ogg"]:
                        candidate = trans_file.parent / (trans_file.stem + ext)
                        if candidate.exists():
                            audio_file = candidate
                            break

                if not audio_file.exists():
                    print(f"    [Помилка] Аудіофайл не знайдено для {trans_file.name}")
                    continue

                # Нарізаємо аудіо
                try:
                    output_audio = output_folder / f"нарізка.{audio_file.suffix.lstrip('.')}"
                    print(f"    [Нарізка] {_format_timestamp(start_sec)} → {output_audio.name}")

                    _cut_audio_segment(audio_file, output_audio, start_sec, duration_sec=60)

                    # Генеруємо текстовий фрагмент
                    output_text = output_folder / "фрагмент_транскрипту.txt"
                    with open(output_text, "w", encoding="utf-8") as f:
                        f.write(f"КЛЮЧОВА ФРАЗА: {phrase}\n")
                        f.write(f"Знайдено у файлі: {trans_file.name}\n")
                        f.write(f"Час на записі: {_format_timestamp(start_sec)}\n")
                        f.write(f"\nКОНТЕКСТ (+- 10 сек):\n")
                        f.write(context)

                    print(f"    [✓] Нарізка та текст створені")
                    processed += 1

                    all_matches.append({
                        "phrase": phrase,
                        "file": trans_file.name,
                        "time": _format_timestamp(start_sec),
                        "folder": output_folder_name,
                        "context": context,
                        "skipped": False,
                    })

                except Exception as e:
                    print(f"    [Помилка] Не вдалося нарізати: {e}")

    # Генеруємо загальний висновок (ЗАВЖДИ, навіть якщо все пропущено)
    _generate_summary_report(cuts_folder.parent, all_matches)

    print(f"\n[Завершено] Оброблено: {processed}, Пропущено: {skipped}")

    return {
        "processed": processed,
        "skipped": skipped,
        "matches": all_matches,
    }


def _generate_summary_report(output_folder: Path, all_matches: List[Dict]):
    """
    Генеруємо загальний висновок з усіма знайденими фразами.
    Файл перезаписується при кожному запуску, щоб містити ПОВНУ хронологію.
    output_folder повинна бути папкою _CourtDefense.
    """
    report_file = output_folder / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("ЗАГАЛЬНИЙ ВИСНОВОК: КЛЮЧОВІ ФРАЗИ І ЧАСОВІ МІТКИ\n")
        f.write("=" * 70 + "\n\n")

        # Групуємо за фразами
        phrases_dict = {}
        for match in all_matches:
            phrase = match["phrase"]
            if phrase not in phrases_dict:
                phrases_dict[phrase] = []
            phrases_dict[phrase].append(match)

        # Виводимо для кожної фрази
        for phrase, matches in sorted(phrases_dict.items()):
            f.write("=" * 70 + "\n")
            f.write(f"КЛЮЧЕВА ФРАЗА: {phrase}\n")
            f.write("=" * 70 + "\n\n")

            for match in matches:
                f.write(f"• Знайдено у файлі: {match['file']}\n")
                f.write(f"• Точний час на записі: {match['time']}\n")
                f.write(f"• Посилання на підпапку: {match['folder']}\n")

                if match['skipped']:
                    f.write(f"• Статус: [ПРОПУЩЕНО - вже оброблено]\n")
                else:
                    f.write(f"• Статус: [НОВИЙ - щойно оброблено]\n")

                f.write(f"\n• Контекст фрагмента (+-10 сек):\n")
                f.write("  " + match['context'].replace("\n", "\n  ") + "\n")
                f.write("-" * 70 + "\n\n")

    print(f"[✓] Загальний висновок: {report_file}")
