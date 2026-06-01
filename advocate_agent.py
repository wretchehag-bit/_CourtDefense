"""
╔══════════════════════════════════════════════════════════════════════════╗
║          АГЕНТ-АДВОКАТ — АВТОНОМНИЙ КЛАСИФІКАТОР ДОКАЗІВ               ║
║                        v1.0 | ст. 173-2 КУпАП                          ║
╚══════════════════════════════════════════════════════════════════════════╝

Що робить:
  1. Сканує всі папки в SORTED_DIR
  2. Знаходить транскрипції в папка_с_транскрипцией
  3. Паралельно (8 потоків) надсилає кожну в Claude для аналізу
  4. Класифікує: STRONG / SUPPORT / NEUTRAL / RISKY
  5. Копіює файли в структуровані папки результатів
  6. Генерує таблицю аналізу + стратегічний звіт

Структура вхідних даних:
  SORTED_DIR/
    [timestamp]_[назва_що_описує_зміст]/
      папка_с_транскрипцией/
        *.txt
      папка_с_нарезками/
      *.m4a

Результат:
  ВІДІБРАНІ_ДОКАЗИ/
    1_СИЛЬНІ_ДОКАЗИ/
    2_ДОПОМІЖНІ/
    3_НЕЙТРАЛЬНІ/
    4_РИЗИКОВІ_НЕ_НЕСТИ/
    АНАЛІЗ_ВСІХ_ФАЙЛІВ.txt
    ЗВІТ_ДЛЯ_СУДУ.txt

Використання:
  python advocate_agent.py
  python advocate_agent.py --root "D:\\шлях\\до\\папки"
  python advocate_agent.py --workers 10 --no-cache
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import argparse
import time
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Optional
from threading import Lock

# ── UTF-8 консоль ──────────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
import anthropic

# ══════════════════════════════════════════════════════════════════════════
# КОНФІГУРАЦІЯ
# ══════════════════════════════════════════════════════════════════════════

OUTPUT_DIR  = Path(__file__).parent / "ВІДІБРАНІ_ДОКАЗИ"
CACHE_FILE  = Path(__file__).parent / ".advocate_cache.json"

try:
    from case_config import CASE, SORTED_DIR as _SORTED_DIR
    DEFAULT_ROOT = _SORTED_DIR
except ImportError:
    from case_config_example import CASE, SORTED_DIR as _SORTED_DIR  # type: ignore
    DEFAULT_ROOT = _SORTED_DIR

# Папки виводу
CATEGORY_DIRS = {
    "STRONG":  "1_СИЛЬНІ_ДОКАЗИ",
    "SUPPORT": "2_ДОПОМІЖНІ_ДОКАЗИ",
    "NEUTRAL": "3_НЕЙТРАЛЬНІ",
    "RISKY":   "4_РИЗИКОВІ_НЕ_НЕСТИ",
}

CATEGORY_LABELS = {
    "STRONG":  "✅ СИЛЬНИЙ ДОКАЗ",
    "SUPPORT": "⚠️  ДОПОМІЖНИЙ",
    "NEUTRAL": "🔍 НЕЙТРАЛЬНИЙ",
    "RISKY":   "❌ РИЗИКОВИЙ",
}

PRINT_LOCK = Lock()

# ══════════════════════════════════════════════════════════════════════════
# МОДЕЛІ ДАНИХ
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class TranscriptFile:
    """Один файл транскрипції з метаданими."""
    recording_name: str        # назва папки запису (семантична мітка)
    txt_path: Path             # шлях до .txt файлу
    text: str                  # вміст транскрипції
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.text)


@dataclass
class ClassificationResult:
    """Результат аналізу одного файлу агентом."""
    recording_name: str
    txt_path: str
    category: str              # STRONG / SUPPORT / NEUTRAL / RISKY
    score: int                 # 1-10
    reason: str                # чому така категорія
    key_quotes: list[str]      # ключові цитати (до 3)
    court_tip: str             # порада для суду
    folder_name_signal: str    # що сигналізує назва папки
    error: Optional[str] = None

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)


# ══════════════════════════════════════════════════════════════════════════
# ПРОМПТ КЛАСИФІКАТОРА
# ══════════════════════════════════════════════════════════════════════════

CLASSIFIER_SYSTEM = """Ти — досвідчений адвокат-практик по справах ст. 173-2 КУпАП (домашнє насильство) з 15-річним стажем у судах Київської області.

