# Court Defense AI — Standalone Android App

Fully standalone — no PC required. The app calls cloud APIs directly from your phone.

## Architecture

```
Android Phone
  ├── Audio files  →  OpenAI Whisper API  →  transcript text
  ├── PDF files    →  Anthropic Files API →  Claude reads natively
  ├── DOCX/TXT     →  parsed on device
  └── All text     →  Claude (Anthropic API)  →  full analysis
```

Internet connection required (for API calls). No PC needed.

---

## API Keys Required

| Key | Where to get | Required? |
|-----|-------------|-----------|
| Anthropic API key | console.anthropic.com → API Keys | **Yes** |
| OpenAI API key | platform.openai.com → API keys | Only for audio |

**Without OpenAI key** — audio files are skipped, PDF/DOCX/TXT work fine.

---

## How to Build

### Requirements
- [Android Studio](https://developer.android.com/studio) (free)
- JDK 11+ (bundled with Android Studio)

### Steps
1. Open Android Studio
2. **File → Open** → select `android_standalone/` folder
3. Wait for Gradle sync (~2-5 min first time)
4. **Build → Build Bundle(s)/APK(s) → Build APK(s)**
5. APK: `app/build/outputs/apk/debug/app-debug.apk`
6. Transfer to phone → install (allow unknown sources)

---

## How to Use

1. Open **Court Defense AI** on your phone
2. Tap ⚙ Settings → enter API keys → Save
3. Tap **＋ Add Files** → select audio/PDF/DOCX/TXT files
4. Tap **▶ Analyze**
5. Watch progress in the log area
6. Results open automatically — Copy / Share / Save

---

## File Size Limits

| Type | Limit | Notes |
|------|-------|-------|
| Audio | 25 MB | Whisper API limit per file |
| PDF | ~20 MB | Anthropic Files API |
| DOCX/TXT | Unlimited | Processed on device |

For audio > 25 MB, split the file first (e.g. with a audio editor app).

---

## Project Structure

```
android_standalone/
  app/src/main/
    java/ai/courtdefense/standalone/
      MainActivity.java      ← file picker + start screen
      SettingsActivity.java  ← API key entry
      ResultActivity.java    ← shows analysis (copy/share/save)
      PipelineRunner.java    ← core pipeline logic
      AnthropicClient.java   ← Claude + Files API calls
      WhisperClient.java     ← OpenAI Whisper API calls
      FileHelper.java        ← DOCX parsing, URI reading
      FileAdapter.java       ← file list UI
    res/layout/              ← XML layouts
    res/values/              ← colors, strings, themes
    AndroidManifest.xml
  app/build.gradle
  build.gradle / settings.gradle
```
