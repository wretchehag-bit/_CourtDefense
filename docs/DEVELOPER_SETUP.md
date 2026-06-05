# 👨‍💻 Настройка середовища розробника | Developer Setup

**Для розробників, які клонують цей проект**

---

## ⚡ Швидкий старт (5 хвилин)

### 1. Встановити інструменти (якщо ще не встановлені)

```bash
# Windows: Інсталювати з Chocolatey або вручну
choco install pyenv-win poetry

# macOS: Інсталювати через Homebrew
brew install pyenv poetry

# Linux: Встановити скрипти
curl https://pyenv.run | bash
curl -sSL https://install.python-poetry.org | python3 -
```

### 2. Клонувати проект

```bash
git clone <repo-url>
cd d:\12314234\trust
```

### 3. Встановити Python та залежності

```bash
# pyenv автоматично виберіть Python 3.11.9 (з .python-version)
pyenv versions

# Встановити залежності
poetry install

# Перевірити що все працює
poetry run pytest tests/
```

### 4. Запустити проект

```bash
# Веб-інтерфейс
poetry run python start_app.py
# http://localhost:8000

# Або Streamlit
poetry run streamlit run app_streamlit.py
# http://localhost:8501
```

**✅ Готово! Розробка може починатись!**

---

## 📚 Детальна настройка

### Крок 1: Pyenv

#### Windows

**Через Chocolatey (рекомендовано):**
```powershell
choco install pyenv-win
```

**Або вручну:**
1. Завантажити: https://github.com/pyenv-win/pyenv-win/releases
2. Розпакувати в: `C:\Users\<username>\.pyenv`
3. Додати до PATH:
   - Система → Променні оточення → PATH
   - Додати: `C:\Users\<username>\.pyenv\bin`
   - Додати: `C:\Users\<username>\.pyenv\shims`
4. Перезавантажити терміналь

#### macOS

```bash
# Homebrew
brew install pyenv

# Додати до ~/.zshrc або ~/.bash_profile
export PYENV_ROOT="$HOME/.pyenv"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
```

#### Linux (Ubuntu/Debian)

```bash
# Встановити залежності
sudo apt-get install -y make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev

# Встановити pyenv
curl https://pyenv.run | bash

# Додати до ~/.bashrc
export PYENV_ROOT="$HOME/.pyenv"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
```

### Крок 2: Python 3.11.9

```bash
# Встановити
pyenv install 3.11.9

# Перевірити
pyenv versions
# Повинно показати:
#   3.11.9 (set by /path/to/.python-version)
# * system
```

### Крок 3: Poetry

#### Windows

```powershell
# PowerShell (Administrator)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Додати до PATH
$env:Path += ";$env:APPDATA\Python\Scripts"

# Перевірити
poetry --version
```

#### macOS / Linux

```bash
# Встановити
curl -sSL https://install.python-poetry.org | python3 -

# Додати до шляху
export PATH="$HOME/.local/bin:$PATH"

# Додати до ~/.bashrc або ~/.zshrc для постійного ефекту

# Перевірити
poetry --version
```

### Крок 4: Проект

```bash
# Перейти в проект
cd d:\12314234\trust

# Встановити залежності
poetry install

# ГОТОВО! ✅
```

---

## 🚀 Повсякденна розробка

### Запуск проекту

**Варіант 1: Через `poetry run` (рекомендовано)**
```bash
# Веб-інтерфейс
poetry run python start_app.py

# Streamlit
poetry run streamlit run app_streamlit.py

# Тести
poetry run pytest tests/

# Інші команди
poetry run flake8 webapp/
poetry run black --check webapp/
```

**Варіант 2: Активувати оболонку**
```bash
# Активувати віртуальне оточення
poetry shell

# Тепер можна запускати без poetry run
python start_app.py
pytest tests/

# Вийти
exit
```

### Додавання залежностей

