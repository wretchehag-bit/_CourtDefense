# Court Defense AI System v2.0

AI-powered pipeline for legal defense case preparation under Ukrainian administrative law (КУпАП).

## What it does

1. **Transcribes** audio recordings using Whisper (GPU-accelerated)
2. **Extracts key phrases** from transcripts and cuts audio by critical moments (with checkpoints)
3. **Classifies** each transcript as `STRONG / SUPPORT / NEUTRAL / RISKY` evidence via Claude API
4. **Analyzes** the full case (protocols, documents, transcripts) and generates a court document package

---

## Installation

```powershell
# 1. Clone or extract repository
cd d:\12314234\trust

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set Anthropic API key
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # Windows PowerShell
# OR
export ANTHROPIC_API_KEY=sk-ant-...     # Linux/Mac

# 4. (Optional) Create case config
copy case_config_example.py case_config.py
# Then edit case_config.py with your case details
```

---

## How to Use

### **Option 1: Desktop Application (Recommended) 🖥️**

Native window with integrated web UI — no browser needed.

```powershell
python run_app.py
```

- ✅ Native window opens automatically
- ✅ FastAPI backend starts in background
- ✅ Ready immediately (no browser needed)
- ✅ Text selection enabled (advocates can copy-paste reports)
- ✅ Clean shutdown when you close the window

**Features available:**
- Upload audio files + documents
- Process entire case folders
- View real-time task status
- Download processed transcripts & analysis
- Convert PDFs to text (with OCR for scanned documents)

---

### **Option 2: Web UI in Browser**

```powershell
python start_app.py
```

- Opens browser at `http://localhost:8000`
- Same features as desktop app
- Choose this if you prefer browser interface

**Web UI includes:**
- File upload (audio + documents)
- Folder processing with progress tracking
- Task queue management
- Results download
- PDF conversion with Claude OCR

---

### **Option 3: Automatic Audio Cutting by Key Phrases 🎵**

Extract critical moments from transcripts automatically. Creates short audio clips + text fragments for each match.

```powershell
python run_audio_cutter.py
```

**Interactive prompts:**
```
Введіть шлях до папки справи: D:\cases\case_123
Введіть шлях до файлу зі списком фраз: search_phrases.txt
```

**What happens:**
1. ✅ Searches all transcriptions for key phrases
2. ✅ **Skips already-processed matches** (checkpoints prevent duplicate work)
3. ✅ Creates audio segments (60-second clips at each match)
4. ✅ Generates text fragments with context
5. ✅ Produces summary report with all findings

**Output structure:**
```
case_folder/
├── _CourtDefense/
│   ├── 02_нарізки_за_фразами/
│   │   ├── [Phrase]__[Filename]__min_[MM-SS]/
│   │   │   ├── нарізка.mp3                    ← 60-second audio clip
│   │   │   └── фрагмент_транскрипту.txt       ← Context + metadata
│   │   └── [more matches...]
│   │
│   └── 00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt    ← Summary (updated each run)
```

**Example `search_phrases.txt`:**
```
ключова фраза
важливе свідчення
порушення процедури
неправильне рішення
# Comments are ignored
```

**Key feature: Idempotency (Checkpoints)**
- First run: processes new matches
- Second run: **skips already-processed** → saves time!
- Result: no duplicate audio cutting, no wasted computation
- Example: 50 phrases → 3 new matches found → only those 3 are cut (not all 50)

---

### **Option 4: Full CLI Pipeline (Advanced)**

```powershell
# Process entire case: transcribe → classify → analyze
python orchestrator.py

# Individual components
python transcribe.py              # Audio transcription (GPU)
python advocate_agent.py          # Classify evidence (STRONG/SUPPORT/NEUTRAL/RISKY)
python defense_master.py          # Generate court documents
```

---

### **Option 5: Original Audio Splitter (Legacy)**

```powershell
python "import os.py"
```

Interactive menu to split audio files into chunks and transcribe.

---

## Workflow Example

### Scenario: Process a court case folder

```powershell
# 1. Start desktop app
python run_app.py

# 2. In the UI:
#    - Click "Pick Folder" → select your case folder
#    - Review audio files
#    - Click "Process" → transcription starts
#    - View results in real-time

# 3. After transcription is ready, extract key moments:
python run_audio_cutter.py
# Input: same case folder
# Input: search_phrases.txt (create with critical phrases)
# Output: short audio clips + text summaries in _CourtDefense/02_нарізки_за_фразами/

# 4. Review summary report
# → _CourtDefense/00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt
```

