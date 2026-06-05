# 📦 Poetry + Pyenv Setup | Професійний стек розробки

**Дата:** 2026-06-04  
**Версія:** 2.1.1  
**Статус:** ✅ Production Ready

---

## 🎯 Чому Poetry + Pyenv?

### ✅ Переваги

| Аспект | Раніше (pip) | Тепер (Poetry) |
|--------|--------------|----------------|
| **Відтворюваність** | ❌ Часто різняться версії | ✅ Детермінований `poetry.lock` |
| **Ізоляція** | ❌ Глобальне або venv | ✅ Повна ізоляція в проекті |
| **Python версія** | ❌ Вручну вибиратись | ✅ Автоматично через pyenv |
| **Залежності** | ❌ `requirements.txt` непоточний | ✅ `pyproject.toml` + `poetry.lock` |
| **Команди** | ❌ `pip install` | ✅ `poetry add`, `poetry update` |
| **Ліцензування** | ❌ Не відстежується | ✅ Чітко визначено |
| **Збірка** | ❌ Складна конфіг | ✅ Вбудована підтримка |

---

## 🚀 Крок 1: Встановлення pyenv

### Windows

**Вариант А: Через Chocolatey (рекомендовано)**
```powershell
choco install pyenv-win
# Або якщо не маєте Chocolatey:
# https://chocolatey.org/install
```

**Вариант Б: Вручну з GitHub**
```powershell
git clone https://github.com/pyenv-win/pyenv-win.git "$env:USERPROFILE\.pyenv"

# Додати до PATH
$env:Path += ";$env:USERPROFILE\.pyenv\bin"
$env:Path += ";$env:USERPROFILE\.pyenv\shims"
```

### macOS / Linux

```bash
# macOS (Homebrew)
brew install pyenv

# Linux (Ubuntu/Debian)
curl https://pyenv.run | bash
```

### Перевірка

```bash
pyenv --version
# Повинно вивести: pyenv 2.X.X
```

---

## 🚀 Крок 2: Встановлення Python 3.11.9

```bash
# Скачати та встановити Python 3.11.9
pyenv install 3.11.9

# Перевірити
pyenv versions
# Повинно показати: * 3.11.9 (set by /path/to/.python-version)
```

Система автоматично прочитає `.python-version` і активує правильну версію!

---

## 🚀 Крок 3: Встановлення Poetry

### Windows

```powershell
# PowerShell (Administrator)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Додати Poetry до PATH
$env:Path += ";$env:APPDATA\Python\Scripts"
```

### macOS / Linux

```bash
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

### Перевірка

```bash
poetry --version
# Повинно вивести: Poetry 1.7.X
```

---

## 🚀 Крок 4: Ініціалізація проекту

Файли вже готові:
- ✅ `pyproject.toml` — описує проект та залежності
- ✅ `poetry.lock` — детермінована версія залежностей
- ✅ `.python-version` — указує Python 3.11.9

Просто встановіть залежності:

```bash
cd d:\12314234\trust

# Встановити всі залежності з poetry.lock
poetry install

# Якщо вам потрібна GPU підтримка (CUDA):
# poetry install --extras gpu
```

---

## 📝 Як використовувати Poetry у розробці

### Запуск проекту у віртуальному оточенні Poetry

```bash
# Метод 1: Через poetry run (рекомендовано)
poetry run python start_app.py
poetry run streamlit run app_streamlit.py
poetry run pytest tests/

# Метод 2: Активувати оболонку
poetry shell
python start_app.py
streamlit run app_streamlit.py
exit
```

---

## 📦 Управління залежностями

### Додати нову залежність

```bash
# Додати звичайну залежність
poetry add requests

# Додати залежність для розробки (dev)
poetry add --group dev pytest-xdist

# Додати з конкретною версією
poetry add "numpy>=1.20,<2.0"

# Додати з git репозиторію
poetry add git+https://github.com/user/repo.git
```

### Оновити залежності

```bash
# Оновити всі залежності (з урахуванням constraints)
poetry update

# Оновити конкретну залежність
poetry update requests

# Перегляд оновлень без застосування
poetry update --dry-run
```

### Видалити залежність

```bash
poetry remove requests
poetry remove --group dev pytest
```

### Переглянути установлені пакети

```bash
poetry show
poetry show --outdated  # показати застарілі
poetry show requests     # інфо про конкретний пакет
```

---

## 🔒 Блокування залежностей

### Що таке `poetry.lock`?

- Файл, який фіксує **точні версії** всіх залежностей
- Автоматично генерується Poetry
- Забезпечує **однакове оточення** для всіх розробників

### Коли оновлюється

```bash
poetry update          # Оновить poetry.lock
poetry install         # Встановить те, що в poetry.lock
```

### Зберігання в Git

```bash
git add poetry.lock    # ОБОВ'ЯЗКОВО commitimо
git add pyproject.toml
```

---

## 🐍 Переконаємось що Python правильна

```bash
poetry run python --version
# Повинно вивести: Python 3.11.9

poetry env info
# Показить інформацію про oточення Poetry
```

---

## 🏗️ PyInstaller + Poetry

При збірці виконавчого файлу (`.exe` на Windows):

```bash
# 1. Отримати шлях до Python у оточенні Poetry
$pythonPath = poetry env info --path

