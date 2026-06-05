import os
import sys
import httpx
import anthropic

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SORTED_DIR   = r"D:\12314234\нарезки\Отсортированные_данные_для_суда"
NEW_CHUNKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "готовые_нарезки")
PDF_ANALYSIS_PATH = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "ilovepdf_extracted-pages (1)", "all_pages_recognized.txt"
))
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEFENSE_ANALYSIS_V2.txt")

LAWYER_PROMPT = """
Ты — опытный украинский адвокат-практик по делам ст. 173-2 КУпАП (домашнее насилие) с 15-летним стажем.
Ты знаешь все процессуальные тонкости, судебную практику Київського регіону, реальные рычаги защиты.

Обвиняемый: Панько Павло Миколайович (13.06.1980).
Дело: ВАД №973440/9648/9649, три административных протокола, ст. 173-2 ч.1 и ч.2 КУпАП.
Заседание: 01.06.2026, 10:00, судья Гришко О.М., Києво-Святошинський районний суд.

Тебе предоставлены ДВА блока материалов:

== БЛОК А: МАТЕРИАЛЫ ПОЛИЦЕЙСКОГО ДЕЛА ==
Полная расшифровка административного дела.

== БЛОК Б: АУДИОЗАПИСИ (ТРАНСКРИПЦИИ) ==
Аудиозаписи систематизированы и ПОДПИСАНЫ по смыслу содержания (имена папок).
Обращай особое внимание на имена папок/файлов — они описывают суть каждой записи.

---

ТВОЯ ЗАДАЧА — МАКСИМАЛЬНО ДЕТАЛЬНЫЙ АДВОКАТСКИЙ АНАЛИЗ:

## 1. КАРТА ДОКАЗАТЕЛЬСТВ
Составь таблицу: каждая запись (по имени папки) → что в ней есть полезного для защиты → конкретная цитата → к какому пункту обвинения относится.

## 2. СИЛЬНЕЙШИЕ АРГУМЕНТЫ ЗАЩИТЫ
Топ-10 аргументов с конкретными цитатами из транскрипций. Для каждого: цитата → юридический аргумент → норма закона.

## 3. ПОЛНЫЕ ТЕКСТЫ ХОДАТАЙСТВ (готовы к подаче)
Напиши готовые тексты ходатайств:
- О приобщении аудиозаписей к делу (с перечнем и описанием каждого фрагмента)
- О вызове свидетелей (конкретные люди упомянутые в записях — имена, кем приходятся)
- О возврате протокола на доработку (по процессуальным нарушениям)
- О назначении психологической экспертизы
- Письменные пояснения подзащитного по каждому эпизоду обвинения

## 4. СЕКРЕТЫ АДВОКАТА — РЕАЛЬНАЯ ТАКТИКА
Что опытный защитник делает В ЗАЛЕсуда по ст.173-2 что не пишут в учебниках:
- Как вести себя при вопросах судьи
- Как реагировать на показания заявительницы
- Что говорить, что МОЛЧАТЬ
- Как использовать паузы и процессуальные моменты
- Чего НЕЛЬЗЯ делать ни в коем случае
- Как использовать форму оценки рисков (середній рівень) как главный щит
- Тактика перекрестного допроса заявительницы (если будет допрос)

## 5. ПИСЬМЕННАЯ ПОЗИЦИЯ ЗАЩИТЫ
Готовый текст письменных пояснень підзащитного для суда (2-3 стр.) — от первого лица, по-украински, юридически грамотно.

## 6. ПРОГНОЗ ПО КАЖДОМУ ИЗ ТРЁХ ДЕЛ
Отдельно по каждому из трёх протоколов — реальный исход, что можно добиться.

## 7. ПЛАН ДЕЙСТВИЙ ДО 01.06.2026 — ПОЧАСОВО
Что делать сегодня вечером 31.05 и утром 01.06 до 10:00.

Анализируй как практик: конкретно, без воды, с цитатами, с готовыми текстами документов.
"""


