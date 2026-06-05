"""Audio cutting by timestamps: FFmpeg-based evidence extraction.

ВАРТА v2.2 - Production module for audio cutting by timestamp markers.

KEY FEATURES:
1. Timestamp parsing: "1 marker text" + "15:48---15:56" → cut
2. Folder structure: [Marker]__[File]_[StartMinute]
3. Instant cut: FFmpeg stream copy (no re-encoding)
4. Smart search: Recursive across case folder, flexible prefix matching
5. 100% resilience: encoding fallback, FFmpeg autonomy, Windows safety

v2.2 ADDITIONS:
6. Time-bound clamping: auto-detects audio duration, clamps out-of-range timestamps
7. Transcript binding: extracts matching [HH:MM:SS] lines into фрагмент_транскрипту.txt
8. Audio-cut isolation: try/except around FFmpeg export; always writes transcript fragment
9. Guaranteed summary report: 00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt, append mode, never empty

ARCHITECTURE:
- _get_audio_duration():       ffprobe → float seconds (0.0 on failure = no clamping)
- _clamp_segment():            pure function, clamps [start, end] to [0, duration]
- _extract_transcript_context(): filter [HH:MM:SS] lines within time window
- _save_transcript_fragment(): always writes фрагмент_транскрипту.txt
- _write_summary_report():     append-mode summary; never overwrites with empty content
- _read_text_safe():           encoding resilience (UTF-8 → Windows-1251 → CP1252 → Latin1)
- _parse_timestamp_markers():  regex timestamp parsing
- _find_audio_for_transcript(): smart recursive audio search
- _extract_base_name():        base name extraction for flexible matching
- _cut_audio_segment():        FFmpeg stream copy
- _generate_court_report():    court-formatted report with context
- cut_audio_by_timestamps():   main pipeline
"""

import re
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from . import config

# Compiled once — [HH:MM:SS] timecode pattern used in Whisper transcripts
_TC_RE = re.compile(r'\[(\d{2}):(\d{2}):(\d{2})\]')


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg / FFprobe helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_ffmpeg_path() -> str:
    """Cascade FFmpeg resolution: system PATH → bundled → default."""
    return config.resolve_ffmpeg()


def _get_audio_duration(audio_path: Path) -> float:
    """Return audio duration in seconds via ffprobe.

    Tries the ffprobe binary alongside the bundled ffmpeg first,
    then falls back to the system 'ffprobe'.
    Returns 0.0 on any failure (safe: disables clamping, keeps old behaviour).
    """
    ffmpeg_exe = _resolve_ffmpeg_path()
    ffmpeg_p = Path(ffmpeg_exe)

    # Build candidate list: bundled ffprobe first, then system ffprobe
    suffix = ".exe" if os.name == "nt" else ""
    candidates: List[str] = []
    if ffmpeg_p.parent != Path("."):
        candidates.append(str(ffmpeg_p.parent / f"ffprobe{suffix}"))
    candidates.append("ffprobe")

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    for probe in candidates:
        try:
            cmd = [
                probe,
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(audio_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
                startupinfo=startupinfo,
            )
            if result.returncode == 0:
                raw = result.stdout.decode("utf-8", errors="replace").strip().splitlines()
                if raw:
                    return float(raw[0])
        except Exception:
            continue

    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Time-bound clamping
# ─────────────────────────────────────────────────────────────────────────────

def _clamp_segment(
    start_sec: int,
    end_sec: int,
    duration_sec: float,
) -> Tuple[int, int, bool]:
    """Clamp a [start, end] segment to [0, duration_sec].

    Returns:
        (clamped_start, clamped_end, should_skip)

    should_skip is True when:
    - the entire segment lies beyond the track end (start >= duration)
    - clamped_start >= clamped_end after clamping

    When duration_sec <= 0 (unknown), no clamping is applied and
    should_skip is always False (preserves original behaviour).
    """
    if duration_sec <= 0:
        return start_sec, end_sec, False

    duration_int = int(duration_sec)

    if start_sec >= duration_int:
        return start_sec, end_sec, True

    clamped_start = max(0, start_sec)
    clamped_end = min(end_sec, duration_int)

    if clamped_start >= clamped_end:
        return clamped_start, clamped_end, True

    return clamped_start, clamped_end, False


# ─────────────────────────────────────────────────────────────────────────────
# Transcript context extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_transcript_context(
    transcript_text: str,
    start_sec: int,
    end_sec: int,
) -> str:
    """Extract transcript lines whose [HH:MM:SS] timestamp falls within [start_sec, end_sec].

    Handles Whisper output format:
        [00:01:15] Рядок тексту тут.

    Returns matching lines joined by newline, or "" if none found.
    """
    if not transcript_text:
        return ""

    matching: List[str] = []
    for line in transcript_text.splitlines():
        m = _TC_RE.search(line)
        if m:
            h, mn, s = map(int, m.groups())
            offset = h * 3600 + mn * 60 + s
            if start_sec <= offset <= end_sec:
                matching.append(line.strip())

    return "\n".join(matching)


