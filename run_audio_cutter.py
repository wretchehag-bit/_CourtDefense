#!/usr/bin/env python3
"""
CLI точка входу для автоматичної нарізки аудіо за ключовими фразами.
Запуск: python run_audio_cutter.py
"""
import sys
from pathlib import Path

# Додаємо корінь проекту до path
sys.path.insert(0, str(Path(__file__).parent))

from webapp.audio_cutter import cut_audio_by_phrases


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

    # Запитуємо файл зі списком фраз
    search_file = input(
        "Введіть шлях до файлу зі списком фраз [за замовчуванням: search_phrases.txt]: "
    ).strip()

    if not search_file:
        search_file = "search_phrases.txt"

    search_path = Path(search_file)
    if not search_path.exists():
        print(f"[Попередження] Файл не знайдено: {search_file}")
        print("[Інформація] Буду шукати пусту папку фраз")

    print()
    print("[Запуск] Обробка почалася...")
    print()

    try:
        result = cut_audio_by_phrases(
            case_folder=case_folder,
            search_phrases_file=search_file,
        )

        print()
        print("=" * 70)
        print("РЕЗУЛЬТАТИ:")
        print(f"  • Оброблено (новое): {result['processed']}")
        print(f"  • Пропущено (вже готово): {result['skipped']}")
        print(f"  • Всього знайдено: {len(result['matches'])}")
        print("=" * 70)

        if result["processed"] > 0:
            print()
            print("[✓] Нарізка успішно завершена!")
            print(f"[✓] Див. папку: {case_path / '_CourtDefense' / '02_нарізки_за_фразами'}")
            return 0
        elif result["skipped"] > 0:
            print()
            print("[✓] Всі фрагменти вже обробляються раніше.")
            print("[✓] Чекпоінти працюють: немає дублювання.")
            return 0
        else:
            print()
            print("[Інформація] Фраз не знайдено.")
            return 0

    except Exception as e:
        print()
        print(f"[ПОМИЛКА] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
