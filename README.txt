================================================================================
  Court Defense AI  —  Quick Start Guide
================================================================================

FIRST LAUNCH (one-time setup, ~5-15 min)
─────────────────────────────────────────
  1. Run  CourtDefense.exe
  2. Click  "⚙ Install Dependencies"
     → Downloads Python packages (torch, whisper, etc.)
     → Progress is shown in the log window
     → Internet connection required for this step
  3. Enter your Anthropic API Key
     → Get one at: console.anthropic.com  (Billing → API Keys)
     → The key is saved automatically — you won't need to enter it again
  4. Click  "▶ Start"
     → The browser opens automatically at http://localhost:8000

EVERY NEXT LAUNCH
─────────────────
  Just run  CourtDefense.exe  — the server starts and the browser opens.

--------------------------------------------------------------------------------

HOW TO USE THE APP
──────────────────
  ANALYZE A CASE
    1. Drag & drop your files into the upload zone (audio + documents together)
    2. Click "Upload and run analysis"
    3. Wait for the pipeline to finish (Transcription → Documents → Claude)
    4. Download the results:  00_ANALYSIS.txt  +  00_CHEAT_SHEET.txt

  CONVERT A LARGE PDF TO TEXT  (scanned / handwritten, 100+ pages)
    1. Go to the "PDF → Text (OCR)" section in the sidebar
    2. Drop your PDF file
    3. Click "Recognize text"
    4. Download the extracted  *_text.txt  file
    5. Use that text file in the main analysis if needed

  SUPPORTED FILE TYPES
    Audio:     .m4a  .mp3  .wav  .flac  .ogg  .aac  .wma
    Documents: .pdf  .docx  .txt

--------------------------------------------------------------------------------

FOLDER STRUCTURE
────────────────
  CourtDefense.exe      ← launcher (run this)
  webapp\               ← web application (do not delete)
  requirements.txt      ← package list (do not delete)
  case_config_example.py← template for case settings (optional)
  jobs\                 ← your results appear here after each run
  .venv\                ← installed packages (do not delete)
  .launcher_settings.json ← saved API key and port (auto-created)

--------------------------------------------------------------------------------

OPTIONAL: CONFIGURE YOUR CASE
──────────────────────────────
  Copy  case_config_example.py  →  case_config.py
  Fill in your case details (defendant name, case number, court, etc.)
  The AI will include this context in every analysis automatically.

--------------------------------------------------------------------------------

TROUBLESHOOTING
───────────────
  "Port already in use"
    → Change the port in the launcher (e.g. 8001) and restart.

  "API balance is too low"
    → Top up at console.anthropic.com → Billing.

  Analysis seems wrong or missing
    → Check that ANTHROPIC_API_KEY is set correctly in the launcher.
    → Make sure the audio language setting matches your recordings (Ukrainian).

  PDF shows no text extracted
    → It is a scanned document — use the "PDF → Text (OCR)" tool first.

  Need to reinstall packages
    → Delete the  .venv\  folder, then click "⚙ Install Dependencies" again.

--------------------------------------------------------------------------------

REQUIREMENTS
────────────
  Windows 10 / 11  (64-bit)
  Internet connection (first launch only + each AI analysis call)
  Anthropic API key  (console.anthropic.com)
  GPU optional — CPU mode works, transcription will be slower

================================================================================
  Court Defense AI  |  Powered by Claude (Anthropic) + Whisper
================================================================================
