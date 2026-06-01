# Court Defense AI — Android App

A WebView client for Court Defense AI.  
The heavy processing (Whisper transcription, Claude API) runs on a PC — the Android app is a full-featured mobile interface connecting over Wi-Fi.

---

## Architecture

```
[Android phone]  ←──── Wi-Fi ────→  [PC running CourtDefense.exe]
  WebView app                          FastAPI server :8000
  (this APK)                           Whisper + Claude
```

The phone and PC must be on the **same Wi-Fi network**.

---

## How to Build (Android Studio — free)

### Requirements
- [Android Studio](https://developer.android.com/studio) (free)
- JDK 11+ (bundled with Android Studio)
- Internet connection (first build downloads Gradle + dependencies)

### Steps

1. Open Android Studio
2. **File → Open** → select the `android/` folder
3. Wait for Gradle sync (first time: 2-5 min)
4. **Build → Build Bundle(s)/APK(s) → Build APK(s)**
5. APK is saved to:
   `android/app/build/outputs/apk/debug/app-debug.apk`
6. Transfer the APK to your phone and install it
   (Settings → Install unknown apps → allow)

### Build release APK (for distribution)

1. **Build → Generate Signed Bundle/APK**
2. Create a keystore (first time) → fill in details
3. Choose **APK** → Release
4. APK saved to: `android/app/build/outputs/apk/release/`

---

## How to Use

### On the PC
1. Run `CourtDefense.exe`
2. Click **▶ Start**
3. Find your PC's IP address:
   - Open CMD → type `ipconfig`
   - Look for **IPv4 Address** (e.g. `192.168.1.100`)

### On the Phone
1. Install `app-debug.apk`
2. Open **Court Defense AI**
3. Enter the PC's IP address: `192.168.1.100`
   (port 8000 is added automatically)
4. Tap **Connect**
5. The full web UI opens — upload files, view results

---

## Features

- Upload audio files and documents directly from phone storage
- Full pipeline: Transcription → Document extraction → Claude analysis
- PDF OCR for scanned documents
- Download generated analysis documents
- Saves server address — reconnects automatically on next launch
- Error page with retry when server is unreachable
- ⋮ menu → Reload / Change server

---

## File Structure

```
android/
  app/
    build.gradle              ← app config (version, SDK, deps)
    src/main/
      AndroidManifest.xml     ← permissions, activities
      java/ai/courtdefense/app/
        SplashActivity.java   ← launch screen
        SetupActivity.java    ← server URL entry screen
        MainActivity.java     ← main WebView + file chooser
      res/
        layout/               ← XML layouts
        values/               ← colors, strings, themes
        drawable/             ← icons and backgrounds
  build.gradle                ← project-level Gradle
  settings.gradle
  gradle.properties
```

---

## Troubleshooting

**"net::ERR_CONNECTION_REFUSED"**
→ CourtDefense.exe is not running, or wrong IP address.

**"net::ERR_ADDRESS_UNREACHABLE"**
→ Phone and PC are not on the same Wi-Fi network.

**Windows Firewall blocking the connection**
→ On the PC: Windows Defender Firewall → Allow an app → add `python.exe` for Private networks.
Or run in PowerShell (as admin):
```powershell
New-NetFirewallRule -DisplayName "CourtDefense" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

**File upload not working**
→ Grant "Files and media" permission in Android Settings → Apps → Court Defense AI → Permissions.