def _save_transcript_fragment(
    folder: Path,
    context_text: str,
    start_sec: int,
    end_sec: int,
) -> None:
    """Always write фрагмент_транскрипту.txt into folder.

    Guaranteed to create the file even when context_text is empty
    (in which case it records that no lines were found in this window).
    """
    def fmt(s: int) -> str:
        return f"{s // 60:02d}:{s % 60:02d}"

    header = f"Часовий діапазон: {fmt(start_sec)} → {fmt(end_sec)}\n{'─' * 60}\n"
    body = context_text if context_text else "[Рядків транскрипції у цьому діапазоні не знайдено]"

    fragment_file = folder / "фрагмент_транскрипту.txt"
    fragment_file.write_text(header + body, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Summary report
# ─────────────────────────────────────────────────────────────────────────────

def _write_summary_report(output_root: Path, episodes: List[Dict]) -> None:
    """Append a run block to 00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt.

    Append mode: never overwrites previous runs.
    Never writes an empty block (guards for empty episodes list).
    Each episode includes a "Контекст фрагмента" section with
    the extracted transcript text.
    """
    if not episodes:
        return

    def fmt(s: int) -> str:
        return f"{s // 60:02d}:{s % 60:02d}"

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = [
        "",
        "═" * 70,
        f"ЗАПУСК: {run_ts}   |   Оброблено епізодів: {len(episodes)}",
        "═" * 70,
    ]

    for i, ep in enumerate(episodes, 1):
        audio_status = ep.get("audio_status", "?")
        was_clamped = ep.get("was_clamped", False)
        clamp_note = ""
        if was_clamped:
            orig_s = ep.get("original_start", ep["start_sec"])
            orig_e = ep.get("original_end", ep["end_sec"])
            clamp_note = f"  [CLAMP] Оригінал: {fmt(orig_s)}→{fmt(orig_e)}"

        lines += [
            "",
            f"  {i}. {ep['marker']}",
            f"     Файл   : {ep['source']}",
            f"     Час    : {fmt(ep['start_sec'])} → {fmt(ep['end_sec'])}{clamp_note}",
            f"     Аудіо  : {audio_status}",
            f"     Папка  : {ep.get('folder', '—')}",
            "     Контекст фрагмента:",
        ]
        context = ep.get("context", "").strip()
        if context:
            for ctx_line in context.splitlines():
                lines.append(f"       {ctx_line}")
        else:
            lines.append("       [Текст транскрипції не знайдено]")
        lines.append("     " + "─" * 60)

    report_path = output_root / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt"
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Text / file utilities
# ─────────────────────────────────────────────────────────────────────────────

def _read_text_safe(file_path: Path, fallback_text: str = "") -> str:
    """Read text file with cascading encoding fallback.

    Order: UTF-8 → Windows-1251 → CP1252 → Latin1 → ASCII → UTF-8(replace).
    Never raises; returns fallback_text on complete failure.
    """
    if not file_path.exists():
        return fallback_text

    for enc in ("utf-8", "windows-1251", "cp1252", "latin1", "ascii"):
        try:
            with open(file_path, "r", encoding=enc, errors="strict") as fh:
                return fh.read()
        except (UnicodeDecodeError, LookupError, OSError):
            continue

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return fallback_text


def _sanitize_folder_name(text: str, max_length: int = 50) -> str:
    r"""Windows-safe folder name: replace forbidden chars < > : " / \ | ? * with _."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", text)
    sanitized = sanitized[:max_length]
    sanitized = sanitized.rstrip(". ")
    return sanitized if sanitized else "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Timestamp / marker parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_timestamp_markers(text: str) -> List[Tuple[str, int, int]]:
    """Parse timestamp markers from text.

    Accepted formats:
        1 marker description
        15:48---15:56

    or inline:
        1 marker description (15:48---15:56)

    Returns list of (marker, start_sec, end_sec).
    """
    markers: List[Tuple[str, int, int]] = []
    time_pattern = r"(\d{1,2}):(\d{2})---(\d{1,2}):(\d{2})"

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if not re.match(r"^\d{1,2}:\d{2}", line):
            marker = line
            # Two-line format: timestamp on next line
            if i + 1 < len(lines):
                m = re.search(time_pattern, lines[i + 1].strip())
                if m:
                    sm, ss, em, es = map(int, m.groups())
                    markers.append((marker, sm * 60 + ss, em * 60 + es))
                    i += 2
                    continue
            # Inline format: timestamp in parens on same line
            m = re.search(time_pattern, line)
            if m:
                sm, ss, em, es = map(int, m.groups())
                clean = re.sub(time_pattern, "", line).strip()
                clean = re.sub(r"\(\s*\)\s*$", "", clean).strip()
                if clean:
                    markers.append((clean, sm * 60 + ss, em * 60 + es))

        i += 1

    return markers


# ─────────────────────────────────────────────────────────────────────────────
# Audio file search
# ─────────────────────────────────────────────────────────────────────────────

def _extract_base_name(filename: str) -> str:
    """Extract base name for flexible audio ↔ transcript matching.

    Examples:
        "270520256_1648_АНАЛІЗ.txt" → "270520256_1648"
        "recording_chunk.json"      → "recording"
        "audio_part_1.mp3"          → "audio"
    """
    name = filename.rsplit(".", 1)[0] if "." in filename else filename
    name = re.sub(
        r"(_АНАЛІЗ|_chunk|_part_\d+|_chunk_\d+|_temp|_tmp).*$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    if re.search(r"_(?:chunk|part)_\d+$", name, flags=re.IGNORECASE):
        name = re.sub(r"_(?:chunk|part)_\d+$", "", name, flags=re.IGNORECASE)
    return name.strip("_").strip() or name


def _find_audio_for_transcript(transcript_path: Path, case_folder: Path) -> Optional[Path]:
    """Find audio file for a transcript via smart recursive search.

    Strategy:
    1. Same folder, same base name (any audio extension)
    2. Recursive search across case_folder, flexible base-name prefix matching
    3. Skips _CourtDefense output and chunk/part files
    """
    base_name = _extract_base_name(transcript_path.name)

    # 1. Same folder
    for ext in (".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"):
        candidate = transcript_path.parent / (base_name + ext)
        if candidate.exists():
            return candidate

    # 2. Recursive search
    audio_exts = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac"}
    for af in case_folder.rglob("*"):
        if af.name.startswith(".") or "_CourtDefense" in str(af):
            continue
        if "chunk" in af.name.lower() or "part_" in af.name.lower():
            continue
        if af.suffix.lower() not in audio_exts:
            continue

        af_base = _extract_base_name(af.name)
        if base_name in af_base or af_base in base_name:
            return af
        if base_name and af_base and base_name.split("_")[0] == af_base.split("_")[0]:
            return af

    return None


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg cutting
# ─────────────────────────────────────────────────────────────────────────────

def _cut_audio_segment(
    input_audio: Path,
    output_audio: Path,
    start_sec: int,
    end_sec: int,
) -> bool:
    """Cut audio segment using FFmpeg stream copy (no re-encoding).

    Uses -ss / -to with -c copy for near-instant lossless cuts.
    Returns True on success, False on any failure.
    """
    try:
        ffmpeg_exe = _resolve_ffmpeg_path()

        def sec_to_time(seconds: int) -> str:
            return f"{seconds // 60}:{seconds % 60:02d}"

        cmd = [
            ffmpeg_exe,
            "-ss", sec_to_time(start_sec),
            "-i", str(input_audio),
            "-to", sec_to_time(end_sec),
            "-c", "copy",
            "-y",
            str(output_audio),
        ]

        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,
            startupinfo=startupinfo,
        )

        if result.returncode != 0:
            err = (result.stderr or b"")[:400].decode("utf-8", errors="replace")
            print(f"[FFmpeg error] {err}")
            return False

        return True

    except FileNotFoundError:
        print("[Error] FFmpeg not found. Install FFmpeg or place it in ffmpeg/bin/")
        return False
    except subprocess.TimeoutExpired:
        print("[Error] FFmpeg timed out (> 5 min)")
        return False
    except Exception as exc:
        print(f"[Error] {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Court report
# ─────────────────────────────────────────────────────────────────────────────

def _generate_court_report(
    marker: str,
    source_file: str,
    start_sec: int,
    end_sec: int,
    context_text: str = "",
) -> str:
    """Generate a court-formatted report with timestamps and transcript context."""

    def fmt(s: int) -> str:
        return f"{s // 60:02d}:{s % 60:02d}"

    duration = end_sec - start_sec
    return (
        f"=== {marker} ===\n"
        f"Оригінальний запис: {source_file}\n"
        f"Час фрагмента на оригінальному записі: {fmt(start_sec)} ---> {fmt(end_sec)}\n"
        f"----------------------------------------------------------------------\n"
        f"[ХВИЛИНИ ДЛЯ ПРОСЛУХОВУВАННЯ В ЦЬОМУ НЕВЕЛИЧКОМУ ФРАГМЕНТІ]:\n"
        f"00:00 --- {fmt(duration)} хв\n"
        f"----------------------------------------------------------------------\n"
        f"ТРАНСКРИПЦІЯ ФРАГМЕНТА:\n"
        f"{context_text if context_text else '[Контекст недоступний]'}\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def cut_audio_by_timestamps(case_folder: str) -> Dict:
    """Main pipeline: process a case folder by timestamp markers.

    For each transcript with timestamp markers:
      1. Resolve the matching audio file.
      2. Get audio duration (ffprobe) for clamping.
      3. For each marker:
         a. Clamp timestamps to [0, duration]; log [ПРОПУСК] if out of range.
         b. Create episode subfolder (always).
         c. Extract transcript context lines for this window (always).
         d. Write фрагмент_транскрипту.txt (always, even on audio failure).
         e. Attempt FFmpeg cut (isolated try/except).
         f. Write ЗВІТ_ДЛЯ_СУДУ.txt (always).
      4. Append all episodes to 00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt (append mode).

    Returns stats dict with keys: success, processed, skipped, errors, episodes.
    """
    case_path = Path(case_folder)
    if not case_path.exists():
        print(f"[Error] Case folder does not exist: {case_folder}")
        return {"success": False, "processed": 0, "skipped": 0, "errors": 0}

    print(f"[Start] Processing case: {case_path.name}")

    output_root = case_path / "_CourtDefense" / "02_нарізки_за_фразами"
    output_root.mkdir(parents=True, exist_ok=True)

    transcript_files = [
        p for p in case_path.rglob("*.txt")
        if not p.name.startswith(".")
        and "_CourtDefense" not in str(p)
        and "chunk" not in p.name.lower()
        and "part_" not in p.name.lower()
    ]

    print(f"[Info] Found {len(transcript_files)} transcript(s)")

    stats: Dict = {
        "success": True,
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "episodes": [],
    }
    all_episodes: List[Dict] = []  # accumulate for summary report

    for trans_file in transcript_files:
        print(f"\n[Processing] {trans_file.name}")

        text = _read_text_safe(trans_file)
        if not text:
            print("  [Skip] Could not read file")
            stats["skipped"] += 1
            continue

        markers = _parse_timestamp_markers(text)
        if not markers:
            print("  [Info] No timestamp markers found")
            stats["skipped"] += 1
            continue

        print(f"  [Found] {len(markers)} marker(s)")

        audio_file = _find_audio_for_transcript(trans_file, case_path)
        if not audio_file:
            print(f"  [Error] Audio file not found for {trans_file.name}")
            stats["errors"] += 1
            continue

        print(f"  [Audio] {audio_file.name}")

        # Get duration once per audio file for clamping
        audio_duration = _get_audio_duration(audio_file)
        if audio_duration > 0:
            print(f"  [Duration] {audio_duration:.1f}s ({audio_duration / 60:.1f} min)")
        else:
            print("  [Duration] Unknown (ffprobe unavailable; clamping disabled)")

        for marker, start_sec, end_sec in markers:
            # ── 1. Clamp timestamps ───────────────────────────────────────────
            clamped_start, clamped_end, skip = _clamp_segment(
                start_sec, end_sec, audio_duration
            )

            if skip:
                dur_info = f"{audio_duration:.0f}s" if audio_duration > 0 else "unknown"
                print(
                    f"    [ПРОПУСК] '{marker}' "
                    f"({start_sec // 60}:{start_sec % 60:02d}–"
                    f"{end_sec // 60}:{end_sec % 60:02d}) "
                    f"— beyond audio duration ({dur_info})"
                )
                stats["skipped"] += 1
                continue

            was_clamped = (clamped_start != start_sec) or (clamped_end != end_sec)
            if was_clamped:
                print(
                    f"    [CLAMP] '{marker}' "
                    f"{start_sec // 60}:{start_sec % 60:02d}→"
                    f"{clamped_start // 60}:{clamped_start % 60:02d}, "
                    f"end {end_sec // 60}:{end_sec % 60:02d}→"
                    f"{clamped_end // 60}:{clamped_end % 60:02d}"
                )

            # ── 2. Create episode folder (always) ─────────────────────────────
            folder_name = (
                f"{_sanitize_folder_name(marker)}__"
                f"{_sanitize_folder_name(audio_file.stem)}_"
                f"{clamped_start // 60}"
            )
            episode_folder = output_root / folder_name
            episode_folder.mkdir(parents=True, exist_ok=True)

            # ── 3. Extract transcript context (always) ────────────────────────
            context_text = _extract_transcript_context(text, clamped_start, clamped_end)

            # ── 4. Save transcript fragment (always, even on audio failure) ───
            _save_transcript_fragment(
                episode_folder, context_text, clamped_start, clamped_end
            )

            # ── 5. Attempt FFmpeg cut (isolated) ──────────────────────────────
            audio_status = "Ошибка аудио"
            output_audio = episode_folder / f"нарізка{audio_file.suffix}"
            try:
                if _cut_audio_segment(
                    audio_file, output_audio, clamped_start, clamped_end
                ):
                    audio_status = "OK"
                    stats["processed"] += 1
                    print(
                        f"    [OK] '{marker}' "
                        f"({clamped_start // 60}:{clamped_start % 60:02d})"
                    )
                else:
                    stats["errors"] += 1
                    print(f"    [ERR] FFmpeg failed: '{marker}'")
            except Exception as exc:
                stats["errors"] += 1
                print(f"    [ERR] Audio export exception: {str(exc)[:120]}")

            # ── 6. Write court report (always) ────────────────────────────────
            report = _generate_court_report(
                marker, audio_file.name,
                clamped_start, clamped_end,
                context_text,
            )
            (episode_folder / "ЗВІТ_ДЛЯ_СУДУ.txt").write_text(
                report, encoding="utf-8"
            )

            # ── 7. Collect for summary report ─────────────────────────────────
            ep_record: Dict = {
                "marker": marker,
                "source": audio_file.name,
                "start_sec": clamped_start,
                "end_sec": clamped_end,
                "original_start": start_sec,
                "original_end": end_sec,
                "was_clamped": was_clamped,
                "audio_status": audio_status,
                "context": context_text,
                "folder": folder_name,
            }
            all_episodes.append(ep_record)
            stats["episodes"].append({
                "marker": marker,
                "folder": folder_name,
                "start_sec": clamped_start,
                "end_sec": clamped_end,
            })

    # ── Write guaranteed summary report ──────────────────────────────────────
    _write_summary_report(output_root, all_episodes)

    print(
        f"\n[Done] Processed: {stats['processed']}, "
        f"Skipped: {stats['skipped']}, "
        f"Errors: {stats['errors']}"
    )
    return stats
