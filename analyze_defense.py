import os
import sys
import re
import httpx
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

TRANSCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "готовые_нарезки")
PDF_ANALYSIS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "ilovepdf_extracted-pages (1)", "all_pages_recognized.txt"
)
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEFENSE_ANALYSIS.txt")

LAWYER_PROMPT = """
Ты — опытный украинский адвокат по семейным делам и делам об административных правонарушениях.
Специализация: защита по ст. 173-2 КУпАП (домашнее насилие), семейное право (место проживания детей, права отца).

Тебе предоставлены ДВА блока материалов:

== БЛОК А: МАТЕРИАЛЫ ПОЛИЦЕЙСКОГО ДЕЛА ==
Полная расшифровка административного дела ВАД №973440/9648/9649 (ст. 173-2 ч.1 КУпАП).
Обвиняемый: Панько Павло Миколайович, дата рождения 13.06.1980.
Дата инцидента: 07.05.2026 - 12.05.2026.
Рассматривается в Києво-Святошинському районному суді.

== БЛОК Б: АУДИОЗАПИСИ (ТРАНСКРИПЦИИ) ==
Семейные разговоры, обращения к суду, записи взаимодействия с детьми и супругой.

---

ТВОЯ ЗАДАЧА — ПОЛНЫЙ ЮРИДИЧЕСКИЙ АНАЛИЗ ЗАЩИТЫ:

1. РАЗБОР ДЕЛА
   - Что конкретно инкриминируется по ст. 173-2 КУпАП
   - Какие доказательства предъявлены обвинением
   - Где в материалах дела есть юридические уязвимости (процессуальные нарушения, противоречия, недостаточность доказательной базы)

2. ЧТО ПОМОГАЕТ ЗАЩИТЕ (из аудиозаписей)
   - Конкретные цитаты и эпизоды, которые демонстрируют отсутствие агрессии / нормальные семейные отношения
   - Свидетельства хорошего отношения к детям
   - Финансовый вклад, забота, воспитание
   - Попытки конструктивного диалога с супругой

3. ЧТО МОЖНО ОСПОРИТЬ
   - По каждому пункту обвинения — конкретный контраргумент
   - Как трактовать спорные эпизоды в пользу защиты
   - Какие нормы КУпАП и УПК применимы

4. СТРАТЕГИЯ ЗАЩИТЫ В СУДЕ
   - Позиция на заседании (что говорить, что признавать, что отрицать)
   - Ходатайства которые стоит подать
   - Свидетели которых стоит привлечь
   - Доказательства которые стоит приобщить к делу

5. РИСКИ И ПРОГНОЗ
   - Вероятный исход при текущей доказательной базе
   - Что может усилить позицию до заседания

Анализируй детально, по-адвокатски: с конкретными ссылками на материалы, цитатами, юридическими нормами.
"""


def collect_transcripts(root: str) -> list[tuple[str, str]]:
    """Returns list of (label, text) from all .txt files, sorted by folder name."""
    results = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fname in sorted(filenames):
            if fname.lower().endswith(".txt"):
                fpath = os.path.join(dirpath, fname)
                rel = os.path.relpath(fpath, root)
                try:
                    with open(fpath, encoding="utf-8", errors="replace") as f:
                        text = f.read().strip()
                    if text:
                        results.append((rel, text))
                except Exception as e:
                    print(f"  Пропуск {rel}: {e}")
    return results


def read_pdf_analysis() -> str:
    path = os.path.normpath(PDF_ANALYSIS_PATH)
    if not os.path.exists(path):
        print(f"  Файл PDF-анализа не найден: {path}")
        return ""
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def build_message(transcripts: list[tuple[str, str]], pdf_text: str) -> str:
    parts = []

    if pdf_text:
        parts.append("=" * 70)
        parts.append("БЛОК А: МАТЕРИАЛЫ ПОЛИЦЕЙСКОГО ДЕЛА (расшифровка PDF)")
        parts.append("=" * 70)
        parts.append(pdf_text)
        parts.append("\n")

    parts.append("=" * 70)
    parts.append(f"БЛОК Б: АУДИОТРАНСКРИПЦИИ ({len(transcripts)} файлов)")
    parts.append("=" * 70)

    for label, text in transcripts:
        parts.append(f"\n--- ФАЙЛ: {label} ---")
        parts.append(text)

    return "\n".join(parts)


def main():
    print("=== Адвокат-анализатор (Claude Opus 4.7) ===\n")

    print(f"Сбор транскрипций из: {TRANSCRIPTS_DIR}")
    transcripts = collect_transcripts(TRANSCRIPTS_DIR)
    print(f"  Найдено транскрипций: {len(transcripts)}")
    for label, text in transcripts:
        print(f"    • {label} ({len(text):,} символов)")

    print(f"\nЧтение PDF-анализа...")
    pdf_text = read_pdf_analysis()
    if pdf_text:
        print(f"  PDF-анализ: {len(pdf_text):,} символов")
    else:
        print("  PDF-анализ не найден, продолжаю только с аудио.")

    if not transcripts and not pdf_text:
        print("Нет материалов для анализа. Выход.")
        return

    full_context = build_message(transcripts, pdf_text)
    total_chars = len(full_context)
    print(f"\nИтого материалов: {total_chars:,} символов (~{total_chars//4:,} токенов)")

    print("\nНачинаем анализ? (y/n):")
    if sys.stdin.isatty():
        answer = input("> ").strip().lower()
    else:
        answer = "y"
        print("> (авто-да)")
    if answer not in ("y", "yes", "да", "д"):
        print("Отмена.")
        return

    client = anthropic.Anthropic(
        http_client=httpx.Client(verify=False, timeout=600.0)
    )

    print("\nОтправка в Claude (юридический анализ в реальном времени)...")
    print("=" * 70)

    full_response = ""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=16000,
        messages=[{
            "role": "user",
            "content": full_context + "\n\n" + LAWYER_PROMPT,
        }],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_response += text

    print(f"\n\n{'='*70}")
    print("Сохранение анализа защиты...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_response)
    print(f"Готово! Анализ сохранен: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
