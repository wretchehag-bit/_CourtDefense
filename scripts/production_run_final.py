#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Production Batch Audio Cutter v3.0 — Two-Mode Pipeline with v2.2 safety.

MODE 1 — Timestamp cuts (phrases_example.txt):
  - Format:  "Description (MM:SS---MM:SS)"
  - Action:  ffprobe measures real duration, _clamp_segment auto-corrects
             out-of-range timestamps so FFmpeg never sees invalid input.
  - Output:  01_timestamp_cuts/<n>_<label>/нарізка.ext
             01_timestamp_cuts/<n>_<label>/фрагмент_транскрипту.txt  (always)

MODE 2 — Keyword search (phrases.txt):
  - Format:  plain text keyword per line (NO timestamps)
  - Action:  Search [HH:MM:SS] Whisper transcript for keyword hits,
             cut ±10 s context window around each hit.
  - Output:  02_keyword_cuts/<kw>__hit<n>/нарізка.ext
             02_keyword_cuts/<kw>__hit<n>/фрагмент_транскрипту.txt  (always)

Run:
    cd D:\\12314234\\trust
    python scripts/production_run_final.py

Output: $CASE_FOLDER/_CourtDefense/production_run_output/
Log:    <project_root>/logs/production_run.log
"""

import sys
import io
import re
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict

# ── UTF-8 stdout/stderr (Windows cp1252 can't handle Cyrillic) ───────────────
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

# ── sys.path bootstrap ───────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent   # scripts/
PROJECT_ROOT = SCRIPT_DIR.parent               # trust/
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from court_defense.core.audio_cutter import (
    _read_text_safe,
    _sanitize_folder_name,
    _extract_base_name,
    _cut_audio_segment,
    _resolve_ffmpeg_path,
    # v2.2 additions
    _get_audio_duration,
    _clamp_segment,
    _extract_transcript_context,
    _save_transcript_fragment,
    _write_summary_report,
)

# ── Paths (configure via CASE_FOLDER env variable) ───────────────────────────
# Set CASE_FOLDER before running:
#   Windows: $env:CASE_FOLDER = "D:\your\case\folder"
#   Linux:   export CASE_FOLDER=/home/user/case
_default_case = Path(__file__).resolve().parents[1] / "case_data"
CASE_FOLDER     = Path(os.environ.get("CASE_FOLDER", str(_default_case)))
PHRASES_TS_FILE = Path(os.environ.get("PHRASES_TS_FILE", str(CASE_FOLDER / "phrases_example.txt")))
PHRASES_KW_FILE = Path(os.environ.get("PHRASES_KW_FILE", str(CASE_FOLDER / "phrases_example.txt")))
OUTPUT_ROOT     = CASE_FOLDER / "_CourtDefense" / "production_run_output"
LOGS_DIR        = PROJECT_ROOT / "logs"
LOG_FILE        = LOGS_DIR / "production_run.log"

CONTEXT_WINDOW_S = 10
AUDIO_EXTS       = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}

# ── Cyrillic → ASCII transliteration (for output file/folder names) ──────────
_TRANSLIT = str.maketrans({
    'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','є':'ye','ж':'zh',
    'з':'z','и':'i','і':'i','ї':'yi','й':'y','к':'k','л':'l','м':'m',
    'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f',
    'х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch','ь':'','ю':'yu','я':'ya',
    'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Є':'Ye','Ж':'Zh',
    'З':'Z','И':'I','І':'I','Ї':'Yi','Й':'Y','К':'K','Л':'L','М':'M',
    'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F',
    'Х':'Kh','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Shch','Ь':'','Ю':'Yu','Я':'Ya',
    'э':'e','ё':'yo','ъ':'','Э':'E','Ё':'Yo','Ъ':'',
})

def _ascii(name: str) -> str:
    name = name.translate(_TRANSLIT)
    name = name.encode("ascii", errors="ignore").decode("ascii")
    name = re.sub(r"[\s_]+", "_", name).strip("_")
    return name or "seg"

# ── Logging ──────────────────────────────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
_log_fh = open(LOG_FILE, "a", encoding="utf-8")

def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] [{level:<7}] {msg}"
    try:
        _log_fh.write(line + "\n")
        _log_fh.flush()
    except Exception:
        pass
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("cp1252", errors="replace").decode("cp1252"))

def sep(title: str = "") -> None:
    log("=" * 72)
    if title:
        log(f"  {title}")
        log("=" * 72)

# ── Scanning ─────────────────────────────────────────────────────────────────

def scan_audio_and_dirs(folder: Path) -> Tuple[List[Path], int]:
    """Return (audio_files, subdir_count), skipping _CourtDefense trees."""
    audio: List[Path] = []
    dirs: set = set()
    for p in folder.rglob("*"):
        if "_CourtDefense" in str(p):
            continue
        if p.is_dir():
            dirs.add(p)
            continue
        if p.suffix.lower() not in AUDIO_EXTS:
            continue
        if "chunk" in p.name.lower() or "part_" in p.name.lower():
            continue
        audio.append(p)
    return sorted(audio), len(dirs)

# ── Transcript lookup ─────────────────────────────────────────────────────────

def find_transcript(audio: Path) -> Optional[Path]:
    """Locate .txt transcript for audio by base-name matching."""
    base = _extract_base_name(audio.name)
    # 1. Same dir, exact suffix swap
    same = audio.with_suffix(".txt")
    if same.exists():
        return same
    # 2. Same dir, flexible
    for txt in audio.parent.glob("*.txt"):
        t = _extract_base_name(txt.name)
        if base == t or base in t or t in base:
            return txt
    # 3. Global recursive fallback
    for txt in CASE_FOLDER.rglob("*.txt"):
        if "_CourtDefense" in str(txt):
            continue
        t = _extract_base_name(txt.name)
        if base == t or (base and base in t) or (t and t in base):
            return txt
    return None

# ── Phrase loaders ────────────────────────────────────────────────────────────

_TS_RE = re.compile(r"(\d{1,3}):(\d{2})---(\d{1,3}):(\d{2})")
_TC_RE = re.compile(r"\[(\d{2}):(\d{2}):(\d{2})\]")

def load_timestamp_phrases(path: Path) -> List[Tuple[str, int, int]]:
    if not path.exists():
        log(f"Timestamp file not found: {path}", "WARN")
        return []
    results: List[Tuple[str, int, int]] = []
    lines = _read_text_safe(path).splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].strip()
        if not raw or raw.startswith("#"):
            i += 1
            continue
        m = _TS_RE.search(raw)
        if m:
            sm, ss, em, es = map(int, m.groups())
            label = _TS_RE.sub("", raw).strip(" ()")
            results.append((label or f"seg_{sm:03d}{ss:02d}", sm*60+ss, em*60+es))
            i += 1
            continue
        if i + 1 < len(lines):
            m2 = _TS_RE.search(lines[i+1])
            if m2:
                sm, ss, em, es = map(int, m2.groups())
                results.append((raw, sm*60+ss, em*60+es))
                i += 2
                continue
        i += 1
    return results

def load_keywords(path: Path) -> List[str]:
    if not path.exists():
        log(f"Keywords file not found: {path}", "WARN")
        return []
    kws = []
    for ln in _read_text_safe(path).splitlines():
        ln = ln.strip().rstrip("-").strip()
        if ln and not ln.startswith("#"):
            kws.append(ln)
    return kws

def parse_timed_segments(text: str) -> List[Tuple[int, str]]:
    segs = []
    for line in text.splitlines():
        m = _TC_RE.match(line.strip())
        if m:
            h, mn, s = map(int, m.groups())
            segs.append((h*3600 + mn*60 + s, line[m.end():].strip()))
    return segs

def kw_hits(keyword: str, segs: List[Tuple[int, str]]) -> List[int]:
    kl = keyword.lower()
    return [sec for sec, txt in segs if kl in txt.lower()]

# ── Episode cut (v2.2-aware) ──────────────────────────────────────────────────

def process_episode(
    audio: Path,
    tx_text: str,
    episode_folder: Path,
    start_sec: int,
    end_sec: int,
    label: str,
    audio_duration: float,
    stats: Dict,
    all_episodes: List[Dict],
    mode: str,
) -> None:
    """
    Single episode: clamp → create folder → extract context →
    save фрагмент_транскрипту.txt → try FFmpeg cut → write ЗВІТ.
    Never raises; always writes the transcript fragment.
    """
    # 1. Clamp
    cs, ce, skip = _clamp_segment(start_sec, end_sec, audio_duration)
    if skip:
        dur_str = f"{audio_duration:.0f}s" if audio_duration > 0 else "unknown"
        log(
            f"    [ПРОПУСК] '{label}' "
            f"({start_sec//60}:{start_sec%60:02d}→{end_sec//60}:{end_sec%60:02d}) "
            f"за межами ({dur_str})",
            "WARN",
        )
        stats["skipped"] += 1
        return

    was_clamped = (cs != start_sec) or (ce != end_sec)
    if was_clamped:
        log(
            f"    [CLAMP] '{label}' "
            f"{start_sec//60}:{start_sec%60:02d}→{cs//60}:{cs%60:02d} / "
            f"{end_sec//60}:{end_sec%60:02d}→{ce//60}:{ce%60:02d}",
            "WARN",
        )

    # 2. Create episode subfolder (always)
    episode_folder.mkdir(parents=True, exist_ok=True)

    # 3. Extract transcript context
    ctx = _extract_transcript_context(tx_text, cs, ce)

    # 4. Save фрагмент_транскрипту.txt (ALWAYS, even if audio fails)
    _save_transcript_fragment(episode_folder, ctx, cs, ce)

    # 5. FFmpeg cut (isolated)
    audio_status = "Ошибка аудио"
    out_audio = episode_folder / f"нарізка{audio.suffix}"
    try:
        if _cut_audio_segment(audio, out_audio, cs, ce):
            audio_status = "OK"
            stats["cuts"] += 1
            log(f"    [OK] '{label}' {cs//60}:{cs%60:02d}→{ce//60}:{ce%60:02d}", "SUCCESS")
        else:
            stats["errors"] += 1
            log(f"    [ERR] FFmpeg failed: '{label}'", "ERROR")
    except Exception as exc:
        stats["errors"] += 1
        log(f"    [ERR] Audio export exception '{label}': {str(exc)[:100]}", "ERROR")

    # 6. Court report (always)
    report_text = (
        f"=== {label} ===\n"
        f"Режим: {mode}\n"
        f"Файл: {audio.name}\n"
        f"Час: {cs//60:02d}:{cs%60:02d} → {ce//60:02d}:{ce%60:02d}\n"
        f"Аудіо: {audio_status}\n"
        f"{'─'*60}\n"
        f"Транскрипція фрагмента:\n"
        f"{ctx if ctx else '[рядків не знайдено]'}\n"
    )
    (episode_folder / "ЗВІТ_ДЛЯ_СУДУ.txt").write_text(report_text, encoding="utf-8")

    # 7. Collect for summary
    all_episodes.append({
        "marker": label,
        "source": audio.name,
        "mode": mode,
        "start_sec": cs,
        "end_sec": ce,
        "original_start": start_sec,
        "original_end": end_sec,
        "was_clamped": was_clamped,
        "audio_status": audio_status,
        "context": ctx,
        "folder": str(episode_folder.relative_to(OUTPUT_ROOT)),
    })

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    run_start = datetime.now()
    _log_fh.write(f"\n{'#'*72}\n# RUN STARTED: {run_start.isoformat()}\n{'#'*72}\n")

    stats: Dict = {
        "run_started": run_start.isoformat(),
        "audio_found": 0,
        "subdirs_scanned": 0,
        "audio_with_transcript": 0,
        "audio_no_transcript": 0,
        "cuts": 0,
        "skipped": 0,
        "errors": 0,
        "keyword_hits_total": 0,
        "ts_phrases_loaded": 0,
        "kw_phrases_loaded": 0,
        "transcript_fragments_written": 0,
        "files": [],
    }
    all_episodes: List[Dict] = []

    # ── Stage 0: environment ──────────────────────────────────────────────────
    sep("STAGE 0 — Environment")
    log(f"Case folder  : {CASE_FOLDER}  (exists={CASE_FOLDER.exists()})")
    log(f"Mode 1 file  : {PHRASES_TS_FILE.name}  (exists={PHRASES_TS_FILE.exists()}, auto-skip if no timestamps)")
    log(f"Mode 2 file  : {PHRASES_KW_FILE.name}  (exists={PHRASES_KW_FILE.exists()})")
    log(f"FFmpeg       : {_resolve_ffmpeg_path()}")
    log(f"Output root  : {OUTPUT_ROOT}")
    log(f"Log file     : {LOG_FILE}")

    # ── Stage 1: load phrases ─────────────────────────────────────────────────
    sep("STAGE 1 — Loading phrase lists")
    ts_phrases = load_timestamp_phrases(PHRASES_TS_FILE)
    stats["ts_phrases_loaded"] = len(ts_phrases)
    log(f"Mode 1 timestamp phrases : {len(ts_phrases)}")
    for i, (lbl, s, e) in enumerate(ts_phrases[:4], 1):
        log(f"  {i}. '{lbl}'  [{s//60}:{s%60:02d}→{e//60}:{e%60:02d}]", "DEBUG")
    if len(ts_phrases) > 4:
        log(f"  … +{len(ts_phrases)-4} more", "DEBUG")

    kw_phrases = load_keywords(PHRASES_KW_FILE)
    stats["kw_phrases_loaded"] = len(kw_phrases)
    log(f"Mode 2 keyword phrases   : {len(kw_phrases)}")
    for i, kw in enumerate(kw_phrases[:6], 1):
        log(f"  {i}. '{kw}'", "DEBUG")
    if len(kw_phrases) > 6:
        log(f"  … +{len(kw_phrases)-6} more", "DEBUG")

    if not ts_phrases and not kw_phrases:
        log("No phrases loaded. Exiting.", "WARN")
        return

    # ── Stage 2: scan ─────────────────────────────────────────────────────────
    sep(f"STAGE 2 — Recursive scan of {CASE_FOLDER}")
    audio_files, subdir_count = scan_audio_and_dirs(CASE_FOLDER)
    stats["audio_found"] = len(audio_files)
    stats["subdirs_scanned"] = subdir_count
    log(f"Subdirectories scanned : {subdir_count}")
    log(f"Audio files found      : {len(audio_files)}")

    if not audio_files:
        log("No audio files found. Exiting.", "WARN")
        return

    # ── Stage 3: process ──────────────────────────────────────────────────────
    sep("STAGE 3 — Processing")
    fragments_before = 0

    for idx, audio in enumerate(audio_files, 1):
        log(f"\n[{idx}/{len(audio_files)}] {audio.name}")
        file_stat: Dict = {
            "file": str(audio.relative_to(CASE_FOLDER)),
            "duration_s": 0.0,
            "cuts": 0,
            "errors": 0,
        }

        transcript = find_transcript(audio)
        if transcript:
            stats["audio_with_transcript"] += 1
            log(f"  Transcript : {transcript.name}")
        else:
            stats["audio_no_transcript"] += 1
            log(f"  Transcript : [not found]", "WARN")

        # Get duration (v2.2 clamping)
        duration = _get_audio_duration(audio)
        file_stat["duration_s"] = round(duration, 1)
        if duration > 0:
            log(f"  Duration   : {duration:.1f}s ({duration/60:.1f} min)")
        else:
            log(f"  Duration   : unknown (ffprobe failed, clamping disabled)", "WARN")

        audio_stem = _ascii(_sanitize_folder_name(audio.stem, max_length=40))
        tx_text = _read_text_safe(transcript) if transcript else ""

        cuts_before = stats["cuts"]

        # ── Mode 1: timestamp cuts ────────────────────────────────────────────
        if ts_phrases:
            log(f"  MODE 1 : {len(ts_phrases)} timestamp phrase(s)")
            ts_out = OUTPUT_ROOT / audio_stem / "01_timestamp_cuts"
            for n, (label, start, end) in enumerate(ts_phrases, 1):
                ep_folder = ts_out / f"{n:03d}_{_ascii(_sanitize_folder_name(label, 45))}"
                process_episode(
                    audio, tx_text, ep_folder,
                    start, end, label, duration, stats, all_episodes, "MODE1_TIMESTAMP"
                )

        # ── Mode 2: keyword cuts ──────────────────────────────────────────────
        if kw_phrases and transcript and tx_text:
            segs = parse_timed_segments(tx_text)
            if segs:
                log(f"  MODE 2 : {len(kw_phrases)} keyword(s) in {len(segs)} timed lines")
                kw_out = OUTPUT_ROOT / audio_stem / "02_keyword_cuts"
                for kw in kw_phrases:
                    try:
                        hits = kw_hits(kw, segs)
                        if not hits:
                            continue
                        stats["keyword_hits_total"] += len(hits)
                        log(f"    KW '{kw}': {len(hits)} hit(s)")
                        kw_ascii = _ascii(_sanitize_folder_name(kw, 35))
                        for h_idx, hit_sec in enumerate(hits, 1):
                            ep_folder = kw_out / f"{kw_ascii}__hit{h_idx:02d}"
                            process_episode(
                                audio, tx_text, ep_folder,
                                max(0, hit_sec - CONTEXT_WINDOW_S),
                                hit_sec + CONTEXT_WINDOW_S,
                                f"{kw} @{hit_sec//60}:{hit_sec%60:02d}",
                                duration, stats, all_episodes, "MODE2_KEYWORD"
                            )
                    except Exception as exc:
                        log(f"    KW '{kw}' error: {exc}", "ERROR")
                        stats["errors"] += 1
            else:
                log(f"  MODE 2 : no [HH:MM:SS] lines in transcript", "WARN")
        elif kw_phrases and not transcript:
            log(f"  MODE 2 : skipped (no transcript)", "WARN")

        file_stat["cuts"] = stats["cuts"] - cuts_before
        file_stat["errors"] = stats["errors"]
        stats["files"].append(file_stat)

    # count фрагмент_транскрипту.txt files actually written
    frag_count = sum(
        1 for _ in OUTPUT_ROOT.rglob("фрагмент_транскрипту.txt")
    )
    stats["transcript_fragments_written"] = frag_count

    # ── Stage 4: summary report ───────────────────────────────────────────────
    _write_summary_report(OUTPUT_ROOT, all_episodes)
    vysnovok = OUTPUT_ROOT / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt"

    elapsed = (datetime.now() - run_start).total_seconds()
    stats["elapsed_seconds"] = round(elapsed, 1)
    stats["run_finished"] = datetime.now().isoformat()

    sep("FINAL REPORT")
    log(f"Elapsed                       : {elapsed:.1f}s  ({elapsed/60:.1f} min)")
    log(f"Subdirectories scanned        : {subdir_count}")
    log(f"Audio files found             : {stats['audio_found']}")
    log(f"  with transcript             : {stats['audio_with_transcript']}")
    log(f"  without transcript          : {stats['audio_no_transcript']}")
    log(f"Mode 1 timestamp phrases      : {stats['ts_phrases_loaded']}")
    log(f"Mode 2 keyword phrases        : {stats['kw_phrases_loaded']}")
    log(f"Keyword hits total            : {stats['keyword_hits_total']}")
    log(f"Total cuts (audio) created    : {stats['cuts']}")
    log(f"Skipped by clamping (v2.2)    : {stats['skipped']}  (no FFmpeg errors)")
    log(f"Audio errors                  : {stats['errors']}")
    log(f"фрагмент_транскрипту.txt files: {frag_count}")
    log(f"Summary report                : {'EXISTS' if vysnovok.exists() else 'MISSING'}")
    log(f"Output folder                 : {OUTPUT_ROOT}")

    report_path = OUTPUT_ROOT / "production_run_report.json"
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False, default=str)
        log(f"JSON report saved             : {report_path}", "SUCCESS")
    except Exception as exc:
        log(f"Could not write JSON report: {exc}", "WARN")

    status = "SUCCESS" if stats["errors"] == 0 else "PARTIAL"
    log(f"\nRUN STATUS: {status}")
    _log_fh.close()


if __name__ == "__main__":
    main()
