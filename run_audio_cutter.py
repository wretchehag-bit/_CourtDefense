#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI для автоматичної нарізки аудіо за ключовими фразами.

Run: python run_audio_cutter.py
"""
import sys
import os
from pathlib import Path

# Add src/ to path for court_defense imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from court_defense.core.audio_cutter import cut_audio_by_phrases

# Project root for resolving relative paths to phrase files
current_dir = Path(__file__).parent.resolve()


def main():
    """Інтерактивний CLI для нарізки аудіо."""
    print("=" * 70)
    print("Court Defense AI — Автоматична нарізка аудіо за ключовими фразами")
    print("=" * 70)
    print()

    # Запитуємо шлях до папки справи
    case_folder = input("Введіть шлях до папки справи: ").strip()

    if not case_folder:
        print("[Помилка] Шлях не може бути пустим")
        return 1

    case_path = Path(case_folder)
    if not case_path.exists():
        print(f"[Помилка] Папка не існує: {case_folder}")
        return 1

    if case_path.is_file():
        print(f"[Помилка] Вказано файл замість ПАПКИ справи: {case_folder}")
        return 1

    # Запитуємо файл зі списком фраз
    search_file_input = input(
        "Введіть шлях до файлу зі списком фраз [за замовчуванням: search_phrases.txt]: "
    ).strip()

    # Розумне визначення шляху до файлу фраз
    if not search_file_input:
        search_path = current_dir / "search_phrases.txt"
    else:
        search_path = Path(search_file_input)
        # Якщо ввели відносний шлях, перевіряємо його спочатку в папці проекту
        if not search_path.is_absolute():
            if (current_dir / search_path).exists():
                search_path = current_dir / search_path

    # Захист від Windows double-extension (якщо файл названо search_phrases.txt.txt)
    if not search_path.exists() and search_path.suffix != ".txt":
        alt_path = search_path.with_suffix(".txt")
        if alt_path.exists():
            search_path = alt_path

    # Кінцева валідація файлу перед запуском
    if not search_path.exists():
        print(f"[Помилка] Файл із фразами не знайдено!")
        print(f"Перевірений шлях: {search_path}")
        print(f"Будь ласка, переконайтеся, що файл створено в папці: {current_dir}")
        return 1

    if search_path.is_dir():
        print(f"[Помилка] Ви вказали шлях до ПАПКИ замість текстового файлу .txt!")
        print(f"Шлях: {search_path}")
        print(f"Спробуйте вказати: {search_path / 'search_phrases.txt'}")
        return 1

    print()
    print(f"[Конфігурація] Папка справи: {case_path}")
    print(f"[Конфігурація] Файл фраз:   {search_path}")
    print("[Запуск] Обробка почалася...")
    print()

    try:
        result = cut_audio_by_phrases(
            case_folder=str(case_path),
            search_phrases_file=str(search_path),
        )

        print()
        print("=" * 70)
        print("РЕЗУЛЬТАТИ:")
        print(f"  • Оброблено (нове): {result.get('processed', 0)}")
        print(f"  • Пропущено (вже готово): {result.get('skipped', 0)}")
        print(f"  • Всього знайдено: {len(result.get('matches', []))}")
        print("=" * 70)

        if result.get("processed", 0) > 0:
            print()
            print("[✓] Нарізка успішно завершена!")
            print(f"[✓] Див. папку: {case_path / '_CourtDefense' / '02_нарізки_за_фразами'}")
            return 0
        elif result.get("skipped", 0) > 0:
            print()
            print("[✓] Всі фрагменти вже оброблені раніше.")
            print("[✓] Чекпоінти працюють: немає дублювання.")
            return 0
        else:
            print()
            print("[Інформація] Фраз не знайдено у транскрипціях.")
            return 0

    except Exception as e:
        print()
        print(f"[ПОМИЛКА ВИКОНАННЯ] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