Твоя задача — оцінити аудіотранскрипцію з точки зору її цінності як ДОКАЗУ ЗАХИСТУ.

Справа: {case_number}, {article}
Обвинувачений: {defendant}

КРИТЕРІЇ КЛАСИФІКАЦІЇ:

STRONG (сильний доказ, нести в суд обов'язково):
- Заявниця сама говорить речі що суперечать її показанням
- Спокійний тон обвинуваченого навіть в конфліктній ситуації
- Обвинувачений проявляє турботу про дітей (гуляє, грає, розмовляє)
- Фінансова підтримка сім'ї підтверджена словами заявниці
- Заявниця провокує або сама ініціює конфлікт
- Свідки підтверджують нормальні стосунки в сім'ї

SUPPORT (допоміжний, посилює загальну картину):
- Нейтральне побутове спілкування без агресії
- Обвинувачений спокійно вирішує питання дітей/побуту
- Доброзичливий тон розмови
- Обговорення спільного господарства, плани

NEUTRAL (нейтральний, не допомагає і не шкодить):
- Технічні розмови (де ключі, купи хліб і т.п.)
- Короткі незначущі репліки
- Розмови не пов'язані з суттю справи

RISKY (ризиковий, НЕ нести в суд):
- Підвищений голос або різкий тон обвинуваченого (навіть якщо виправданий)
- Будь-яка лексика що можна трактувати як тиск, погрози, образи
- Суперечки де обвинувачений виглядає агресором
- Згадки про інциденти що фігурують в протоколах
- Емоційні висловлювання які прокурор може використати проти

ВАЖЛИВО:
- Розмови йдуть МІШАНИНОЮ українська + російська — аналізуй обидві мови
- Назва папки часто описує суть запису — врахуй її
- Будь КОНСЕРВАТИВНИМ щодо RISKY: якщо є сумнів — краще RISKY ніж SUPPORT
- Давай відповідь ТІЛЬКИ у форматі JSON, без пояснень поза JSON
""".format(**CASE)

CLASSIFIER_USER_TEMPLATE = """Проаналізуй цю транскрипцію як адвокат захисту.

НАЗВА ПАПКИ (семантична мітка запису): "{recording_name}"

ТРАНСКРИПЦІЯ:
{text}

Дай відповідь СТРОГО у такому JSON форматі (без markdown, без ```json, тільки сирий JSON):
{{
  "category": "STRONG|SUPPORT|NEUTRAL|RISKY",
  "score": <число 1-10, де 10=найсильніший доказ, 1=найнебезпечніший>,
  "folder_name_signal": "<що сигналізує назва папки — позитив/негатив/нейтраль>",
  "reason": "<1-3 речення чому ця категорія>",
  "key_quotes": ["<цитата 1>", "<цитата 2>"],
  "court_tip": "<1-2 речення: як використати або чому точно не нести>"
}}"""


# ══════════════════════════════════════════════════════════════════════════
# СКАНЕР ФАЙЛІВ
# ══════════════════════════════════════════════════════════════════════════

def scan_transcripts(root: Path) -> list[TranscriptFile]:
    """
    Сканує структуру:
      root/
        [recording_name]/
          папка_с_транскрипцией/
            *.txt
    """
    results: list[TranscriptFile] = []
    seen_content: set[str] = set()

    if not root.exists():
        print(f"[!] Директорія не знайдена: {root}")
        return results

    recording_dirs = sorted([d for d in root.iterdir() if d.is_dir()])
    print(f"  Знайдено папок записів: {len(recording_dirs)}")

    for rec_dir in recording_dirs:
        transcript_dir = rec_dir / "папка_с_транскрипцией"
        if not transcript_dir.exists():
            # Шукаємо транскрипцію напряму в папці
            txt_files = list(rec_dir.glob("*.txt"))
        else:
            txt_files = sorted(transcript_dir.glob("*.txt"))

        for txt_path in txt_files:
            try:
                text = txt_path.read_text(encoding="utf-8", errors="replace").strip()
                if not text or text in seen_content:
                    continue
                seen_content.add(text)
                results.append(TranscriptFile(
                    recording_name=rec_dir.name,
                    txt_path=txt_path,
                    text=text,
                ))
            except Exception as e:
                print(f"  [!] Пропуск {txt_path}: {e}")

    return results


# ══════════════════════════════════════════════════════════════════════════
# КЕШ
# ══════════════════════════════════════════════════════════════════════════

def load_cache(cache_path: Path) -> dict[str, dict]:
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache_path: Path, cache: dict, lock: Lock) -> None:
    with lock:
        try:
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"  [!] Кеш: помилка збереження: {e}")


# ══════════════════════════════════════════════════════════════════════════
# КЛАСИФІКАТОР (один виклик Claude)
# ══════════════════════════════════════════════════════════════════════════

def classify_single(
    tf: TranscriptFile,
    client: anthropic.Anthropic,
    cache: dict,
    cache_lock: Lock,
    cache_path: Path,
    index: int,
    total: int,
) -> ClassificationResult:
    """Класифікує один файл. Використовує кеш якщо є."""

    cache_key = str(tf.txt_path)

    # Перевірка кешу
    if cache_key in cache:
        d = cache[cache_key]
        with PRINT_LOCK:
            print(f"  [{index:3}/{total}] ⚡ КЕШ  {tf.recording_name[:55]:<55} → {CATEGORY_LABELS.get(d.get('category','?'), '?')}")
        return ClassificationResult(**d)

    # Обрізаємо транскрипцію якщо дуже довга (>6000 символів)
    text = tf.text
    if len(text) > 6000:
        text = text[:5800] + "\n... [скорочено]"

    user_msg = CLASSIFIER_USER_TEMPLATE.format(
        recording_name=tf.recording_name,
        text=text,
    )

    retries = 3
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model="claude-opus-4-8",
                max_tokens=800,
                system=CLASSIFIER_SYSTEM,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()

            # Очищаємо від можливих markdown огорток
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            data = json.loads(raw)

            # Валідація
            if data.get("category") not in ("STRONG", "SUPPORT", "NEUTRAL", "RISKY"):
                data["category"] = "NEUTRAL"
            data["score"] = max(1, min(10, int(data.get("score", 5))))

            result = ClassificationResult(
                recording_name=tf.recording_name,
                txt_path=str(tf.txt_path),
                category=data["category"],
                score=data["score"],
                reason=data.get("reason", ""),
                key_quotes=data.get("key_quotes", [])[:3],
                court_tip=data.get("court_tip", ""),
                folder_name_signal=data.get("folder_name_signal", ""),
            )

            # Зберігаємо в кеш
            with cache_lock:
                cache[cache_key] = asdict(result)
            save_cache(cache_path, cache, cache_lock)

            with PRINT_LOCK:
                icon = {"STRONG": "✅", "SUPPORT": "⚠️ ", "NEUTRAL": "🔍", "RISKY": "❌"}.get(result.category, "?")
                print(f"  [{index:3}/{total}] {icon} {tf.recording_name[:55]:<55} → score:{result.score:2} | {result.category}")

            return result

        except json.JSONDecodeError as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            with PRINT_LOCK:
                print(f"  [{index:3}/{total}] [!] JSON помилка: {tf.recording_name[:40]} → {e}")
            return ClassificationResult(
                recording_name=tf.recording_name,
                txt_path=str(tf.txt_path),
                category="NEUTRAL",
                score=5,
                reason="Помилка парсингу відповіді моделі",
                key_quotes=[],
                court_tip="Перевірити вручну",
                folder_name_signal="невідомо",
                error=str(e),
            )

        except anthropic.RateLimitError:
            wait = 20 * (attempt + 1)
            with PRINT_LOCK:
                print(f"  [{index:3}/{total}] ⏳ Rate limit, чекаємо {wait}s...")
            time.sleep(wait)

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
                continue
            with PRINT_LOCK:
                print(f"  [{index:3}/{total}] [!] Помилка: {tf.recording_name[:40]} → {e}")
            return ClassificationResult(
                recording_name=tf.recording_name,
                txt_path=str(tf.txt_path),
                category="NEUTRAL",
                score=5,
                reason=f"Помилка API: {e}",
                key_quotes=[],
                court_tip="Перевірити вручну",
                folder_name_signal="невідомо",
                error=str(e),
            )

    # fallback
    return ClassificationResult(
        recording_name=tf.recording_name,
        txt_path=str(tf.txt_path),
        category="NEUTRAL", score=5,
        reason="Всі спроби вичерпано",
        key_quotes=[], court_tip="Перевірити вручну",
        folder_name_signal="невідомо", error="max retries",
    )


# ══════════════════════════════════════════════════════════════════════════
# КОПІЮВАННЯ ФАЙЛІВ У СТРУКТУРОВАНІ ПАПКИ
# ══════════════════════════════════════════════════════════════════════════

def copy_results(
    results: list[ClassificationResult],
    output_dir: Path,
    transcripts: dict[str, TranscriptFile],
) -> None:
    """Копіює файли транскрипцій у відповідні папки за категорією."""

    for cat, dirname in CATEGORY_DIRS.items():
        (output_dir / dirname).mkdir(parents=True, exist_ok=True)

    for res in results:
        target_dir = output_dir / CATEGORY_DIRS[res.category]

        # Копіюємо .txt файл транскрипції
        src = Path(res.txt_path)
        if src.exists():
            # Ім'я файлу: score_назва.txt (для сортування)
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', res.recording_name)
            dest_name = f"score{res.score:02d}_{safe_name}.txt"
            dest = target_dir / dest_name
            shutil.copy2(src, dest)

        # Поруч зберігаємо міні-аналіз
        analysis_name = f"score{res.score:02d}_{safe_name}_АНАЛІЗ.txt"
        analysis_path = target_dir / analysis_name
        analysis_text = _format_single_analysis(res)
        analysis_path.write_text(analysis_text, encoding="utf-8")


def _format_single_analysis(res: ClassificationResult) -> str:
    lines = [
        f"ЗАПИС: {res.recording_name}",
        f"КАТЕГОРІЯ: {res.category_label}",
        f"ОЦІНКА: {res.score}/10",
        "",
        f"СИГНАЛ НАЗВИ ПАПКИ: {res.folder_name_signal}",
        "",
        f"ПРИЧИНА КЛАСИФІКАЦІЇ:",
        f"  {res.reason}",
        "",
        "КЛЮЧОВІ ЦИТАТИ:",
    ]
    for q in res.key_quotes:
        lines.append(f"  • «{q}»")
    if not res.key_quotes:
        lines.append("  (немає)")
    lines += [
        "",
        f"ПОРАДА ДЛЯ СУДУ:",
        f"  {res.court_tip}",
    ]
    if res.error:
        lines += ["", f"[!] ПОМИЛКА: {res.error}"]
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
# ГЕНЕРАЦІЯ ЗВІТІВ
# ══════════════════════════════════════════════════════════════════════════

def generate_full_table(results: list[ClassificationResult], output_dir: Path) -> None:
    """Таблиця всіх файлів з оцінками."""

    by_cat = {c: [] for c in CATEGORY_DIRS}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    lines = [
        "АНАЛІЗ ВСІХ ТРАНСКРИПЦІЙ",
        "=" * 80,
        f"Справа: {CASE['case_number']} | {CASE['article']}",
        f"Обвинувачений: {CASE['defendant']}",
        f"Дата аналізу: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        f"Всього файлів: {len(results)}",
        "=" * 80,
        "",
        "ЗВЕДЕНА СТАТИСТИКА:",
        f"  ✅ СИЛЬНІ ДОКАЗИ:    {len(by_cat['STRONG']):3} файлів",
        f"  ⚠️  ДОПОМІЖНІ:       {len(by_cat['SUPPORT']):3} файлів",
        f"  🔍 НЕЙТРАЛЬНІ:      {len(by_cat['NEUTRAL']):3} файлів",
        f"  ❌ РИЗИКОВІ:         {len(by_cat['RISKY']):3} файлів",
        "",
    ]

    for cat in ("STRONG", "SUPPORT", "NEUTRAL", "RISKY"):
        cat_results = sorted(by_cat[cat], key=lambda r: -r.score)
        lines += [
            "─" * 80,
            f"{CATEGORY_LABELS[cat]} ({len(cat_results)} файлів)",
            "─" * 80,
        ]
        for r in cat_results:
            lines += [
                f"  [{r.score:2}/10] {r.recording_name}",
                f"         {r.reason[:120]}",
                f"         Порада: {r.court_tip[:100]}",
                "",
            ]

    path = output_dir / "АНАЛІЗ_ВСІХ_ФАЙЛІВ.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  ✓ {path.name}")


def generate_strategy_report(results: list[ClassificationResult], output_dir: Path) -> None:
    """Стратегічний звіт для підготовки до суду."""

    strong  = sorted([r for r in results if r.category == "STRONG"],  key=lambda r: -r.score)
    support = sorted([r for r in results if r.category == "SUPPORT"], key=lambda r: -r.score)
    risky   = [r for r in results if r.category == "RISKY"]

    lines = [
        "╔══════════════════════════════════════════════════════════════════════╗",
        "║               СТРАТЕГІЧНИЙ ЗВІТ ДЛЯ ПІДГОТОВКИ ДО СУДУ            ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        "",
        f"Справа: {CASE['case_number']}",
        f"Засідання: {CASE['hearing_date']}, {CASE['court']}",
        f"Дата аналізу: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        "",
        "═" * 70,
        "1. ПРІОРИТЕТНІ ДОКАЗИ — НЕСТИ В СУД В ПЕРШУ ЧЕРГУ",
        "═" * 70,
        f"   (топ {min(10, len(strong))} з {len(strong)} сильних записів)",
        "",
    ]

    for i, r in enumerate(strong[:10], 1):
        lines += [
            f"  {i}. [{r.score}/10] {r.recording_name}",
            f"     ЧОМУ: {r.reason}",
        ]
        for q in r.key_quotes[:2]:
            lines.append(f"     ЦИТАТА: «{q[:100]}»")
        lines += [f"     ТАКТИКА: {r.court_tip}", ""]

    lines += [
        "═" * 70,
        f"2. ДОПОМІЖНІ ДОКАЗИ ({len(support)} файлів) — ДОДАТИ ДО ЗАГАЛЬНОГО КОНТЕКСТУ",
        "═" * 70,
        "",
    ]
    for r in support[:5]:
        lines += [
            f"  • [{r.score}/10] {r.recording_name}",
            f"    {r.reason[:100]}",
            "",
        ]
    if len(support) > 5:
        lines.append(f"  ... та ще {len(support)-5} файлів (повний список в АНАЛІЗ_ВСІХ_ФАЙЛІВ.txt)")
    lines.append("")

    lines += [
        "═" * 70,
        f"3. ⛔ РИЗИКОВІ ЗАПИСИ — НЕ НЕСТИ В СУД ({len(risky)} файлів)",
        "═" * 70,
        "   УВАГА: ці записи можуть нашкодити захисту!",
        "",
    ]
    for r in risky:
        lines += [
            f"  ❌ {r.recording_name}",
            f"     РИЗИК: {r.reason[:120]}",
            "",
        ]

    lines += [
        "═" * 70,
        "4. РЕКОМЕНДОВАНА СТРАТЕГІЯ ПОДАННЯ ДОКАЗІВ",
        "═" * 70,
        "",
        "  КРОК 1. На початку засідання подайте клопотання про долучення",
        f"          аудіозаписів. До клопотання включіть ТІЛЬКИ файли з папок",
        "          1_СИЛЬНІ_ДОКАЗИ та 2_ДОПОМІЖНІ_ДОКАЗИ.",
        "",
        "  КРОК 2. Пріоритет відтворення в залі суду (якщо суддя дозволить):",
    ]
    for i, r in enumerate(strong[:3], 1):
        lines.append(f"          {i}. {r.recording_name}")
        lines.append(f"             → {r.court_tip}")
    lines += [
        "",
        "  КРОК 3. Файли з 4_РИЗИКОВІ_НЕ_НЕСТИ — залишити вдома.",
        "          Якщо опонент згадає ці записи — заперечити їх контекст.",
        "",
        "═" * 70,
        "5. СТАТИСТИКА",
        "═" * 70,
        f"  Всього проаналізовано: {len(results)} файлів",
        f"  Корисних для захисту: {len(strong) + len(support)} ({(len(strong)+len(support))*100//max(len(results),1)}%)",
        f"  Ризикових: {len(risky)} ({len(risky)*100//max(len(results),1)}%)",
        f"  Середня оцінка сильних доказів: "
        f"{sum(r.score for r in strong)/max(len(strong),1):.1f}/10",
        "",
    ]

    path = output_dir / "ЗВІТ_ДЛЯ_СУДУ.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✓ {path.name}")


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Агент-Адвокат: автономна класифікація доказів"
    )
    parser.add_argument("--root",      type=str, default=str(DEFAULT_ROOT),
                        help="Директорія з записами")
    parser.add_argument("--output",    type=str, default=str(OUTPUT_DIR),
                        help="Директорія результатів")
    parser.add_argument("--workers",   type=int, default=8,
                        help="Кількість паралельних потоків (default: 8)")
    parser.add_argument("--no-cache",  action="store_true",
                        help="Ігнорувати кеш, аналізувати заново")
    parser.add_argument("--dry-run",   action="store_true",
                        help="Тільки скан, без Claude API")
    args = parser.parse_args()

    root_dir   = Path(args.root)
    output_dir = Path(args.output)

    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║          АГЕНТ-АДВОКАТ — АВТОНОМНИЙ КЛАСИФІКАТОР               ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"  Справа: {CASE['case_number']}")
    print(f"  Джерело: {root_dir}")
    print(f"  Результат: {output_dir}")
    print(f"  Потоки: {args.workers}")
    print()

    # ── Сканування ──────────────────────────────────────────────────────
    print("[1/4] СКАНУВАННЯ ТРАНСКРИПЦІЙ...")
    transcripts = scan_transcripts(root_dir)

    if not transcripts:
        print("[!] Транскрипцій не знайдено. Перевірте шлях.")
        sys.exit(1)

    print(f"  Знайдено транскрипцій: {len(transcripts)}")
    total_chars = sum(t.char_count for t in transcripts)
    print(f"  Загальний обсяг: {total_chars:,} символів")

    if args.dry_run:
        print("\n[DRY-RUN] Сканування завершено. API не викликається.")
        for t in transcripts:
            print(f"  • {t.recording_name} ({t.char_count:,} символів)")
        return

    # ── Кеш ─────────────────────────────────────────────────────────────
    cache_path = Path(args.output).parent / ".advocate_cache.json"
    cache = {} if args.no_cache else load_cache(cache_path)
    cache_lock = Lock()

    cached_count = sum(1 for t in transcripts if str(t.txt_path) in cache)
    print(f"  Кешовано: {cached_count}/{len(transcripts)}")
    print()

    # ── Claude client ────────────────────────────────────────────────────
    client = anthropic.Anthropic(
        http_client=httpx.Client(verify=False, timeout=120.0)
    )

    # ── Паралельна класифікація ──────────────────────────────────────────
    print(f"[2/4] КЛАСИФІКАЦІЯ (Claude Opus, {args.workers} потоків)...")
    print(f"  ✅=STRONG  ⚠️=SUPPORT  🔍=NEUTRAL  ❌=RISKY  ⚡=КЕШ")
    print()

    results: list[ClassificationResult] = []
    total = len(transcripts)

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                classify_single,
                tf, client, cache, cache_lock, cache_path, idx, total
            ): tf
            for idx, tf in enumerate(transcripts, 1)
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                tf = futures[future]
                print(f"  [!] Критична помилка для {tf.recording_name}: {e}")

    elapsed = time.time() - start_time
    print()
    print(f"  Класифікація завершена за {elapsed:.0f}с")

    # Статистика
    by_cat = {c: len([r for r in results if r.category == c]) for c in CATEGORY_DIRS}
    print(f"  ✅ STRONG:  {by_cat['STRONG']:3}  |  ⚠️  SUPPORT: {by_cat['SUPPORT']:3}"
          f"  |  🔍 NEUTRAL: {by_cat['NEUTRAL']:3}  |  ❌ RISKY: {by_cat['RISKY']:3}")
    print()

    # ── Копіювання файлів ────────────────────────────────────────────────
    print("[3/4] СОРТУВАННЯ У ПАПКИ...")
    output_dir.mkdir(parents=True, exist_ok=True)
    transcripts_by_path = {str(t.txt_path): t for t in transcripts}
    copy_results(results, output_dir, transcripts_by_path)
    print(f"  Файли скопійовано в: {output_dir}")
    print()

    # ── Генерація звітів ─────────────────────────────────────────────────
    print("[4/4] ГЕНЕРАЦІЯ ЗВІТІВ...")
    generate_full_table(results, output_dir)
    generate_strategy_report(results, output_dir)

    # ── Підсумок ─────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                        ГОТОВО!                                  ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Проаналізовано:  {len(results):3} файлів                                 ║")
    print(f"║  ✅ В суд:        {by_cat['STRONG']:3} сильних + {by_cat['SUPPORT']:3} допоміжних            ║")
    print(f"║  ❌ Не нести:     {by_cat['RISKY']:3} ризикових                             ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Папка: {str(output_dir)[:55]:<55} ║")
    print("╚══════════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
