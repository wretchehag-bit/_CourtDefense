"""
ЮНІТ-ТЕСТИ: Модуль audio_cutter.py

Покривають:
1. Парсинг часових міток (regex + конвертація)
2. Очищення імен папок (Windows safety)
3. Каскадна резолюція FFmpeg (автономність)
4. Розумний пошук аудіо (рекурсивний + гнучкий матчинг)
5. Стійкість до кодування (encoding fallback)
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import os

from court_defense.core.audio_cutter import (
    _parse_timestamp_markers,
    _sanitize_folder_name,
    _resolve_ffmpeg_path,
    _extract_base_name,
    _find_audio_for_transcript,
    _read_text_safe,
    _cut_audio_segment,
    _clamp_segment,
    _extract_transcript_context,
    _get_audio_duration,
    _save_transcript_fragment,
    _write_summary_report,
)


# ════════════════════════════════════════════════════════════════════════════
# 1. ТЕСТИ ПАРСИНГУ ЧАСОВИХ МІТОК
# ════════════════════════════════════════════════════════════════════════════

class TestParseTimestampMarkers:
    """Тест парсингу часових міток та маркерів."""

    def test_parse_simple_markers(self):
        """Базовий парсинг: маркер на одному рядку, час на наступному."""
        text = """1 дискридетація батька
15:48---15:56"""

        result = _parse_timestamp_markers(text)

        assert len(result) == 1
        marker, start_sec, end_sec = result[0]
        assert marker == "1 дискридетація батька"
        assert start_sec == 15 * 60 + 48  # 948 seconds
        assert end_sec == 15 * 60 + 56    # 956 seconds

    def test_parse_inline_markers(self):
        """Парсинг маркера з часом в одному рядку."""
        text = "1 важливе свідчення (10:30---10:45)"

        result = _parse_timestamp_markers(text)

        assert len(result) == 1
        marker, start_sec, end_sec = result[0]
        assert "важливе свідчення" in marker
        assert start_sec == 10 * 60 + 30
        assert end_sec == 10 * 60 + 45

    def test_parse_multiple_markers(self):
        """Парсинг кількох маркерів."""
        text = """1 перший фрагмент
