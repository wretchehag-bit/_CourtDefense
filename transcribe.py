"""
Транскрипція аудіофайлів через Whisper (GPU або CPU)
====================================================
Сканує AUDIO_INPUT_DIR, транскрибує нові файли,
зберігає в Отсортированные_данные_для_суда у форматі для advocate_agent.

Використання:
  python transcribe.py                     # GPU якщо є, інакше CPU
  python transcribe.py --device cpu
  python transcribe.py --model large-v3
"""
import sys, re, time, argparse
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from case_config import AUDIO_INPUT_DIR
except ImportError:
    from case_config_example import AUDIO_INPUT_DIR  # type: ignore

SCRIPT_DIR  = Path(__file__).parent
OUTPUT_DIR  = SCRIPT_DIR / "Отсортированные_данные_для_суда"
AUDIO_EXTS  = {".m4a", ".mp3", ".wav", ".flac", ".ogg", ".aac", ".wma"}


def safe_name(stem: str) -> str:
    """Strip trailing dots/spaces that Windows forbids in dir names."""
    return re.sub(r'[\s.]+$', '', stem).strip()


def transcribe_file(audio: Path, model, output_dir: Path) -> bool:
    rec_name = safe_name(audio.stem)
    out_txt  = output_dir / rec_name / "папка_с_транскрипцией" / "part_01_chunk.txt"

    if out_txt.exists() and out_txt.stat().st_size > 100:
        print(f"  ⚡ вже є   {rec_name[:60]}")
        return True

    out_txt.parent.mkdir(parents=True, exist_ok=True)
    mb = audio.stat().st_size / 1024 / 1024
    print(f"  Транскрибую ({mb:.1f} MB): {rec_name[:55]}")
    t0 = time.time()

    segments, _ = model.transcribe(
        str(audio), language="uk", beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    lines = []
    for seg in segments:
        h = int(seg.start // 3600)
        m = int((seg.start % 3600) // 60)
        s = seg.start % 60
        lines.append(f"[{h:02d}:{m:02d}:{s:05.2f}] {seg.text.strip()}")

    text = "\n".join(lines)
    out_txt.write_text(text, encoding="utf-8")
    print(f"  ✓ {len(lines)} сегментів, {len(text):,} символів за {time.time()-t0:.0f}с")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default=str(AUDIO_INPUT_DIR), help="Папка з аудіо")
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    parser.add_argument("--model",  default="medium", help="Розмір моделі Whisper")
    parser.add_argument("--device", default="auto",   help="cuda / cpu / auto")
    args = parser.parse_args()

    input_dir  = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        print(f"[!] Папка не знайдена: {input_dir}")
        sys.exit(1)

    audio_files = sorted(f for f in input_dir.iterdir() if f.suffix.lower() in AUDIO_EXTS)
    if not audio_files:
        print(f"[!] Аудіофайлів не знайдено в {input_dir}")
        sys.exit(1)

    # Detect device
    device, compute = "cpu", "int8"
    if args.device == "auto" or args.device == "cuda":
        try:
            import torch
            if torch.cuda.is_available():
                device, compute = "cuda", "float16"
                print(f"  GPU: {torch.cuda.get_device_name(0)}")
        except ImportError:
            pass
    elif args.device == "cpu":
        device, compute = "cpu", "int8"

    print("╔══════════════════════════════════════════════════════╗")
    print("║   ТРАНСКРИПЦІЯ АУДІОЗАПИСІВ                         ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  Пристрій: {device.upper()} ({compute})")
    print(f"  Модель:   Whisper {args.model}")
    print(f"  Файлів:   {len(audio_files)}\n")

    from faster_whisper import WhisperModel
    print("  Завантажую модель...")
    model = WhisperModel(args.model, device=device, compute_type=compute)
    print("  Модель завантажена.\n")

    ok = 0
    for i, f in enumerate(audio_files, 1):
        print(f"  [{i}/{len(audio_files)}]", end=" ")
        if transcribe_file(f, model, output_dir):
            ok += 1

    print(f"\n  Готово: {ok}/{len(audio_files)}")
    print(f"  Результат: {output_dir}")


if __name__ == "__main__":
    main()
