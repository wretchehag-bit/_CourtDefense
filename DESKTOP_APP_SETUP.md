# Court Defense AI — Desktop Application Setup

## Quick Start

```powershell
python run_app.py
```

This launches the native desktop application with an integrated web UI.

## What Happens

1. **Backend Server** starts automatically on `http://127.0.0.1:8000`
   - Runs uvicorn in a background thread
   - Handles PDF processing, transcription analysis, and document generation

2. **Server Health Check** waits up to 30 seconds for the backend to become ready
   - Pings `http://127.0.0.1:8000/` until it responds
   - Prevents the GUI from opening before the API is available

3. **Native Window** (pywebview) opens at full size (1200×800)
   - Platform-native window (Windows, macOS, Linux)
   - Text selection enabled (advocates can select and copy report text)
   - Serves the web UI from the running backend

4. **Graceful Shutdown** when you close the window
   - Backend thread terminates cleanly
   - Port 8000 is released
   - No lingering processes

## Requirements

- Python 3.8+
- All dependencies from `requirements.txt`:
  ```powershell
  pip install -r requirements.txt
  ```

Key packages:
- `fastapi` — Web framework
- `uvicorn` — ASGI server
- `pywebview` — Native window wrapper
- `anthropic` — Claude API client
- `pdfplumber` — PDF text extraction
- `faster-whisper` — Audio transcription

## Troubleshooting

### "Backend failed to start (timeout)"
- Check that port 8000 is not already in use
- Verify `anthropic` package is installed
- Check logs for any import errors

### Window doesn't show
- Ensure X11 or Wayland is available (Linux)
- Try running `python start_app.py` instead to use browser

### Port 8000 already in use
Kill any lingering processes:
```powershell
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS
lsof -i :8000
kill -9 <PID>
```

## Architecture

```
run_app.py (Entry Point)
  ├─ Thread 1: uvicorn server (port 8000)
  │   └─ FastAPI app (webapp/main.py)
  │       ├─ PDF conversion (/convert-pdf)
  │       ├─ Audio processing (/upload)
  │       ├─ Task status (/status/{task_id})
  │       └─ Static files (index.html, CSS, JS)
  │
  └─ Main Thread: pywebview window
      └─ HTTP client to http://127.0.0.1:8000
```

## Testing

Run the integration test to verify everything works:
```powershell
python test_desktop_integration.py
```

Or run the pytest suite:
```powershell
python -m pytest tests/test_pipeline.py -v
```

## Notes

- The backend runs on `127.0.0.1:8000` (localhost only, not exposed to network)
- The window can be resized; the web UI is responsive
- Text selection is enabled to support advocate workflows (copy-paste into court documents)
- All data stays local; no files are uploaded to external services (except Claude API for OCR)