# 2. Збудувати з PyInstaller
poetry run pyinstaller --onefile `
  --distpath="$pythonPath/dist" `
  run_app.py

# Результат буде в:
# $pythonPath/dist/run_app.exe
```

---

## 📝 Файл `.python-version`

Цей файл казує pyenv, яку версію Python використовувати:

```
3.11.9
```

Коли ви:
- `cd` в папку проекту → pyenv автоматично активує Python 3.11.9
- `cd` назад → повертається до системної версії

### Як це працює

```bash
# Ви в проекті
cd d:\12314234\trust
python --version  # → Python 3.11.9

# Ви нижче
cd ..
python --version  # → Python X.X.X (система)
```

---

## 🧪 Тестування

```bash
# Запустити тести з Poetry
poetry run pytest tests/

# Запустити з покриттям
poetry run pytest --cov=webapp tests/

# Запустити конкретний тест
poetry run pytest tests/test_audio_cutter.py::TestParseTimestampMarkers
```

---

## 📚 Структура файлів Poetry

```
d:\12314234\trust\
├── pyproject.toml          ← Конфіг проекту (НОВИЙ!)
├── poetry.lock             ← Блокування залежностей (НОВИЙ!)
├── .python-version         ← pyenv конфіг (НОВИЙ!)
├── requirements.txt        ← (ЗАСТАРІЛИЙ - можна видалити)
│
├── .venv/                  ← Віртуальне оточення Poetry
├── webapp/
├── tests/
├── run_app.py
└── ...
```

---

## ⚠️ Частих помилок і рішень

### Помилка 1: "poetry: command not found"

**Рішення:**
```bash
# Додайте Poetry до PATH
# Windows: $env:Path += ";$env:APPDATA\Python\Scripts"
# macOS/Linux: export PATH="$HOME/.local/bin:$PATH"

# Або переінсталюйте Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

### Помилка 2: "Python 3.11.9 not installed"

**Рішення:**
```bash
pyenv install 3.11.9
pyenv versions  # Перевірьте
```

### Помилка 3: "poetry install" не працює

**Рішення:**
```bash
# Очистити кеш
poetry cache clear . --all

# Переінсталювати
rm poetry.lock
poetry install
```

### Помилка 4: ".python-version not being used"

**Рішення:**
```bash
# Перевірьте, що pyenv активований
pyenv versions

# Перевірьте PATH
echo $PATH | grep pyenv

# Перезавантажте оболонку
exec $SHELL
```

---

## 🔄 Міграція з pip на Poetry

### Для існуючого проекту

```bash
# 1. Оновити requirements.txt → pyproject.toml (вже зроблено!)
# 2. Встановити залежності
poetry install

# 3. (опціонально) Видалити старий .venv
rm -rf .venv  # або deltree .venv на Windows

# 4. Перевірити що все працює
poetry run pytest tests/
poetry run python start_app.py
```

### Для розробників, які клонують проект

```bash
# 1. Встановити pyenv (якщо ще не встановлено)
# 2. Встановити Poetry (якщо ще не встановлено)
# 3. Клонувати проект
git clone <repo>
cd d:\12314234\trust

# 4. pyenv автоматично виберіть Python 3.11.9
pyenv versions  # Перевірьте

# 5. Встановити залежності
poetry install

# 6. Всі готово!
poetry run python start_app.py
```

---

## 💡 Корисні команди

```bash
# Показити де находиться віртуальне оточення
poetry env info --path

# Показати Python шлях
poetry run which python  # macOS/Linux
poetry run where python  # Windows

# Запустити довільну команду
poetry run echo "Hello"
poetry run pip list  # Всі встановлені пакети

# Переглянути залежностями дерево
poetry show --tree

# Експортувати requirements.txt (якщо потрібно)
poetry export -f requirements.txt --output requirements.txt
```

---

## 🎯 Checksum для розробника

**Перш ніж почати розробку:**

```bash
✓ Встановити pyenv
✓ Встановити Python 3.11.9
✓ Встановити Poetry
✓ Перейти в папку проекту
✓ Запустити: poetry install
✓ Перевірити: poetry run pytest tests/
✓ Запустити: poetry run python start_app.py
```

**Якщо все ОК - готово!** ✅

---

## 📞 Поддержка

Якщо виникли проблеми:

1. **Перевірьте віртуальне оточення:**
   ```bash
   poetry env info
   ```

2. **Очистіть кеш:**
   ```bash
   poetry cache clear . --all
   ```

3. **Переінсталюйте залежності:**
   ```bash
   rm poetry.lock
   poetry install
   ```

4. **Звернітесь в техпідтримку:**
   - Email: wretchehag@gmail.com
   - Надайте: `poetry --version`, `python --version`, помилку

---

## 📖 Документація

- **Poetry:** https://python-poetry.org/docs/
- **Pyenv:** https://github.com/pyenv/pyenv
- **PEP 518 (pyproject.toml):** https://www.python.org/dev/peps/pep-0518/

---

**Версія:** 2.1.1  
**Дата:** 2026-06-04  
✅ **Готово до використання!**

🎉 **Вітаємо з переходом на професійний стек!**
