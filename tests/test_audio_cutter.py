"""
Unit-тесты для модуля автоматичної нарізки аудіо по ключовим фразам.
Перевіряє: чекпоінти, ідемпотентність, припинення на готовому.
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp.audio_cutter import (
    _read_search_phrases,
    _find_transcription_files,
    _search_phrase_in_text,
    _format_timestamp,
    _create_output_folder_name,
    _checkpoint_exists,
    cut_audio_by_phrases,
    _generate_summary_report,
)


# ── Тестові фікстури ───────────────────────────────────────────────────────

@pytest.fixture
def temp_case_folder():
    """Створює тимчасову папку структури справи."""
    with tempfile.TemporaryDirectory() as tmpdir:
        case_path = Path(tmpdir) / "test_case"
        case_path.mkdir()
        yield case_path


@pytest.fixture
def search_phrases_file(temp_case_folder):
    """Створює файл зі списком фраз."""
    phrases_file = temp_case_folder / "search_phrases.txt"
    phrases_file.write_text(
        "ключова фраза\n"
        "важлива промова\n"
        "# коментар - ігнорується\n"
        "\n"  # пуста лінія - ігнорується
        "третя фраза\n",
        encoding="utf-8"
    )
    return phrases_file


@pytest.fixture
def sample_whisper_json(temp_case_folder):
    """Створює тестовий JSON файл від Whisper з фіктивним аудіофайлом."""
    audio_folder = temp_case_folder / "audio_files"
    audio_folder.mkdir()

    # Створюємо фіктивний аудіофайл (пусто, лише для існування)
    audio_file = audio_folder / "recording.mp3"
    audio_file.write_bytes(b"fake audio data")

    whisper_file = audio_folder / "recording.json"
    whisper_data = {
        "text": (
            "[00:00:15] Судья: Добрый день, открываем заседание.\n"
            "[00:00:30] Адвокат: Здравствуйте, уважаемые коллеги.\n"
            "[00:01:00] Прокурор: Это ключова фраза по делу номер 123.\n"
            "[00:02:00] Адвокат: Согласен, это важлива промова на весь процесс.\n"
            "[00:03:00] Судья: Спасибо, третя фраза зафиксирована в протоколе.\n"
        ),
        "segments": []
    }
    whisper_file.write_text(json.dumps(whisper_data), encoding="utf-8")
    return whisper_file


@pytest.fixture
def sample_txt_transcription(temp_case_folder):
    """Створює тестовий TXT файл транскрипції з фіктивним аудіофайлом."""
    audio_folder = temp_case_folder / "audio_files"
    audio_folder.mkdir(exist_ok=True)

    # Створюємо фіктивний аудіофайл
    audio_file = audio_folder / "second_recording.wav"
    audio_file.write_bytes(b"fake audio data")

    txt_file = audio_folder / "second_recording.txt"
    txt_file.write_text(
        "[00:10:15] Судья: Продолжаем заседание.\n"
        "[00:10:30] Свидетель: Я видел ключова фраза происходящего.\n"
        "[00:11:00] Адвокат: Это также важлива промова для защиты.\n",
        encoding="utf-8"
    )
    return txt_file


# ── Тести для читання фраз ─────────────────────────────────────────────────

def test_read_search_phrases_valid(search_phrases_file):
    """Тест: читання валідного списку фраз."""
    phrases = _read_search_phrases(search_phrases_file)

    assert len(phrases) == 3
    assert "ключова фраза" in phrases
    assert "важлива промова" in phrases
    assert "третя фраза" in phrases
    # Коментарі та пусті лінії не повинні бути включені
    assert len(phrases) == 3


def test_read_search_phrases_empty_file(temp_case_folder):
    """Тест: читання пустого файлу."""
    empty_file = temp_case_folder / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    phrases = _read_search_phrases(empty_file)
    assert len(phrases) == 0


def test_read_search_phrases_nonexistent():
    """Тест: файл не існує."""
    nonexistent = Path("/nonexistent/path/search_phrases.txt")
    phrases = _read_search_phrases(nonexistent)
    assert len(phrases) == 0


# ── Тести для пошуку файлів ────────────────────────────────────────────────

def test_find_transcription_files(sample_whisper_json, sample_txt_transcription):
    """Тест: пошук файлів транскрипції."""
    case_path = sample_whisper_json.parent.parent

    files = _find_transcription_files(case_path)

    assert len(files) == 2
    assert sample_whisper_json in files
    assert files[sample_whisper_json] == "json"
    assert sample_txt_transcription in files
    assert files[sample_txt_transcription] == "txt"


def test_find_transcription_files_none_found(temp_case_folder):
    """Тест: жоден файл не знайдено."""
    files = _find_transcription_files(temp_case_folder)
    assert len(files) == 0


# ── Тести для пошуку фраз ──────────────────────────────────────────────────

def test_search_phrase_in_text_single_match():
    """Тест: пошук однієї фрази в тексті."""
    text = (
        "[00:00:10] Судья: Добрый день.\n"
        "[00:00:20] Адвокат: Это ключова фраза для дела.\n"
        "[00:00:30] Судья: Спасибо.\n"
    )

    matches = _search_phrase_in_text(text, "ключова фраза", context_seconds=10)

    assert len(matches) == 1
    start_sec, context = matches[0]
    assert start_sec == 20  # [00:00:20]
    assert "ключова фраза" in context


def test_search_phrase_in_text_case_insensitive():
    """Тест: пошук не чутливий до регістру."""
    text = "[00:00:10] Адвокат: КЛЮЧОВА ФРАЗА тут.\n"

    matches = _search_phrase_in_text(text, "ключова фраза")

    assert len(matches) == 1


def test_search_phrase_in_text_no_match():
    """Тест: фраза не знайдена."""
    text = "[00:00:10] Судья: Добрый день.\n"

    matches = _search_phrase_in_text(text, "несуществующая фраза")

    assert len(matches) == 0


def test_search_phrase_in_text_multiple_matches():
    """Тест: множеством відповідностей однієї фрази."""
    text = (
        "[00:00:10] Адвокат: ключова фраза раз.\n"
        "[00:01:00] Судья: ключова фраза два раза.\n"
        "[00:02:00] Прокурор: ключова фраза три раза.\n"
    )

    matches = _search_phrase_in_text(text, "ключова фраза")

    assert len(matches) == 3
    assert matches[0][0] == 10  # [00:00:10]
    assert matches[1][0] == 60  # [00:01:00]
    assert matches[2][0] == 120  # [00:02:00]


# ── Тести для форматування часу ────────────────────────────────────────────

def test_format_timestamp_zero():
    """Тест: форматування 0 секунд."""
    assert _format_timestamp(0) == "0:00"


def test_format_timestamp_seconds_only():
    """Тест: форматування тільки секунди."""
    assert _format_timestamp(45) == "0:45"


def test_format_timestamp_minutes_and_seconds():
    """Тест: форматування хвилин і секунд."""
    assert _format_timestamp(125) == "2:05"


def test_format_timestamp_large():
    """Тест: форматування великого часу."""
    assert _format_timestamp(3665) == "61:05"  # 1 год 1 хв 5 сек


# ── Тести для імен папок ────────────────────────────────────────────────────

def test_create_output_folder_name():
    """Тест: створення імені папки виходу."""
    name = _create_output_folder_name("ключова фраза", "recording.wav", 120)

    assert "ключова_фраза" in name
    assert "recording" in name
    assert "min_2-00" in name  # Windows-compatible: colon replaced with dash


def test_create_output_folder_name_sanitizes_special_chars():
    """Тест: очистка спеціальних символів."""
    name = _create_output_folder_name('Фраза: "важна"!', "test.mp3", 60)

    # Не повинно мати забороненої символи
    assert not any(c in name for c in '<>:"/\\|?*')
    assert "min_1-00" in name  # Colon replaced with dash for Windows


# ── Тести для чекпоінтів ────────────────────────────────────────────────────

def test_checkpoint_exists_true(temp_case_folder):
    """Тест: чекпоінт існує (обидва файли)."""
    output_folder = temp_case_folder / "output_folder"
    output_folder.mkdir()

    # Створюємо обидва необхідних файли
    (output_folder / "нарізка.mp3").write_bytes(b"fake audio data")
    (output_folder / "фрагмент_транскрипту.txt").write_text("test", encoding="utf-8")

    assert _checkpoint_exists(output_folder) is True


def test_checkpoint_exists_missing_audio(temp_case_folder):
    """Тест: чекпоінт НЕ існує (відсутня аудіо)."""
    output_folder = temp_case_folder / "output_folder"
    output_folder.mkdir()

    # Тільки текст, без аудіо
    (output_folder / "фрагмент_транскрипту.txt").write_text("test", encoding="utf-8")

    assert _checkpoint_exists(output_folder) is False


def test_checkpoint_exists_missing_text(temp_case_folder):
    """Тест: чекпоінт НЕ існує (відсутня текст)."""
    output_folder = temp_case_folder / "output_folder"
    output_folder.mkdir()

    # Тільки аудіо, без тексту
    (output_folder / "нарізка.wav").write_bytes(b"fake audio")

    assert _checkpoint_exists(output_folder) is False


def test_checkpoint_not_exists_folder_missing(temp_case_folder):
    """Тест: чекпоінт НЕ існує (папка не створена)."""
    output_folder = temp_case_folder / "nonexistent_folder"

    assert _checkpoint_exists(output_folder) is False


# ── Інтеграційні тести ──────────────────────────────────────────────────────

@patch('webapp.audio_cutter._cut_audio_segment')
def test_cut_audio_by_phrases_processes_new_matches(
    mock_cut,
    temp_case_folder,
    search_phrases_file,
    sample_whisper_json
):
    """Тест: нові совпадения обробляються."""
    mock_cut.return_value = None

    result = cut_audio_by_phrases(
        case_folder=str(temp_case_folder),
        search_phrases_file=str(search_phrases_file)
    )

    # Повинні знайти 3 совпадения (одна за фразу)
    assert len(result["matches"]) == 3
    assert result["processed"] == 3
    assert result["skipped"] == 0


@patch('webapp.audio_cutter._cut_audio_segment')
def test_cut_audio_by_phrases_skips_existing_checkpoint(
    mock_cut,
    temp_case_folder,
    search_phrases_file,
    sample_whisper_json
):
    """КРИТИЧНИЙ ТЕСТ: чекпоінти пропускають вже оброблене."""
    mock_cut.return_value = None

    # Перший запуск - все обробляється
    result1 = cut_audio_by_phrases(
        case_folder=str(temp_case_folder),
        search_phrases_file=str(search_phrases_file)
    )
    assert result1["processed"] == 3
    assert result1["skipped"] == 0

    # Перевіряємо, що папки існують
    cuts_folder = temp_case_folder / "_CourtDefense" / "02_нарізки_за_фразами"
    assert cuts_folder.exists()
    created_folders = list(cuts_folder.glob("*"))
    assert len(created_folders) == 3

    # КЛЮЧОВИЙ ТЕСТ: вручну створюємо файли в папках, щоб чекпоінт вони насправді існували
    for folder in created_folders:
        # Створюємо фіктивну аудіо нарізку
        (folder / "нарізка.mp3").write_bytes(b"fake audio")
        # Створюємо текстовий фрагмент
        (folder / "фрагмент_транскрипту.txt").write_text("тестовий фрагмент", encoding="utf-8")

    # Другий запуск - все повинно бути пропущено
    print("\n[Тест] Другий запуск з чекпоінтами...")
    result2 = cut_audio_by_phrases(
        case_folder=str(temp_case_folder),
        search_phrases_file=str(search_phrases_file)
    )

    print(f"[Тест] Перший запуск: {result1['processed']} обробок")
    print(f"[Тест] Другий запуск: {result2['processed']} обробок (очікується 0)")
    print(f"[Тест] Другий запуск: {result2['skipped']} пропусків (очікується 3)")

    assert result2["processed"] == 0, "Не повинно обробляти вже готове!"
    assert result2["skipped"] == 3, "Повинно пропустити всі готові файли!"


@patch('webapp.audio_cutter._cut_audio_segment')
def test_cut_audio_by_phrases_idempotent(
    mock_cut,
    temp_case_folder,
    search_phrases_file,
    sample_whisper_json
):
    """Тест: ідемпотентність - повторні запуски дають однаковий результат."""
    mock_cut.return_value = None

    # Перший запуск
    result1 = cut_audio_by_phrases(
        case_folder=str(temp_case_folder),
        search_phrases_file=str(search_phrases_file)
    )
    assert result1["processed"] == 3
    assert result1["skipped"] == 0
    print(f"[Запуск 1] обробок={result1['processed']}, пропущено={result1['skipped']}")

    # Вручну "завершуємо" файли, щоб чекпоінти працювали
    cuts_folder = temp_case_folder / "_CourtDefense" / "02_нарізки_за_фразами"
    for folder in cuts_folder.glob("*"):
        (folder / "нарізка.mp3").write_bytes(b"fake")
        (folder / "фрагмент_транскрипту.txt").write_text("тест", encoding="utf-8")

    # Другий запуск - повинен пропустити все
    result2 = cut_audio_by_phrases(
        case_folder=str(temp_case_folder),
        search_phrases_file=str(search_phrases_file)
    )
    assert result2["processed"] == 0, "Другий запуск повинен пропустити все"
    assert result2["skipped"] == 3, "Повинен пропустити 3"
    print(f"[Запуск 2] обробок={result2['processed']}, пропущено={result2['skipped']}")

    # Третій запуск - також повинен пропустити
    result3 = cut_audio_by_phrases(
        case_folder=str(temp_case_folder),
        search_phrases_file=str(search_phrases_file)
    )
    assert result3["processed"] == 0, "Третій запуск повинен пропустити все"
    assert result3["skipped"] == 3, "Повинен пропустити 3"
    print(f"[Запуск 3] обробок={result3['processed']}, пропущено={result3['skipped']}")


@patch('webapp.audio_cutter._cut_audio_segment')
def test_summary_report_generated(
    mock_cut,
    temp_case_folder,
    search_phrases_file,
    sample_whisper_json
):
    """Тест: загальний висновок генерується при кожному запуску."""
    mock_cut.return_value = None

    # Перший запуск
    cut_audio_by_phrases(
        case_folder=str(temp_case_folder),
        search_phrases_file=str(search_phrases_file)
    )

    # Отчет находится в папке _CourtDefense
    report_file = temp_case_folder / "_CourtDefense" / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt"
    assert report_file.exists(), "Звіт повинен бути створений"

    content = report_file.read_text(encoding="utf-8")
    assert "ЗАГАЛЬНИЙ ВИСНОВОК" in content
    assert "ключова фраза" in content
    assert "важлива промова" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