```bash
# Додати звичайну залежність
poetry add requests

# Додати для розробки
poetry add --group dev black

# Додати з конкретною версією
poetry add "numpy>=1.20,<2.0"

# Оновити poetry.lock (для GIT)
git add poetry.lock
git commit -m "Add new dependency: requests"
```

### Оновлення залежностей

```bash
# Оновити всі (з урахуванням обмежень)
poetry update

# Оновити конкретну
poetry update requests

# Перегляд оновлень
poetry show --outdated
```

### Тестування

```bash
# Всі тести
poetry run pytest tests/

# Конкретний файл
poetry run pytest tests/test_audio_cutter.py

# З покриттям
poetry run pytest --cov=webapp tests/

# Конкретний тест
poetry run pytest tests/test_audio_cutter.py::TestParseTimestampMarkers::test_parse_simple_markers
```

### Код-стиль

```bash
# Форматування
poetry run black webapp/ tests/

# Перевірка стилю
poetry run flake8 webapp/

# Type checking
poetry run mypy webapp/
```

---

## 🔍 Корисні команди

```bash
# Показити інформацію про оточення
poetry env info

# Показити шлях до Python
poetry run which python    # macOS/Linux
poetry run where python    # Windows

# Список встановлених пакетів
poetry show
poetry show --tree    # з залежностями

# Пошук пакета в PyPI
poetry search requests

# Експортувати requirements.txt
poetry export -f requirements.txt --output requirements.txt

# Видалити оточення (для чистки)
poetry env remove <name>
```

---

## ⚠️ Розв'язання проблем

### Проблема 1: Python 3.11.9 не знайдено

```bash
# Установить
pyenv install 3.11.9

# Перевірити
pyenv versions
```

### Проблема 2: Poetry команда не знайдена

```bash
# Windows: Додайте до PATH
$env:Path += ";$env:APPDATA\Python\Scripts"

# macOS/Linux: Додайте до ~/.bashrc або ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Переоткрити терміналь
```

### Проблема 3: `poetry install` не працює

```bash
# Очистити кеш
poetry cache clear . --all

# Переінсталювати
rm poetry.lock
poetry install
```

### Проблема 4: Python версія не коректна

```bash
# Перевірити поточну версію
python --version

# Перевірити що pyenv активований
pyenv versions

# Перевірити що .python-version існує
cat .python-version  # Має бути: 3.11.9

# Якщо не працює, перезавантажте оболонку
exec $SHELL
```

### Проблема 5: Оточення не активується

```bash
# Видалити оточення
poetry env remove <env-name>

# Переінсталювати
poetry install
```

---

## 🎯 До / Після

### РАНІШЕ (pip)

```bash
# Вручну встановлювати Python
# Вручну створювати venv
python -m venv venv
source venv/bin/activate  # або: venv\Scripts\activate

# Встановлювати залежності
pip install -r requirements.txt

# Оновлювати
pip install --upgrade pytest
```

### ТЕПЕР (Poetry)

```bash
# Python автоматично через pyenv
# Оточення автоматично через Poetry

# Встановлювати залежності
poetry install

# Оновлювати
poetry update pytest

# Додавати нові
poetry add requests
```

---

## 📋 Чек-лист для нових розробників

- [ ] Встановити pyenv
- [ ] Встановити Python 3.11.9 (`pyenv install 3.11.9`)
- [ ] Встановити Poetry
- [ ] Клонувати проект
- [ ] `cd d:\12314234\trust`
- [ ] Перевірити версію Python (`python --version` → 3.11.9)
- [ ] `poetry install`
- [ ] `poetry run pytest tests/` (повинно бути 41 passing)
- [ ] `poetry run python start_app.py` (відкрити http://localhost:8000)
- [ ] Розпочати розробку! 🚀

---

## 📞 Допомога

- **Документація Poetry:** https://python-poetry.org/docs/
- **Pyenv GitHub:** https://github.com/pyenv/pyenv
- **Проблеми:** wretchehag@gmail.com

---

**Версія:** 2.1.1  
✅ **Готово до розробки!**

Успіхів у розробці! 🚀
