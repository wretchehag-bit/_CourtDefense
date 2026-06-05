#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Streamlit UI для Audio Cutter (Evidence Extraction).

Run: streamlit run app_streamlit.py
Opens in browser: http://localhost:8501
"""
import sys
from pathlib import Path

# Add src/ to path for court_defense imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import time
from court_defense.core.audio_cutter import cut_audio_by_timestamps
from court_defense.core.services import _read_text_safe

st.set_page_config(
    page_title="🎵 Нарізка доказів | Court Defense AI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main { max-width: 1200px; }
    .stButton button { width: 100%; }
    .metric {
        background: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        margin: 5px 0;
        border-left: 4px solid #0068C9;
    }
    .success-box {
        background: #d1e7dd;
        border: 1px solid #badbcc;
        padding: 15px;
        border-radius: 8px;
        color: #0f5132;
    }
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c2c7;
        padding: 15px;
        border-radius: 8px;
        color: #842029;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("# ⚖️ Court Defense AI — Нарізка доказів")
st.markdown("""
**Автоматична видобудь критичних фрагментів** з судових записів за часовими мітками.

Система сканує папку справи, знаходить аудіофайли й їх транскрипції,
потім розбиває записи на фрагменти за вказаними маркерами часу.
""")

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR: CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Конфігурація")

    # Case folder
    case_folder = st.text_input(
        "📁 Шлях до папки справи",
        placeholder="C:\\my_cases\\case_123 або /home/user/case_123",
        help="Абсолютний шлях до папки, яка містить аудіо та документи"
    )

    # Toggle for custom phrases file
    st.markdown("---")
    use_custom_file = st.checkbox(
        "📋 Вибрати окремий файл з фразами",
        value=False,
        help="Якщо ввімкнено, можна вибрати файл з будь-якого місця на диску"
    )

    if use_custom_file:
        # Custom phrases file path
        phrases_file = st.text_input(
            "📄 Шлях до файлу з фразами",
            placeholder="C:\\files\\my_phrases.txt або /home/user/phrases.txt",
            help="Повний абсолютний шлях до .txt файлу"
        )
    else:
        # Default phrases file in case folder
        phrases_file = None  # Will be search_phrases.txt in case_folder
        st.info("📄 Буде використовуватись `search_phrases.txt` в папці справи")

    st.markdown("---")
    # API Key (optional)
    api_key = st.text_input(
        "🔑 Anthropic API Key (опціонально)",
        type="password",
        help="Для ШІ-аналітики результатів",
    )

# ─────────────────────────────────────────────────────────────────────────────
# MAIN PANEL
# ─────────────────────────────────────────────────────────────────────────────

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("## 🚀 Запуск нарізки")

    if not case_folder:
        st.warning("⚠️ Будь ласка, вкажіть шлях до папки справи")
    elif not Path(case_folder).exists():
        st.error(f"❌ Папка не знайдена: {case_folder}")
    else:
        # Show folder info
        case_path = Path(case_folder)
        audio_files = list(case_path.rglob("*.mp3")) + list(case_path.rglob("*.wav")) + \
                      list(case_path.rglob("*.m4a")) + list(case_path.rglob("*.flac"))
        doc_files = list(case_path.rglob("*.txt")) + list(case_path.rglob("*.json"))

        st.info(f"""
        ✓ **Папка знайдена**
        - 🎵 Аудіофайлів: {len(audio_files)}
        - 📄 Документів/Транскрипцій: {len(doc_files)}
        """)

        # Determine phrases file
        if use_custom_file:
            if not phrases_file or not phrases_file.strip():
                st.error("❌ Вкажіть шлях до файлу з фразами")
                phrases_path_to_use = None
            else:
                phrases_path_to_use = Path(phrases_file.strip())
                if not phrases_path_to_use.exists():
                    st.error(f"❌ Файл не знайдено: {phrases_file}")
                    phrases_path_to_use = None
        else:
            phrases_path_to_use = case_path / "search_phrases.txt"
            if not phrases_path_to_use.exists():
                st.error(f"❌ Файл `search_phrases.txt` не знайдено в папці справи")
                phrases_path_to_use = None

        # Show file info and run button if file exists
        if phrases_path_to_use:
            phrases_text = _read_text_safe(phrases_path_to_use)
            phrase_count = len([l for l in phrases_text.splitlines() if l.strip() and not l.strip().startswith("#")])
            st.success(f"✓ Файл знайдено ({phrase_count} маркерів часу)")

            # Run button
            if st.button("▶️ Запустити нарізку", type="primary", use_container_width=True):
                with st.spinner("⏳ Обробляю..."):
                    try:
                        result = cut_audio_by_timestamps(case_folder)

                        if result:
                            stats = result.get("stats", {})
                            success = stats.get("success", 0)
                            errors = stats.get("errors", 0)

                            st.markdown(f"""
                            <div class="success-box">
                                ✅ <b>Готово!</b><br>
                                Успішно нарізано: <b>{success}</b> фрагментів<br>
                                {"Помилок: " + str(errors) if errors > 0 else ""}
                            </div>
                            """, unsafe_allow_html=True)

                            # Show results
                            st.markdown("### 📊 Результати")
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                st.metric("Успішних", success)
                            with col_b:
                                st.metric("Помилок", errors)
                            with col_c:
                                st.metric("Разом", success + errors)
                        else:
                            st.error("❌ Помилка обробки. Перевірте лог.")
                    except Exception as e:
                        st.markdown(f"""
                        <div class="error-box">
                            ❌ <b>Помилка:</b><br>
                            {str(e)}
                        </div>
                        """, unsafe_allow_html=True)

with col2:
    st.markdown("## 💡 Довідка")
    st.markdown("""
    ### Формат файлу фраз

    ```
    1 перша мітка
    10:30---10:45

    2 друга мітка
    15:00---15:20
    ```

    або в одному рядку:

    ```
    3 фраза (12:00---12:30)
    ```

    ### Результати

    Нарізані файли зберігаються в:
    ```
    case_folder/
    └── _CourtDefense/
        └── 02_нарізки_за_мітками/
    ```
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ADVANCED OPTIONS
# ─────────────────────────────────────────────────────────────────────────────

