# 🚀 Як запустити | How to Run

**Дата:** 2026-06-04  
**Версія:** 2.1

---

## 📋 Передумови

### Необхідне забезпечення:

1. **Python 3.10+**
   ```bash
   python --version  # Повинно бути >= 3.10
   ```

2. **pip** (зазвичай йде з Python)
   ```bash
   pip --version
   ```

3. **FFmpeg** (для нарізки аудіо)
   - Завантажити: https://ffmpeg.org/download.html
   - Розпакувати в `ffmpeg/bin/ffmpeg.exe` (Project root)
   - Або додати до системного PATH

4. **Залежності проекту**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🌐 Варіант 1: Веб-інтерфейс FastAPI (Рекомендовано)

### Запуск

```bash
python start_app.py
```

### Що відбувається

```
2026-06-04 10:45:30 INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Відкрити в браузері

```
http://localhost:8000
```

### Де знайти нарізку доказів

На **лівій панелі (sidebar)** буде раздел:

```
🎵 НАРІЗКА ДОКАЗІВ
━━━━━━━━━━━━━━━━━━━━━━━━
📁 Шлях до папки справи
[Вибрати] 📂

📄 Файл з часовими мітками
[search_phrases.txt]

[✂️ Запустити нарізку]
```

### Шаги

1. Нажать **"📁 Вибрати"** → выбрать папку с делом
2. Система перевірить доступність папки
3. Система перевірить наявність `search_phrases.txt`
4. Якщо все ОК → кнопка активуется
5. Нажать **"✂️ Запустити нарізку"**
6. Спостерігати прогрес у центральній панелі

### Результати

```
case_folder/
└── _CourtDefense/
    └── 02_нарізки_за_мітками/
        ├── фраза_1__recording__min_10-30/
        │   ├── нарізка.mp3
        │   ├── ШІ_АНАЛІТИКА_ФРАГМЕНТА.txt
        │   └── фрагмент_контексту.txt
        └── ...
```

---

## 📱 Варіант 2: Streamlit (Простіше для прототипування)

### Установка Streamlit

```bash
pip install streamlit
```

(Це може зайняти кілька хвилин перший раз)

### Запуск

```bash
streamlit run app_streamlit.py
```

### Що відбувається

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.1.x:8501
```

### Відкрити в браузері

```
http://localhost:8501
```

### UI в Streamlit

```
⚖️ Court Defense AI — Нарізка доказів
════════════════════════════════════════════

[SIDEBAR] Конфігурація     [MAIN] Результати
┌──────────────────────┐
│ 📁 Шлях до папки:    │
│ [input...]           │
│ [📁 Вибрати]         │
│                      │
│ 📄 Файл з фразами:   │
│ [search_phrases.txt] │
│                      │
│ [▶️ Запустити]       │
└──────────────────────┘

                        ✓ Папка знайдена
                        🎵 Аудіофайлів: 5
                        📄 Документів: 12

                        [▶️ Запустити нарізку]

                        ✅ Готово!
                        ┌─────────────────┐
                        │ Успішних: 8     │
                        │ Помилок: 0      │
                        │ Разом: 8        │
                        └─────────────────┘
```

### Переваги

- 🎨 **Простіший інтерфейс** — тільки необхідне
- 📊 **Вбудовані метрики** — красиво показуються результати
- 🔧 **Детальна інформація** — про файли в папці
- 💻 **Окремо від основного додатку** — можна запустити на іншому сервері

---

## 🐍 Варіант 3: Python API (Для інтеграції)

### Просто код

```python
from webapp.audio_cutter import cut_audio_by_timestamps

# Запустити нарізку
result = cut_audio_by_timestamps(
    case_folder="C:\\my_cases\\case_123"
)

# Отримати результати
stats = result.get("stats", {})
print(f"✅ Успішних: {stats['success']}")
print(f"❌ Помилок: {stats['errors']}")

# Отримати детальний звіт
report = result.get("report", "")
print(report)
```

### Для advanced користувачів

```python
from pathlib import Path
from webapp.audio_cutter import (
    _parse_timestamp_markers,
    _find_audio_for_transcript,
    _cut_audio_segment,
)

# Прочитати файл з фразами
case_folder = Path("C:\\cases\\case_123")
phrases_file = case_folder / "search_phrases.txt"
text = phrases_file.read_text(encoding='utf-8')

# Парсити маркери
markers = _parse_timestamp_markers(text)
print(f"Знайдено маркерів: {len(markers)}")

for marker, start_sec, end_sec in markers:
    print(f"  {marker}: {start_sec}s - {end_sec}s")

# Обробити кожен маркер
for marker, start_sec, end_sec in markers:
    # Знайти аудіофайл
    transcript_file = case_folder / "recording.json"
    audio_file = _find_audio_for_transcript(transcript_file, case_folder)
    
    if audio_file:
        output = case_folder / f"cut_{marker}.mp3"
        success = _cut_audio_segment(audio_file, output, start_sec, end_sec)
        print(f"  {'✓' if success else '✗'} {output.name}")
```

