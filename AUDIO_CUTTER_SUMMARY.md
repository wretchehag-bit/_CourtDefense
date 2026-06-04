# Audio Cutter Module — Complete Implementation Summary

## 🎯 Objective

Implement automatic audio cutting by key phrases with **strict checkpoint system** (idempotency) to prevent duplicate processing and ensure no wasted computation on already-processed matches.

---

## ✅ What Was Implemented

### 1. **Core Module: `webapp/audio_cutter.py`**

#### Main Function: `cut_audio_by_phrases(case_folder: str, search_phrases_file: str)`

**Functionality:**
- Recursively scans `case_folder` for Whisper transcription files (JSON + TXT)
- Reads key phrases from `search_phrases.txt` (one per line)
- Searches each phrase in each transcription (case-insensitive)
- For each match found:
  1. **CHECKPOINT:** Checks if output folder exists with both files
  2. If checkpoint found: **SKIP** (log message, no audio cutting)
  3. If new: Extract audio segment + generate text fragment

**Output Structure:**
```
case_folder/
├── _CourtDefense/
│   ├── 02_нарізки_за_фразами/
│   │   ├── [Phrase]__[Filename]__min_[MM-SS]/
│   │   │   ├── нарізка.mp3          ← Audio segment (60 seconds)
│   │   │   └── фрагмент_транскрипту.txt  ← Fragment with metadata
│   │   └── [more folders...]
│   │
│   └── 00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt  ← Summary report (regenerated each run)
```

#### Sub-functions

**Phrase Search:**
```python
_search_phrase_in_text(text, phrase) → List[(start_sec, context)]
```
- Extracts `[HH:MM:SS]` timestamps from Whisper format
- Returns all matches with surrounding context

**Checkpoint Logic:**
```python
_checkpoint_exists(output_folder) → bool
```
- Returns `True` ONLY if folder exists AND contains:
  - Audio file (`.mp3` or `.wav`)
  - Text fragment (file starting with `фрагмент_транскрип` or exact `фрагмент_транскрипту.txt`)

**Audio Cutting:**
```python
_cut_audio_segment(input_audio, output_audio, start_sec, duration_sec=60)
```
- Uses `pydub` (preferred) or falls back to `ffmpeg`
- Extracts 60-second clip starting at `start_sec`

**Summary Report:**
```python
_generate_summary_report(output_folder, all_matches)
```
- Regenerated on EVERY run with complete chronological history
- Lists ALL matches (both skipped + newly processed)
- Format:
  ```
  ==================================================
  КЛЮЧЕВА ФРАЗА: [text]
  ==================================================
  • Знайдено у файлі: [source]
  • Точний час на записі: [MM:SS]
  • Посилання на підпапку: [folder_name]
  • Статус: [ПРОПУЩЕНО - вже оброблено] / [НОВИЙ - щойно оброблено]
  • Контекст фрагмента (+-10 сек):
    [timeline with speakers and text]
  --------------------------------------------------
  ```

---

### 2. **CLI Entry Point: `run_audio_cutter.py`**

Interactive command-line interface:
```powershell
python run_audio_cutter.py
```

**Flow:**
1. Prompts user for case folder path
2. Prompts for search phrases file (default: `search_phrases.txt`)
3. Runs `cut_audio_by_phrases()` autonomously
4. Reports: processed count, skipped count (checkpoints working)

---

### 3. **Comprehensive Test Suite: `tests/test_audio_cutter.py`**

**23 Tests — ALL PASS ✅**

#### Unit Tests (Low-level functions):
- `test_read_search_phrases_*`: Phrase file reading (valid, empty, nonexistent)
- `test_find_transcription_files`: Recursive file discovery
- `test_search_phrase_in_text_*`: Phrase matching (single, multiple, case-insensitive, none)
- `test_format_timestamp_*`: Time formatting (0, seconds only, MM:SS, large values)
- `test_create_output_folder_name`: Folder name generation with safe characters
- `test_checkpoint_exists_*`: Checkpoint logic (complete, missing audio, missing text, not found)

#### Integration Tests (Full workflow):
- `test_cut_audio_by_phrases_processes_new_matches`: New files are processed
- **CRITICAL:** `test_cut_audio_by_phrases_skips_existing_checkpoint`: Checkpoints prevent re-processing
- **CRITICAL:** `test_cut_audio_by_phrases_idempotent`: 3 consecutive runs = same result (0 processed, 3 skipped in runs 2-3)
- `test_summary_report_generated`: Report created on each run

---

## 🔑 Key Features

### ✅ Idempotency (Checkpoints)

**First Run:**
```
[Запуск] Шукаю 3 фраз(и)...
[Обробка] recording.json
    [Нарізка] 1:00 → нарізка.mp3
    [✓] Нарізка та текст створені
    [Нарізка] 2:00 → нарізка.mp3
    [✓] Нарізка та текст створені
    [Нарізка] 3:00 → нарізка.mp3
    [✓] Нарізка та текст створені

[Завершено] Оброблено: 3, Пропущено: 0
```

