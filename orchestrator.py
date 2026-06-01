"""
ОРКЕСТРАТОР — від аудіо до пакету документів для суду
Крок 1: Whisper GPU (RTX 3070) -> транскрипція 4 файлів 01.06.2026
Крок 2: advocate_agent   -> класифікація всіх транскрипцій
Крок 3: defense_master   -> аналіз справи + генерація документів
"""
import sys, os, time, subprocess
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SCRIPT_DIR  = Path(__file__).parent
SOURCE_DIR  = Path(r"D:\12314234\01.06.2026")
SORTED_DIR  = SCRIPT_DIR / "Отсортированные_данные_для_суда"
OUTPUT_DIR  = SCRIPT_DIR / "ВІДІБРАНІ_ДОКАЗИ"
PACKAGE_DIR = SCRIPT_DIR / "ПАКЕТ_ЗАХИСТУ"

FILES = [
    "20260530_222842_загальне_парирування_всіх_справ_і_пояснення_суті.m4a",
    "20260530_232313 поарирування 2 до 11.05.  .m4a",
    "20260531_000625_парирування_3_до_заяви_07_05_до_комплексу.m4a",
    "20260531_005544_парирування_4_до_комплксу_рукописному.m4a",
]

SEP = "=" * 65

def banner(text):
    print(f"\n{'╔' + '═'*63 + '╗'}")
    print(f"║  {text:<61}║")
    print(f"{'╚' + '═'*63 + '╝'}")

def step(n, total, text):
    print(f"\n[{n}/{total}] {text}")
    print("─" * 65)


# ══════════════════════════════════════════════════════════════════
# КРОК 1 — ТРАНСКРИПЦІЯ (GPU)
# ══════════════════════════════════════════════════════════════════

def transcribe_all():
    banner("КРОК 1/3 — ТРАНСКРИПЦІЯ  (Whisper medium, RTX 3070 GPU)")

    from faster_whisper import WhisperModel

    device, compute = "cpu", "int8"
    try:
        import torch
        if torch.cuda.is_available():
            device, compute = "cuda", "float16"
    except ImportError:
        pass

    print(f"  Завантажую модель ({device.upper()})...")
    t0 = time.time()
    model = WhisperModel("medium", device=device, compute_type=compute)
    print(f"  Модель завантажена за {time.time()-t0:.1f}с\n")

    done = 0
    for i, fname in enumerate(FILES, 1):
        audio = SOURCE_DIR / fname
        if not audio.exists():
            print(f"  [{i}/{len(FILES)}] [!] Не знайдено: {fname}")
            continue

        rec_name   = audio.stem.strip().rstrip(". ")
        tr_dir     = SORTED_DIR / rec_name / "папка_с_транскрипцией"
        out_txt    = tr_dir / "part_01_chunk.txt"

        if out_txt.exists() and out_txt.stat().st_size > 100:
            print(f"  [{i}/{len(FILES)}] ⚡ вже є  {rec_name[:55]}")
            done += 1
            continue

        tr_dir.mkdir(parents=True, exist_ok=True)
        mb = audio.stat().st_size / 1024 / 1024
        print(f"  [{i}/{len(FILES)}] Транскрибую ({mb:.1f} MB): {rec_name[:50]}")

        t1 = time.time()
        segments, info = model.transcribe(
            str(audio),
            language="uk",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )

        lines = []
        for seg in segments:
            h  = int(seg.start // 3600)
            m  = int((seg.start % 3600) // 60)
            s  = seg.start % 60
            lines.append(f"[{h:02d}:{m:02d}:{s:05.2f}] {seg.text.strip()}")

        text = "\n".join(lines)
        out_txt.write_text(text, encoding="utf-8")
        elapsed = time.time() - t1

        print(f"         ✓ {len(lines)} сегментів, {len(text):,} символів за {elapsed:.0f}с")
        done += 1

    print(f"\n  Транскрибовано: {done}/{len(FILES)} файлів")
    return done


# ══════════════════════════════════════════════════════════════════
# КРОК 2 — ADVOCATE AGENT
# ══════════════════════════════════════════════════════════════════

def run_advocate():
    banner("КРОК 2/3 — КЛАСИФІКАЦІЯ ДОКАЗІВ  (advocate_agent)")

    advocate = SCRIPT_DIR / "advocate_agent.py"
    result = subprocess.run(
        [sys.executable, str(advocate), "--no-cache"],
        cwd=str(SCRIPT_DIR),
        env={**os.environ},
    )
    return result.returncode == 0


# ══════════════════════════════════════════════════════════════════
# КРОК 3 — DEFENSE MASTER
# ══════════════════════════════════════════════════════════════════

def run_defense_master():
    banner("КРОК 3/3 — МАЙСТЕР-АНАЛІЗ + ПАКЕТ ДОКУМЕНТІВ  (defense_master)")

    master = SCRIPT_DIR / "defense_master.py"
    result = subprocess.run(
        [sys.executable, str(master)],
        cwd=str(SCRIPT_DIR),
        env={**os.environ},
    )
    return result.returncode == 0


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    t_start = time.time()

    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║        ОРКЕСТРАТОР ЗАХИСТУ — ПОВНИЙ ЦИКЛ                       ║")
    print("║        Справа: ВАД №973440/9648/9649 | 01.06.2026 10:00        ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print(f"\n  Джерело аудіо : {SOURCE_DIR}")
    print(f"  Транскрипції  : {SORTED_DIR}")
    print(f"  Результат     : {PACKAGE_DIR}")

    # ── Крок 1 ──────────────────────────────────────────────────
    done = transcribe_all()
    if done == 0:
        print("\n[!] Жодного файлу не транскрибовано. Зупиняємося.")
        sys.exit(1)

    # ── Крок 2 ──────────────────────────────────────────────────
    ok2 = run_advocate()
    if not ok2:
        print("\n[!] advocate_agent завершився з помилкою.")

    # ── Крок 3 ──────────────────────────────────────────────────
    ok3 = run_defense_master()

    # ── Підсумок ─────────────────────────────────────────────────
    total_min = (time.time() - t_start) / 60
    print()
    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║                     ВСЕ ГОТОВО!                                ║")
    print("╠═════════════════════════════════════════════════════════════════╣")
    print(f"║  Час виконання: {total_min:.1f} хв{'':<46}║")
    print("╠═════════════════════════════════════════════════════════════════╣")
    print(f"║  ВІДКРИТИ ЗАРАЗ:                                               ║")
    print(f"║  {str(PACKAGE_DIR / '00_ШПАРГАЛКА_В_ЗАЛ_СУДУ.txt')[:63]:<63}║")
    print(f"║  {str(PACKAGE_DIR / '00_МАЙСТЕР_АНАЛІЗ.txt')[:63]:<63}║")
    print(f"║  {str(PACKAGE_DIR / 'ДОКУМЕНТИ')[:63]:<63}║")
    print("╚═════════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