---

## 📝 Підготовка файлу фраз

### Створити файл `search_phrases.txt`

**В папці справи** (рядом з аудіо та документами):

```
1 батько бачив це особисто
08:45---08:55

2 свідок підтверджує алібі
15:30---15:45

3 прокурор припускає без доказів
22:15---22:25
```

### Правила формату

- **Формат 1 (рекомендовано):**
  ```
  Маркер на одному рядку
  HH:MM---HH:MM (або MM:SS---MM:SS)
  ```

- **Формат 2 (в одному рядку):**
  ```
  Маркер (MM:SS---MM:SS)
  ```

- **Приклади часів:**
  ```
  10:30---10:45     ✓ Valid
  1:05---1:25       ✓ Valid
  00:15---00:30     ✓ Valid
  15:45---16:10     ✓ Valid
  ```

---

## 🛠️ Встановлення FFmpeg

### Windows

1. Завантажити: https://ffmpeg.org/download.html
2. Вибрати **Windows build**
3. Розпакувати в папку проекту:
   ```
   Project/
   └── ffmpeg/
       └── bin/
           ├── ffmpeg.exe
           ├── ffplay.exe
           └── ffprobe.exe
   ```

**Або** додати до системного PATH:
- Windows + R → `sysdm.cpl`
- Environment Variables → PATH → Add → path to ffmpeg/bin

### macOS

```bash
brew install ffmpeg
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get install ffmpeg
```

### Linux (Fedora/RHEL)

```bash
sudo dnf install ffmpeg
```

### Перевірка

```bash
ffmpeg -version
# Має вивести версію FFmpeg
```

---

## 📦 Встановлення залежностей

### Перший раз

```bash
# Клонувати або завантажити проект
cd d:\12314234\trust

# Встановити залежності
pip install -r requirements.txt

# Для Streamlit (опціонально)
pip install streamlit
```

### requirements.txt містить

```
fastapi
uvicorn
faster-whisper
pdfplumber
anthropic
pywebview
```

---

## ✅ Перевірка установки

### Проверить Python

```bash
python --version
# Повинно бути >= 3.10
```

### Проверить pip

```bash
pip --version
```

### Проверить FFmpeg

```bash
ffmpeg -version
```

### Проверить залежності

```bash
pip list | grep -E "fastapi|uvicorn|whisper|anthropic"
```

### Проверить тести

```bash
pytest tests/ -v
# Повинно бути 41 passed
```

---

## 🚨 Решение проблем

### Проблема: "ModuleNotFoundError: No module named 'fastapi'"

**Решение:**
```bash
pip install -r requirements.txt
```

### Проблема: "FFmpeg not found"

**Решение:**
1. Скачайте FFmpeg: https://ffmpeg.org/download.html
2. Распакуйте в `ffmpeg/bin/ffmpeg.exe` (Project root)
3. Или добавьте в системный PATH

### Проблема: "Python version too old"

**Решение:**
1. Скачайте Python 3.10+: https://www.python.org/downloads/
2. Удалите старую версию
3. Установите новую

### Проблема: "Port 8000 is already in use"

**Решение:**
```bash
# Найти процесс на порту 8000
lsof -i :8000              # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Завершить процесс
kill -9 <PID>              # macOS/Linux
taskkill /PID <PID> /F     # Windows
```

### Проблема: "Streamlit command not found"

**Решение:**
```bash
pip install streamlit
```

---

## 🎯 Рекомендовані настройки

### Для локального використання

```bash
# FastAPI + Streamlit
python start_app.py         # Terminal 1
streamlit run app_streamlit.py  # Terminal 2
```

### Для production

```bash
# Тільки FastAPI
python start_app.py

# Або з gunicorn
pip install gunicorn
gunicorn webapp.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

---

## 📊 Приклад повної команди

### Terminal 1: Запустити FastAPI

```bash
cd d:\12314234\trust
python start_app.py
```

Вихід:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Terminal 2: (Опціонально) Запустити Streamlit

```bash
cd d:\12314234\trust
streamlit run app_streamlit.py
```

Вихід:
```
Local URL: http://localhost:8501
Network URL: http://192.168.1.x:8501
```

### Terminal 3: (Опціонально) Запустити Python скрипт

```bash
cd d:\12314234\trust
python your_script.py
```

---

## 💡 Рекомендації

1. **Для новачків:** Використовуйте **FastAPI UI** (відкрити в браузері)
2. **Для швидкого тесту:** Використовуйте **Streamlit** (простіший)
3. **Для інтеграції:** Використовуйте **Python API** (програмний доступ)

---

## 📞 Допомога

- **Документація:** [AUDIO_CUTTER_INTEGRATION.md](AUDIO_CUTTER_INTEGRATION.md)
- **Швидкий старт:** [AUDIO_CUTTER_QUICKSTART.md](AUDIO_CUTTER_QUICKSTART.md)
- **Email:** wretchehag@gmail.com

---

**Версія:** 2.1  
**Дата:** 2026-06-04  
✅ **Готово до використання!**