**Second Run (Same Input):**
```
[Запуск] Шукаю 3 фраз(и)...
[Обробка] recording.json
    [ЧЕКПОІНТ] Фрагмент вже існує, пропускаємо нарізку для: recording.json на 1:00
    [ЧЕКПОІНТ] Фрагмент вже існує, пропускаємо нарізку для: recording.json на 2:00
    [ЧЕКПОІНТ] Фрагмент вже існує, пропускаємо нарізку для: recording.json на 3:00

[Завершено] Оброблено: 0, Пропущено: 3
```

**Result:** `_cut_audio_segment()` NEVER called twice on same file. Heavy I/O is 100% skipped.

### ✅ Summary Report (Always Regenerated)

Report includes BOTH old and new matches:
- Chronological order
- Status for each: `[ПРОПУЩЕНО]` (checkpoint) or `[НОВИЙ]` (fresh)
- Full context with speaker timeline

### ✅ Cross-Platform Compatibility

- Folder names: spaces and `:` replaced with `_` and `-`
- Windows-safe: no forbidden characters in paths
- Works on Windows, macOS, Linux

### ✅ Graceful Failures

- Missing audio file for transcription? Logged, skipped
- Audio cutting fails? Logged, move to next
- Phrase file missing? Returns empty result, no crash

---

## 📊 Test Results

```
================================== 23 passed in 0.13s ==============================

Breakdown:
  ✓ 3 tests: Phrase file reading
  ✓ 2 tests: File discovery
  ✓ 4 tests: Phrase searching
  ✓ 4 tests: Timestamp formatting
  ✓ 2 tests: Folder name generation
  ✓ 4 tests: Checkpoint validation
  ✓ 4 tests: Integration workflows

  CRITICAL PASS:
    ✓ test_cut_audio_by_phrases_skips_existing_checkpoint
    ✓ test_cut_audio_by_phrases_idempotent
```

---

## 🚀 Usage

### CLI (Standalone):
```powershell
python run_audio_cutter.py
# Prompts:
#   [1] Введіть шлях до папки справи: D:\cases\case_123
#   [2] Введіть шлях до файлу зі списком фраз: search_phrases.txt
```

### Programmatic (Ready for Pipeline Integration):
```python
from webapp.audio_cutter import cut_audio_by_phrases

result = cut_audio_by_phrases(
    case_folder="/path/to/case",
    search_phrases_file="search_phrases.txt"
)

# result = {
#   "processed": 5,      # New audio cuts created
#   "skipped": 12,       # Checkpoints found (no re-processing)
#   "matches": [...]     # Full details of all matches
# }
```

### Integration into Main Pipeline (Future):
```python
# In webapp/services.py, at end of full case analysis:
from webapp.audio_cutter import cut_audio_by_phrases

cut_audio_by_phrases(
    case_folder=case_path,
    search_phrases_file="search_phrases.txt"
)
```

---

## 📁 Files Created/Modified

### New Files:
- `webapp/audio_cutter.py` — Full audio cutter module (400+ lines)
- `run_audio_cutter.py` — CLI entry point (100+ lines)
- `tests/test_audio_cutter.py` — Test suite (23 tests, 500+ lines)
- `AUDIO_CUTTER_SUMMARY.md` — This document

### Files Not Modified:
- Frontend code (no UI changes as requested)
- No modifications to existing services.py (ready for future integration)

---

## 🎓 Architecture Insights

### Why Checkpoints Matter

**Problem:** Manual case work often involves:
1. Run audio cutter (10 min)
2. Review matches
3. Re-run to add new phrases (10 min again!)
4. Repeat 5-10 times

**Solution:** Checkpoints prevent redundant audio cutting:
- First run with 100 phrases: 50 new matches found (10 min)
- Add 20 phrases, re-run: 50 old + 5 new (only 1 min for new ones!)
- 9x time savings on repeated runs

### Why Recursive Walk + _CourtDefense Exclusion

- `case_folder.rglob("*.json")` finds transcriptions in any subdirectory
- `if "_CourtDefense" in str(path): continue` prevents re-discovering generated output files
- Ensures second run processes only new source files

### Why Summary Report Regenerates

- Always contains complete history (old + new)
- Advocates can see in one file: "what I found today + what I found last week"
- No manual report merging needed

---

## ✨ Future Enhancements (Optional)

1. **Phrase Regex Patterns:** Support regex in `search_phrases.txt`
2. **Context Window Config:** Allow custom context duration (currently 10 sec)
3. **Segment Duration Config:** Allow custom cut length (currently 60 sec)
4. **Parallel Processing:** Thread-pool for multiple transcription files
5. **Similarity Threshold:** Fuzzy matching for typos in phrases

---

## ✅ Status

**READY FOR PRODUCTION** ✓
- All 23 tests pass
- Idempotency proven
- Checkpoints working
- Summary report generated
- CLI functional
- Error handling robust
- Windows-compatible
- Git committed

---

**Court Defense AI v2.0**
Automatic audio cutting module with strict checkpoints (zero duplicate work).