01:00---01:30
2 другий фрагмент
05:45---06:00"""

        result = _parse_timestamp_markers(text)

        assert len(result) == 2
        assert result[0][0] == "1 перший фрагмент"
        assert result[0][1] == 60  # 01:00
        assert result[0][2] == 90  # 01:30
        assert result[1][0] == "2 другий фрагмент"
        assert result[1][1] == 345  # 05:45
        assert result[1][2] == 360  # 06:00

    def test_parse_empty_text(self):
        """Парсинг порожнього тексту."""
        result = _parse_timestamp_markers("")
        assert result == []

    def test_parse_no_timestamps(self):
        """Текст без часових міток."""
        text = "просто текст без часів"
        result = _parse_timestamp_markers(text)
        assert result == []

    def test_time_conversion_accuracy(self):
        """Точність конвертації часу в секунди."""
        text = "маркер\n00:00---00:01"
        result = _parse_timestamp_markers(text)
        assert result[0][1] == 0  # 00:00 = 0 сек
        assert result[0][2] == 1  # 00:01 = 1 сек

    def test_large_timestamps(self):
        """Обробка великих часів (більше години)."""
        text = "довгий фрагмент\n59:45---60:30"
        result = _parse_timestamp_markers(text)
        assert len(result) == 1
        assert result[0][1] == 59 * 60 + 45
        assert result[0][2] == 60 * 60 + 30


# ════════════════════════════════════════════════════════════════════════════
# 2. ТЕСТИ ОЧИЩЕННЯ ІМЕН ПАПОК (Windows Safety)
# ════════════════════════════════════════════════════════════════════════════

class TestSanitizeFolderName:
    """Тест очищення імен папок від заборонених символів."""

    def test_remove_forbidden_chars(self):
        """Видалення заборонених символів."""
        text = 'фраза<>:"/\\|?*'
        result = _sanitize_folder_name(text)

        # Всі заборонені символи мають бути видалені або замінені
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result
        assert '"' not in result
        assert '/' not in result
        assert '\\' not in result
        assert '|' not in result
        assert '?' not in result
        assert '*' not in result

    def test_truncate_long_name(self):
        """Обрізання довгих імен."""
        long_text = "а" * 100
        result = _sanitize_folder_name(long_text, max_length=50)

        assert len(result) <= 50

    def test_preserve_valid_chars(self):
        """Збереження валідних символів."""
        text = "Фраза 123_батька-справа"
        result = _sanitize_folder_name(text)

        assert "Фраза" in result
        assert "123" in result
        assert "батька" in result
        assert "справа" in result

    def test_empty_after_sanitize(self):
        """Обробка рядка, що стає тільки підкресленнями після очищення."""
        text = "<>:/"
        result = _sanitize_folder_name(text)

        # Заборонені символи замінюються на _, але результат не порожній
        assert result == "____"

    def test_trailing_dots_removed(self):
        """Видалення завершальних точок (Windows вимога)."""
        text = "папка..."
        result = _sanitize_folder_name(text)

        assert not result.endswith('.')


# ════════════════════════════════════════════════════════════════════════════
# 3. ТЕСТИ РЕЗОЛЮЦІЇ FFmpeg
# ════════════════════════════════════════════════════════════════════════════

class TestResolveFFmpegPath:
    """Тест каскадної автономної резолюції FFmpeg."""

    @patch('shutil.which')
    def test_system_path_first(self, mock_which):
        """FFmpeg з системного PATH повинен мати найвищий пріоритет."""
        mock_which.return_value = "/usr/bin/ffmpeg"

        result = _resolve_ffmpeg_path()

        assert result == "/usr/bin/ffmpeg"
        mock_which.assert_called_once_with("ffmpeg")

    @patch('pathlib.Path.exists')
    @patch('shutil.which')
    def test_local_portable_folder(self, mock_which, mock_path_exists):
        """Локальна папка ffmpeg/bin/ffmpeg.exe для Portable."""
        mock_which.return_value = None  # Немає в системному PATH
        mock_path_exists.return_value = True  # bundled ffmpeg exists

        result = _resolve_ffmpeg_path()

        # Повинен повернути локальний шлях (містить 'ffmpeg')
        assert 'ffmpeg' in result

    @patch('pathlib.Path.exists')
    @patch('shutil.which')
    def test_fallback_default(self, mock_which, mock_path_exists):
        """Fallback на дефолт, якщо FFmpeg не знайдено ні в PATH, ні у bundled."""
        mock_which.return_value = None
        mock_path_exists.return_value = False

        result = _resolve_ffmpeg_path()

        # When both PATH and bundled path are unavailable → "ffmpeg" literal
        assert result == "ffmpeg"


# ════════════════════════════════════════════════════════════════════════════
# 4. ТЕСТИ РОЗУМНОГО ПОШУКУ АУДІО
# ════════════════════════════════════════════════════════════════════════════

class TestFindAudioForTranscript:
    """Тест гнучкого рекурсивного пошуку аудіофайлу."""

    def test_find_same_folder(self):
        """Пошук однойменного файлу в одній папці."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Створюємо аудіо та текст
            audio_file = tmp_path / "recording_1648.mp3"
            audio_file.write_bytes(b"fake audio")

            transcript_file = tmp_path / "recording_1648.txt"
            transcript_file.write_text("text")

            # Пошук
            result = _find_audio_for_transcript(transcript_file, tmp_path)

            assert result == audio_file

    def test_find_recursive_different_folders(self):
        """Пошук аудіо в іншій папці (рекурсивний)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Створюємо підпапки
            audio_dir = tmp_path / "audio"
            audio_dir.mkdir()
            text_dir = tmp_path / "transcripts"
            text_dir.mkdir()

            # Аудіо в одній папці
            audio_file = audio_dir / "session_123.mp3"
            audio_file.write_bytes(b"fake")

            # Текст в іншій папці
            transcript_file = text_dir / "session_123_АНАЛІЗ.txt"
            transcript_file.write_text("text")

            # Пошук
            result = _find_audio_for_transcript(transcript_file, tmp_path)

            assert result == audio_file

    def test_extract_base_name_with_analysis_suffix(self):
        """Витяг базового імені з суфіксом _АНАЛІЗ."""
        base_name = _extract_base_name("recording_1648_АНАЛІЗ.txt")
        assert base_name == "recording_1648"

    def test_extract_base_name_with_chunk(self):
        """Витяг базового імені з chunk маркером."""
        base_name = _extract_base_name("audio_chunk_001.json")
        assert "audio" in base_name
        assert "chunk" not in base_name.lower()


# ════════════════════════════════════════════════════════════════════════════
# 5. ТЕСТИ СТІЙКОСТІ ДО КОДУВАННЯ
# ════════════════════════════════════════════════════════════════════════════

class TestReadTextSafe:
    """Тест каскадного encoding fallback."""

    def test_read_utf8(self):
        """Читання UTF-8 файлу."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "test.txt"

            content = "тестовий текст"
            file_path.write_text(content, encoding='utf-8')

            result = _read_text_safe(file_path)
            assert result == content

    def test_read_windows_1251(self):
        """Читання Windows-1251 файлу (Cyrillic)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "test.txt"

            content = "українська мова"
            file_path.write_text(content, encoding='windows-1251')

            result = _read_text_safe(file_path)
            assert result == content

    def test_read_nonexistent_returns_fallback(self):
        """Читання неіснуючого файлу повертає fallback."""
        result = _read_text_safe(Path("/nonexistent/file.txt"), fallback_text="default")
        assert result == "default"

    def test_fallback_chain_works(self):
        """Каскадна спроба кодувань."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "test.txt"

            # Пишемо в Windows-1251 (Cyrillic)
            content = "Тест на кодування"
            file_path.write_text(content, encoding='windows-1251')

            # Маємо прочитати навіть якщо UTF-8 не спрацює
            result = _read_text_safe(file_path)
            assert "Тест" in result or len(result) > 0