---

## Output Files

### **Full Case Analysis**
```
ПАКЕТ_ЗАХИСТУ/
├── 00_ШПАРГАЛКА_В_ЗАЛ_СУДУ.txt          ← One-page cheat sheet
├── 00_МАЙСТЕР_АНАЛІЗ.txt                ← Full AI analysis
└── ДОКУМЕНТИ/
    ├── 01_ЗВЕДЕНІ_ПИСЬМОВІ_ПОЯСНЕННЯ.txt
    ├── 02_КЛОПОТАННЯ_АУДІОЗАПИСИ.txt
    ├── 03_КЛОПОТАННЯ_ПОВЕРНЕННЯ_ПРОТОКОЛУ.txt
    └── ... (more court documents)
```

### **Audio Cutting Results**
```
_CourtDefense/
├── 02_нарізки_за_фразами/
│   └── [phrase]__[file]__min_[time]/
│       ├── нарізка.mp3
│       └── фрагмент_транскрипту.txt
└── 00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt   ← All findings (updated each run)
```

### **Transcriptions**
```
готовые_нарезки/
├── part_1_chunk.mp3 + part_1_transcript.txt
├── part_2_chunk.mp3 + part_2_transcript.txt
└── ... (one pair per audio segment)
```

---

## Requirements

- **Python** 3.10+
- **NVIDIA GPU** (optional — falls back to CPU automatically)
- **Anthropic API key** (for Claude analysis and PDF OCR)
- **ffmpeg** (for audio processing) — auto-installed via dependencies
- **pydub** (audio cutting) — included in requirements.txt

---

## Features

### Core System
- ✅ GPU-accelerated audio transcription (Whisper, `faster-whisper`)
- ✅ AI evidence classification (Claude API)
- ✅ PDF text extraction + OCR for scanned documents
- ✅ Automatic court document generation

### Audio Cutting Module (NEW)
- ✅ **Checkpoints (idempotency)** — never re-processes the same match
- ✅ Phrase-based audio segmentation with timestamps
- ✅ Automatic text fragment generation
- ✅ Comprehensive summary reports (regenerated each run)
- ✅ Windows-compatible folder naming

### Web UI
- ✅ File upload (audio + documents)
- ✅ Folder processing with progress tracking
- ✅ Real-time task status
- ✅ Results download
- ✅ PDF conversion with Claude OCR

### Desktop App
- ✅ Native window (Windows/macOS/Linux)
- ✅ Text selection enabled (copy-paste reports)
- ✅ Automatic backend startup
- ✅ Clean shutdown

---

## Tips

### For Advocates
1. Use **Desktop App** (`python run_app.py`) for daily work
2. Upload audio + case documents
3. Wait for transcription + analysis
4. Extract key moments with audio cutter
5. Download final documents for court

### For Bulk Processing
1. Use **Folder Processing** in web UI
2. Point to entire case directory
3. Let system process all files automatically
4. Review results in generated folders

### For Repeated Runs
1. Use **Audio Cutter** (`python run_audio_cutter.py`)
2. Add new phrases to `search_phrases.txt`
3. System skips already-found matches (checkpoints)
4. Only new phrases are processed → saves time

### Performance
- **Transcription:** ~30 min per hour of audio (GPU), ~2 hours (CPU)
- **Audio cutting:** Instant if checkpoints found, ~10 sec per new match
- **Analysis:** ~1 min per transcript (Claude API)

---

## Troubleshooting

### Port 8000 already in use
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### GPU not detected
System falls back to CPU automatically. For GPU acceleration:
```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

### API key errors
```powershell
# Verify API key is set
echo $env:ANTHROPIC_API_KEY    # Windows
echo $ANTHROPIC_API_KEY        # Linux/Mac

# Or set in current session
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

### Missing dependencies
```powershell
pip install -r requirements.txt --upgrade
```

---

## Documentation

- [Desktop App Setup](DESKTOP_APP_SETUP.md) — Full architecture & troubleshooting
- [Audio Cutter Guide](AUDIO_CUTTER_SUMMARY.md) — Checkpoints & phrase extraction
- [Deployment Summary](DEPLOYMENT_SUMMARY.md) — Integration details
- [CLAUDE.md](CLAUDE.md) — Developer instructions

---

## Support

For issues or questions:
- Check [GitHub Issues](https://github.com/anthropics/claude-code/issues)
- Review documentation files above
- Verify API key and dependencies

---

**Court Defense AI v2.0**
*AI-powered legal defense preparation. Ready for production.*
