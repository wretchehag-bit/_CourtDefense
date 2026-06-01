# Court Defense AI System

AI-powered pipeline for legal defense case preparation under Ukrainian administrative law (КУпАП).

## What it does

1. **Transcribes** audio recordings using Whisper (GPU-accelerated)
2. **Classifies** each transcript as `STRONG / SUPPORT / NEUTRAL / RISKY` evidence via Claude API
3. **Analyzes** the full case (protocols, documents, transcripts) and generates a court document package

## Quick start

```bash
pip install -r requirements.txt

# Copy and fill in your case details
cp case_config.example.py case_config.py
# Edit case_config.py

# Set API key
export ANTHROPIC_API_KEY=sk-ant-...   # Linux/Mac
$env:ANTHROPIC_API_KEY="sk-ant-..."   # Windows PowerShell

# Launch web UI
python start_app.py
# → http://localhost:8000
```

## CLI usage

```bash
# Full pipeline (transcribe → classify → analyze)
python orchestrator.py

# Individual steps
python transcribe.py              # GPU transcription
python advocate_agent.py          # classify evidence
python defense_master.py          # generate document package
```

## Output

```
ПАКЕТ_ЗАХИСТУ/
  00_ШПАРГАЛКА_В_ЗАЛ_СУДУ.txt    ← one-page cheat sheet for court
  00_МАЙСТЕР_АНАЛІЗ.txt           ← full AI case analysis
  ДОКУМЕНТИ/
    01_ЗВЕДЕНІ_ПИСЬМОВІ_ПОЯСНЕННЯ.txt
    02_КЛОПОТАННЯ_АУДІОЗАПИСИ.txt
    03_КЛОПОТАННЯ_ПОВЕРНЕННЯ_ПРОТОКОЛУ.txt
    ...
```

## Requirements

- Python 3.10+
- NVIDIA GPU (optional, falls back to CPU)
- Anthropic API key
