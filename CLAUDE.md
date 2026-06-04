# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A single-file Python CLI tool (`import os.py`) that:
1. Scans the parent directory for audio files (MP3, M4A, WAV, FLAC, WMA, OGG, AAC) and ZIP archives containing audio
2. Presents an interactive numbered menu for file selection
3. Splits the chosen file into 5 equal byte-chunks
4. Transcribes each chunk via `faster-whisper` (model: `medium`, device: `cpu`, compute_type: `int8`)
5. Writes chunked audio and timestamped `.txt` transcripts into `готовые_нарезки/`

Audio is court-proceeding recordings in Ukrainian/surzhyk.

## Running the application

### Native Desktop App (recommended)
```powershell
python run_app.py
```
- Launches native window (Windows/macOS/Linux)
- Auto-starts FastAPI backend on port 8000
- Allows text selection in reports (critical for advocates)
- Clean shutdown when window closes

### Web UI (browser-based)
```powershell
python start_app.py
```
Opens browser at `http://localhost:8000`

### CLI Tool (legacy)
```powershell
python "import os.py"
```
Interactive menu for audio splitting and transcription.

## Key dependency

```
faster-whisper
```

Install with: `pip install faster-whisper`

## Directory layout

- `run_app.py` — **Entry point for native desktop app** (pywebview + FastAPI)
- `start_app.py` — Entry point for web UI (FastAPI in browser)
- `import os.py` — the original single-file CLI tool (keep the name as-is)
- `transcribe.py` — standalone transcription script (GPU/CPU auto-detect)
- `advocate_agent.py` — parallel Claude classifier for transcripts
- `defense_master.py` — full case analysis + document generator
- `lawyer_analyzer.py` — combined analyzer + court document writer
- `orchestrator.py` — end-to-end pipeline runner
- `pipeline.py` — legacy pipeline (ffmpeg + whisper + sort)
- `webapp/` — FastAPI application (main.py, services.py, static/)
- `tests/test_pipeline.py` — Unit tests for PDF processing and API validation
- `case_config_example.py` — **template**: copy to `case_config.py` and fill in case data
- `case_config.py` — user's private config (gitignored, never committed)
- `готовые_нарезки/` — output: `part_N_chunk.<ext>` + `part_N_transcript.txt`
- `Отсортированные_данные_для_суда/` — input recordings

## First-time setup for new users

1. Copy `case_config_example.py` → `case_config.py`
2. Fill in `CASE` dict and path variables in `case_config.py`
3. `pip install -r requirements.txt`
4. `python start_app.py`  (web UI) or run individual scripts

## Known design quirks

- `case_config.py` is gitignored — each user keeps their own private copy.
- Audio is split by **byte offset**, not by time — chunk boundaries may fall mid-word.
- The script resolves its working directory at runtime: if run from inside `нарезки/`, it scans the parent folder for source audio; otherwise it scans the current directory.
- Whisper model is always loaded fresh on each run (no caching between runs).
- GPU (CUDA) is auto-detected; falls back to CPU automatically if not available.
