import os
import re
import sys
import httpx
import anthropic

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _page_num(filename: str) -> int:
    m = re.search(r"-(\d+)\.pdf$", filename, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def find_pdfs(folder: str) -> list[str]:
    names = [f for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    # sort by trailing page number if present, otherwise alphabetically
    return sorted(names, key=lambda f: (_page_num(f) == 0, _page_num(f), f.lower()))


def pick_pdfs(folder: str) -> list[str]:
    pdfs = find_pdfs(folder)
    if not pdfs:
        print(f"PDF файлы не найдены в папке: {folder}")
        return []

    print(f"\nНайдено PDF файлов в папке '{folder}':\n")
    for i, name in enumerate(pdfs, 1):
        size_mb = os.path.getsize(os.path.join(folder, name)) / 1024 / 1024
        print(f"  [{i:3}] {name}  ({size_mb:.1f} МБ)")

    print("\nВведи номера файлов через запятую или пробел (например: 1 3 5)")
    print("Или 'все' чтобы обработать все файлы:")
    raw = input("> ").strip()

    if raw.lower() in ("все", "all", "*"):
        return [os.path.join(folder, f) for f in pdfs]

    selected = []
    for token in raw.replace(",", " ").split():
        try:
            idx = int(token) - 1
            if 0 <= idx < len(pdfs):
                selected.append(os.path.join(folder, pdfs[idx]))
            else:
                print(f"Предупреждение: номер {token} вне диапазона, пропускаю.")
        except ValueError:
            print(f"Предупреждение: '{token}' не является числом, пропускаю.")

    return selected


PROMPT = """
Ты — профессиональный эксперт-криминалист и специалист по расшифровке архивных документов и рукописного текста.
Перед тобой многостраничный документ (возможно разбитый на несколько PDF-файлов по страницам), содержащий материалы административных и уголовных дел, протоколы и рукописные заявления из полиции.
Почерк авторов заявлений крайне тяжелый, неразборчивый, местами беглый.

Твоя задача — провести детальную, полную и дословную расшифровку (транскрибацию) ВСЕХ страниц этого документа от начала и до конца. Не упускай ни одной детали.

Правила расшифровки:
1. Разбирай текст максимально внимательно. Если слово написано неразборчиво, попытайся понять его из контекста юридических формулировок полиции. Если слово абсолютно невозможно разобрать, пиши [неразборчиво].
2. Структурируй вывод. Для каждой страницы делай заголовок: "=== СТРАНИЦА №... ===".
3. Полностью сохраняй структуру: даты, фамилии, адреса, звания, резолюции на полях, штампы и подписи (пиши [подпись], [штамп: текст штампа]).
4. Выдавай чистый текстовый вывод без пересказов и сокращений. Мне нужен полный текст всех заявлений.
"""


CHUNK_SIZE = 90  # Files API rate limit: 100 URL fetches per minute


def _send_chunk(client: anthropic.Anthropic, uploaded: list, chunk_num: int, total_chunks: int) -> str:
    content: list = []
    for uf in uploaded:
        content.append({
            "type": "document",
            "source": {"type": "file", "file_id": uf.id},
        })

    chunk_note = f"\n[Часть {chunk_num} из {total_chunks}]" if total_chunks > 1 else ""
    content.append({"type": "text", "text": PROMPT + chunk_note})

    full_text = ""
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=64000,
        messages=[{"role": "user", "content": content}],
        extra_headers={"anthropic-beta": "files-api-2025-04-14"},
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full_text += text
    return full_text


def process_batch(client: anthropic.Anthropic, pdf_paths: list[str], output_path: str) -> None:
    import time

    total = len(pdf_paths)
    chunks = [pdf_paths[i:i + CHUNK_SIZE] for i in range(0, total, CHUNK_SIZE)]
    total_chunks = len(chunks)

    print(f"\n{'='*60}")
    print(f"Пакетная обработка: {total} страниц → {total_chunks} запрос(ов) по ≤{CHUNK_SIZE} стр.")
    print(f"{'='*60}")

    all_text = ""

    for chunk_idx, chunk_paths in enumerate(chunks, 1):
        chunk_size = len(chunk_paths)
        start_page = (chunk_idx - 1) * CHUNK_SIZE + 1
        end_page = start_page + chunk_size - 1

        print(f"\n--- Часть {chunk_idx}/{total_chunks}: страницы {start_page}–{end_page} ---")

        uploaded = []
        try:
            print(f"Загрузка {chunk_size} файлов в Anthropic Files API...")
            for i, pdf_path in enumerate(chunk_paths, 1):
                name = os.path.basename(pdf_path)
                with open(pdf_path, "rb") as f:
                    uf = client.beta.files.upload(
                        file=(name, f, "application/pdf"),
                    )
                uploaded.append(uf)
                print(f"  [{start_page + i - 2:3}] {name} -> {uf.id}")

            print(f"\nОтправка {chunk_size} страниц в Claude...")
            print("-" * 60)
            chunk_text = _send_chunk(client, uploaded, chunk_idx, total_chunks)
            all_text += chunk_text + "\n\n"
            print(f"\n\nЧасть {chunk_idx} завершена.")

        finally:
            if uploaded:
                print(f"Очистка: удаление {len(uploaded)} файлов...")
                for uf in uploaded:
                    try:
                        client.beta.files.delete(uf.id)
                    except Exception:
                        pass
                print("Удалено.")

        if chunk_idx < total_chunks:
            print("Пауза 65 секунд между частями (rate limit)...")
            time.sleep(65)

    print(f"\nШаг финальный: Сохранение результатов...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(all_text)
    print(f"Готово! Результат сохранен: {output_path}")


def process_single(client: anthropic.Anthropic, pdf_path: str) -> None:
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_txt_path = os.path.join(os.path.dirname(pdf_path), f"{base_name}_recognized.txt")

    print(f"\n{'='*60}")
    print(f"Обработка: {os.path.basename(pdf_path)}")
    print(f"{'='*60}")

    print("Шаг 1: Загрузка файла в Anthropic Files API...")
    with open(pdf_path, "rb") as f:
        uploaded_file = client.beta.files.upload(
            file=(os.path.basename(pdf_path), f, "application/pdf"),
        )
    print(f"Файл загружен. ID: {uploaded_file.id}")

    print("Шаг 2: Отправка запроса в Claude (текст печатается в реальном времени)...")
    print("-" * 60)

    full_text = ""
    try:
        with client.messages.stream(
            model="claude-opus-4-7",
            max_tokens=64000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {"type": "file", "file_id": uploaded_file.id},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }],
            extra_headers={"anthropic-beta": "files-api-2025-04-14"},
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                full_text += text

        print(f"\n\nШаг 3: Сохранение результатов...")
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        print(f"Готово! Результат сохранен: {output_txt_path}")

    finally:
        print("Очистка: удаление файла с серверов Anthropic...")
        client.beta.files.delete(uploaded_file.id)
        print("Удалено.")


def main():
    default_folder = os.path.dirname(os.path.abspath(__file__))

    print("=== PDF Расшифровщик (Claude Opus 4.7) ===")
    print(f"\nПапка по умолчанию: {default_folder}")
    print("Нажми Enter чтобы использовать её, или введи другой путь:")
    raw_folder = input("> ").strip()
    folder = raw_folder if raw_folder else default_folder

    if not os.path.isdir(folder):
        print(f"Ошибка: папка '{folder}' не существует.")
        return

    selected = pick_pdfs(folder)
    if not selected:
        print("Файлы не выбраны. Выход.")
        return

    print(f"\nБудет обработано файлов: {len(selected)}")
    for p in selected:
        print(f"  - {os.path.basename(p)}")

    mode = "batch"
    if len(selected) > 1:
        print("\nРежим обработки:")
        print("  [1] Пакетный — все страницы в ОДИН запрос (лучшее качество, рекомендуется)")
        print("  [2] По одному — каждая страница отдельно")
        print("Выбор (Enter = 1):")
        choice = input("> ").strip()
        mode = "single" if choice == "2" else "batch"

    print("\nНачинаем? (y/n):")
    if input("> ").strip().lower() not in ("y", "yes", "да", "д"):
        print("Отмена.")
        return

    client = anthropic.Anthropic(
        http_client=httpx.Client(verify=False)
    )

    if mode == "batch":
        output_path = os.path.join(folder, "all_pages_recognized.txt")
        try:
            process_batch(client, selected, output_path)
        except Exception as e:
            print(f"\nОШИБКА: {e}")
    else:
        for pdf_path in selected:
            try:
                process_single(client, pdf_path)
            except Exception as e:
                print(f"\nОШИБКА при обработке {os.path.basename(pdf_path)}: {e}")
                print("Продолжаем со следующим файлом...")

    print("\n=== Готово ===")


if __name__ == "__main__":
    main()