with st.expander("🔧 Детальна інформація"):
    st.markdown("### Структура обробки")

    if case_folder and Path(case_folder).exists():
        case_path = Path(case_folder)

        # List audio files
        st.markdown("#### 🎵 Знайдені аудіофайли")
        audio_exts = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"]
        audio_files = []
        for ext in audio_exts:
            audio_files.extend(case_path.rglob(f"*{ext}"))

        if audio_files:
            for af in sorted(audio_files)[:10]:
                size_mb = af.stat().st_size / 1024 / 1024
                st.text(f"📄 {af.name} ({size_mb:.1f} MB)")
            if len(audio_files) > 10:
                st.caption(f"... та ще {len(audio_files) - 10}")
        else:
            st.caption("Аудіофайлів не знайдено")

        # List transcripts
        st.markdown("#### 📋 Знайдені транскрипції")
        transcript_files = list(case_path.rglob("*.json")) + list(case_path.rglob("*.txt"))
        if transcript_files:
            for tf in sorted(transcript_files)[:10]:
                size_kb = tf.stat().st_size / 1024
                st.text(f"📝 {tf.name} ({size_kb:.1f} KB)")
            if len(transcript_files) > 10:
                st.caption(f"... та ще {len(transcript_files) - 10}")
        else:
            st.caption("Транскрипцій не знайдено")

    else:
        st.warning("Виберіть папку справи щоб побачити деталі")

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("""
**Court Defense AI v2.1** | Система автоматизації доказів для адвокатів

🛠️ Розроблено: Court Defense AI Team
📧 Поддержка: wretchehag@gmail.com
⚖️ Лицензия: Закрытая
""")