def collect_sorted_transcripts(root: str) -> list[tuple[str, str]]:
    """Reads .txt from папка_с_транскрипцией subfolders, uses parent folder name as label."""
    results = []
    seen_content = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        if os.path.basename(dirpath) == "папка_с_транскрипцией":
            # label = the recording folder name (grandparent)
            recording_name = os.path.basename(os.path.dirname(dirpath))
            for fname in sorted(filenames):
                if fname.lower().endswith(".txt"):
                    fpath = os.path.join(dirpath, fname)
                    try:
                        with open(fpath, encoding="utf-8", errors="replace") as f:
                            text = f.read().strip()
                        if text and text not in seen_content:
                            seen_content.add(text)
                            label = f"{recording_name} / {fname}"
                            results.append((label, text))
                    except Exception as e:
                        print(f"  Пропуск {fpath}: {e}")
    return results


def collect_new_chunks(root: str) -> list[tuple[str, str]]:
    """Reads .txt from 23-06-xx folders in готовые_нарезки."""
    results = []
    seen_content = set()
    if not os.path.exists(root):
        return results
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        folder = os.path.basename(dirpath)
        if not folder.startswith("23-06-"):
            continue
        for fname in sorted(filenames):
            if fname.lower().endswith(".txt"):
                fpath = os.path.join(dirpath, fname)
                try:
                    with open(fpath, encoding="utf-8", errors="replace") as f:
                        text = f.read().strip()
                    if text and text not in seen_content:
                        seen_content.add(text)
                        label = f"[новая нарезка] {folder} / {fname}"
                        results.append((label, text))
                except Exception as e:
                    print(f"  Пропуск {fpath}: {e}")
    return results


def read_pdf_analysis() -> str:
    if not os.path.exists(PDF_ANALYSIS_PATH):
        print(f"  Файл PDF-анализа не найден: {PDF_ANALYSIS_PATH}")
        return ""
    with open(PDF_ANALYSIS_PATH, encoding="utf-8", errors="replace") as f:
        return f.read().strip()


def build_message(sorted_transcripts, new_transcripts, pdf_text: str) -> str:
    parts = []

    if pdf_text:
        parts.append("=" * 70)
        parts.append("БЛОК А: МАТЕРИАЛЫ ПОЛИЦЕЙСКОГО ДЕЛА (расшифровка PDF)")
        parts.append("=" * 70)
        parts.append(pdf_text)
        parts.append("\n")

    all_transcripts = sorted_transcripts + new_transcripts
    parts.append("=" * 70)
    parts.append(f"БЛОК Б: АУДИОТРАНСКРИПЦИИ ({len(all_transcripts)} файлов)")
    parts.append("ВНИМАНИЕ: Имена папок описывают СУТЬ каждой записи — используй их для контекста!")
    parts.append("=" * 70)

    for label, text in all_transcripts:
        parts.append(f"\n{'─'*60}")
        parts.append(f"ЗАПИСЬ: {label}")
        parts.append('─'*60)
        parts.append(text)

    return "\n".join(parts)


def main():
    print("=== Адвокат-анализатор v2 (Claude Opus 4.7) ===\n")

    print(f"Сбор транскрипций из: {SORTED_DIR}")
    sorted_transcripts = collect_sorted_transcripts(SORTED_DIR)
    print(f"  Отсортированные записи: {len(sorted_transcripts)}")
    for label, text in sorted_transcripts:
        print(f"    • {label} ({len(text):,} символов)")

    print(f"\nСбор новых нарезок из: {NEW_CHUNKS_DIR}")
    new_transcripts = collect_new_chunks(NEW_CHUNKS_DIR)
    print(f"  Новые нарезки (23-06-xx): {len(new_transcripts)}")

    print(f"\nЧтение PDF-анализа...")
    pdf_text = read_pdf_analysis()
    if pdf_text:
        print(f"  PDF-анализ: {len(pdf_text):,} символов")
    else:
        print("  PDF-анализ не найден, продолжаю только с аудио.")

    total = len(sorted_transcripts) + len(new_transcripts)
    if not total and not pdf_text:
        print("Нет материалов для анализа. Выход.")
        return

    full_context = build_message(sorted_transcripts, new_transcripts, pdf_text)
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
    print("Сохранение анализа...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_response)
    print(f"Готово! Сохранено: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

