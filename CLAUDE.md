# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

**Status**: ✅ Enterprise-grade refactoring complete (June 2026)

## What this project is

A professional multi-interface Python application for legal defense case analysis:
- **Audio Intelligence**: Transcribe court recordings (faster-whisper), extract evidence by timestamps
- **Document Analysis**: Process PDFs, contracts, witness statements via Claude API
- **Case Strategy**: AI-powered defense analysis and argument generation
- **Multi-UI**: Desktop app (pywebview), Web UI (FastAPI), CLI (Streamlit alternative)
- **Production Ready**: PyInstaller standalone .exe for Windows distribution

Audio is court-proceeding recordings in Ukrainian/Russian/mixed language.

## Running the application

### Production: Standalone .exe
```powershell
dist\CourtDefense.exe
# OR
dist\RUN_ME.bat
```
- Single 2.7GB executable
- No Python installation required
- Full-featured desktop application
- Works on Windows 7+ (64-bit)

### Development: Desktop App
```powershell
python run_app.py
# Requires: sys.path has src/ for court_defense imports
```

### Development: Web UI
```powershell
python start_app.py
# Opens http://localhost:8000 in browser
```

### Development: Streamlit
```powershell
streamlit run app_streamlit.py
# Alternative UI (http://localhost:8501)
```

### Development: CLI Audio Cutter
```powershell
python run_audio_cutter.py
# Interactive menu for evidence extraction
```

## Key dependency

```
faster-whisper
```

Install with: `pip install faster-whisper`

## Directory layout (Enterprise Architecture)

```
d:\...\trust/
├── src/court_defense/          ← Installable package
│   ├── api/                    ← FastAPI endpoints + static UI
│   │   ├── main.py
│   │   └── static/index.html
│   └── core/                   ← Business logic (no UI)
│       ├── audio_cutter.py
│       ├── services.py
│       └── config.py           ← Central config + resource_path()
├── tests/                      ← 41 passing tests
├── docs/                       ← All documentation
├── scripts/
│   ├── build.ps1               ← PyInstaller build script
│   └── legacy/                 ← Legacy standalone scripts
├── assets/CourtDefense.spec    ← PyInstaller configuration
├── dist/CourtDefense.exe       ← Production standalone app
│
├── Entry Points:
│   ├── run_app.py              ← Desktop (pywebview + FastAPI)
│   ├── start_app.py            ← Web UI (FastAPI + browser)
│   ├── app_streamlit.py        ← Streamlit alternative
│   └── run_audio_cutter.py     ← CLI audio extraction
│
└── Configuration:
    ├── case_config_example.py  ← Template (copy to case_config.py)
    ├── case_config.py          ← User's private config (gitignored)
    ├── pyproject.toml          ← Poetry package config
    └── .python-version         ← Python 3.11.9

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