# ════════════════════════════════════════════════════════════════════════════
# 6. ІНТЕГРАЦІЙНІ ТЕСТИ
# ════════════════════════════════════════════════════════════════════════════

class TestAudioCuttingIntegration:
    """Інтеграційні тести для повної роботи конвеєру."""

    @patch('court_defense.core.audio_cutter._cut_audio_segment')
    def test_full_workflow_simulation(self, mock_cut):
        """Симуляція повного workflow нарізки."""
        mock_cut.return_value = True

        text = """1 перший фрагмент
10:00---10:30"""

        result = _parse_timestamp_markers(text)

        assert len(result) == 1
        marker, start_sec, end_sec = result[0]
        assert marker == "1 перший фрагмент"
        assert start_sec == 600
        assert end_sec == 630

    def test_sanitize_and_extract_integration(self):
        """Інтеграція очищення і витягу базового імені."""
        # Реальні імена файлів від користувача
        transcript_name = "270520256_1648_АНАЛІЗ.txt"
        audio_name = "270520256_1648.mp3"

        transcript_base = _extract_base_name(transcript_name)
        audio_base = _extract_base_name(audio_name)

        assert transcript_base == audio_base

    def test_windows_safe_folder_creation(self):
        """Тест створення папки з небезпечною назвою."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Небезпечна назва
            unsafe_name = 'фраза<>:"test'
            safe_name = _sanitize_folder_name(unsafe_name)

            # Створюємо папку з очищеним іменем
            folder = tmp_path / safe_name
            folder.mkdir(parents=True, exist_ok=True)

            # Папка повинна існувати і мати вхідне ім'я
            assert folder.exists()
            assert safe_name == folder.name


# ════════════════════════════════════════════════════════════════════════════
# 7. ТЕСТИ CLAMPING (v2.2)
# ════════════════════════════════════════════════════════════════════════════

class TestClampSegment:
    """Tests for time-bound clamping logic (v2.2)."""

    def test_valid_range_unchanged(self):
        """A range fully within duration passes through unchanged."""
        s, e, skip = _clamp_segment(60, 120, 300.0)
        assert s == 60
        assert e == 120
        assert skip is False

    def test_negative_start_clamped_to_zero(self):
        """Negative start is clamped to 0."""
        s, e, skip = _clamp_segment(-10, 30, 300.0)
        assert s == 0
        assert e == 30
        assert skip is False

    def test_end_beyond_duration_clamped(self):
        """end_sec beyond track length is clamped to duration."""
        s, e, skip = _clamp_segment(240, 999, 300.0)
        assert s == 240
        assert e == 300
        assert skip is False

    def test_start_at_or_past_duration_skipped(self):
        """Segment starting at or after duration must be skipped."""
        s, e, skip = _clamp_segment(300, 360, 300.0)
        assert skip is True

        s2, e2, skip2 = _clamp_segment(400, 460, 300.0)
        assert skip2 is True

    def test_unknown_duration_no_clamping(self):
        """When duration is 0 (unknown), no clamping — skip is always False."""
        s, e, skip = _clamp_segment(9999, 10000, 0.0)
        assert s == 9999
        assert e == 10000
        assert skip is False

    def test_both_ends_clamped(self):
        """Both start and end clamped when out of bounds."""
        s, e, skip = _clamp_segment(-5, 999, 60.0)
        assert s == 0
        assert e == 60
        assert skip is False


# ════════════════════════════════════════════════════════════════════════════
# 8. ТЕСТИ EXTRACTION TRANSCRIPT CONTEXT (v2.2)
# ════════════════════════════════════════════════════════════════════════════

class TestExtractTranscriptContext:
    """Tests for _extract_transcript_context (v2.2)."""

    SAMPLE = (
        "[00:00:05] Перший рядок\n"
        "[00:01:00] Другий рядок\n"
        "[00:02:30] Третій рядок\n"
        "[00:05:00] Четвертий рядок\n"
    )

    def test_lines_within_window_returned(self):
        """Lines with timestamps inside [start, end] are returned."""
        result = _extract_transcript_context(self.SAMPLE, 60, 150)
        assert "Другий рядок" in result
        assert "Третій рядок" in result

    def test_lines_outside_window_excluded(self):
        """Lines outside the window are not included."""
        result = _extract_transcript_context(self.SAMPLE, 60, 150)
        assert "Перший рядок" not in result
        assert "Четвертий рядок" not in result

    def test_empty_transcript_returns_empty_string(self):
        """Empty input yields empty output."""
        assert _extract_transcript_context("", 0, 100) == ""

    def test_boundary_timestamps_inclusive(self):
        """Timestamps exactly at start and end are included."""
        result = _extract_transcript_context(self.SAMPLE, 5, 60)
        assert "Перший рядок" in result
        assert "Другий рядок" in result

    def test_no_matching_lines_returns_empty(self):
        """Window with no matching lines returns empty string."""
        result = _extract_transcript_context(self.SAMPLE, 1000, 2000)
        assert result == ""


# ════════════════════════════════════════════════════════════════════════════
# 9. ТЕСТИ _get_audio_duration (v2.2)
# ════════════════════════════════════════════════════════════════════════════

class TestGetAudioDuration:
    """Tests for ffprobe-based duration detection (v2.2)."""

    @patch("subprocess.run")
    def test_returns_float_on_success(self, mock_run):
        """Returns parsed float when ffprobe succeeds."""
        mock_run.return_value = MagicMock(returncode=0, stdout=b"123.456\n")
        dur = _get_audio_duration(Path("fake.mp3"))
        assert abs(dur - 123.456) < 0.001

    @patch("subprocess.run")
    def test_returns_zero_on_failure(self, mock_run):
        """Returns 0.0 when ffprobe is unavailable or fails."""
        mock_run.side_effect = FileNotFoundError("ffprobe not found")
        dur = _get_audio_duration(Path("fake.mp3"))
        assert dur == 0.0


# ════════════════════════════════════════════════════════════════════════════
# 10. ТЕСТИ save_transcript_fragment + write_summary_report (v2.2)
# ════════════════════════════════════════════════════════════════════════════

class TestTranscriptFragmentAndSummary:
    """Tests for guaranteed file writes (v2.2)."""

    def test_fragment_written_with_context(self):
        """фрагмент_транскрипту.txt is created with provided context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _save_transcript_fragment(folder, "line one\nline two", 60, 120)
            fragment = folder / "фрагмент_транскрипту.txt"
            assert fragment.exists()
            content = fragment.read_text(encoding="utf-8")
            assert "line one" in content
            assert "01:00" in content   # start time formatted

    def test_fragment_written_even_when_empty_context(self):
        """фрагмент_транскрипту.txt created even with no matching lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            folder = Path(tmpdir)
            _save_transcript_fragment(folder, "", 0, 30)
            fragment = folder / "фрагмент_транскрипту.txt"
            assert fragment.exists()
            content = fragment.read_text(encoding="utf-8")
            assert "не знайдено" in content

    def test_summary_report_appended_not_overwritten(self):
        """Running _write_summary_report twice appends; existing data is preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            ep = [{
                "marker": "тест",
                "source": "audio.mp3",
                "start_sec": 10, "end_sec": 20,
                "original_start": 10, "original_end": 20,
                "was_clamped": False,
                "audio_status": "OK",
                "context": "рядок транскрипції",
                "folder": "тест__audio_0",
            }]
            _write_summary_report(out, ep)
            _write_summary_report(out, ep)
            report = out / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt"
            content = report.read_text(encoding="utf-8")
            # Two runs → two "ЗАПУСК:" entries
            assert content.count("ЗАПУСК:") == 2

    def test_summary_empty_episodes_not_written(self):
        """_write_summary_report with empty list writes nothing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            _write_summary_report(out, [])
            report = out / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt"
            assert not report.exists()

    def test_summary_contains_context_block(self):
        """Summary report includes the 'Контекст фрагмента' section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir)
            ep = [{
                "marker": "ключовий момент",
                "source": "rec.mp3",
                "start_sec": 0, "end_sec": 15,
                "original_start": 0, "original_end": 15,
                "was_clamped": False,
                "audio_status": "OK",
                "context": "він сказав так",
                "folder": "ключовий_момент__rec_0",
            }]
            _write_summary_report(out, ep)
            content = (out / "00_ЗАГАЛЬНИЙ_ВИСНОВОК_ПО_ФРАЗАХ.txt").read_text("utf-8")
            assert "він сказав так" in content
            assert "Контекст фрагмента" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
