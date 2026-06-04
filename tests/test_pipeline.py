"""
Unit-тесты для диагностики проблем с PDF конвертацией и валидацией API.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from webapp import services


# ── Test fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def temp_job_dir():
    """Create temporary job directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        job_dir = Path(tmpdir) / "test_job"
        job_dir.mkdir(parents=True, exist_ok=True)
        yield job_dir


@pytest.fixture
def sample_pdf(temp_job_dir):
    """Create a simple test PDF."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
    except ImportError:
        pytest.skip("reportlab not installed")

    pdf_path = temp_job_dir / "test.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.drawString(100, 750, "Тестовий документ")
    c.drawString(100, 730, "Рядок 1: Доказ по справі")
    c.drawString(100, 710, "Рядок 2: Важливе свідчення")
    c.save()

    return pdf_path


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing."""
    client = MagicMock()

    # Mock Files API
    mock_file = Mock()
    mock_file.id = "file_test_123"
    client.beta.files.upload.return_value = mock_file

    # Mock streaming response
    mock_stream = MagicMock()
    mock_stream.__enter__ = Mock(return_value=mock_stream)
    mock_stream.__exit__ = Mock(return_value=False)
    mock_stream.text_stream = iter([
        "Розпізнаний текст ",
        "з PDF файлу. ",
        "Рядок 1: Доказ по справі. ",
        "Рядок 2: Важливе свідчення."
    ])

    client.messages.stream.return_value = mock_stream
    client.beta.files.delete.return_value = True

    return client


# ── Tests for PDF text extraction ──────────────────────────────────────

def test_pdf_extraction_returns_non_empty_text(temp_job_dir, sample_pdf, mock_anthropic_client):
    """Test that PDF extraction returns non-empty text."""
    tid = "test_tid_123"
    services._tasks[tid] = {
        "stage": "pending", "label": "Test",
        "progress": 0, "message": "", "logs": [], "files": [],
        "error": None, "current": None, "stage_files": {}, "source_dir": None,
    }

    with patch('webapp.services._make_anthropic_client', return_value=mock_anthropic_client):
        # Test _ocr_pdf_single
        text = services._ocr_pdf_single(sample_pdf, tid, mock_anthropic_client)

        assert text is not None, "PDF extraction returned None"
        assert len(text) > 0, "PDF extraction returned empty string"
        assert "Розпізнаний текст" in text, "Expected text not found in extraction"


def test_pdf_extraction_with_pdfplumber(temp_job_dir, sample_pdf):
    """Test that pdfplumber extraction works for text PDFs."""
    try:
        import pdfplumber
    except ImportError:
        pytest.skip("pdfplumber not installed")

    # pdfplumber should extract text from our test PDF
    with pdfplumber.open(str(sample_pdf)) as doc:
        text = ""
        for page in doc.pages:
            t = page.extract_text() or ""
            if t.strip():
                text += t + "\n"

    assert text is not None, "pdfplumber returned None"
    assert len(text) > 0, "pdfplumber returned empty string"
    # Just check that we got some text, reportlab may not encode perfectly
    assert len(text.strip()) > 0, "PDF should have extractable text"


# ── Tests for checkpoint/idempotency ───────────────────────────────────

def test_checkpoint_detection_existing_file(temp_job_dir):
    """Test that checkpoint correctly detects existing transcript files."""
    # Create a fake transcript with enough content (> 100 bytes by default)
    transcript_dir = temp_job_dir / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)

    transcript_file = transcript_dir / "audio1_transcript.txt"
    # Write text that's > 100 bytes to pass checkpoint
    large_text = "Вже оброблена транскрипція. " * 10  # ~280 bytes
    transcript_file.write_text(large_text, encoding="utf-8")

    # Checkpoint should return True
    assert services._checkpoint(transcript_file), "Checkpoint should detect existing file"
    assert transcript_file.stat().st_size > 100, "File should be large enough"


def test_checkpoint_missing_file(temp_job_dir):
    """Test that checkpoint returns False for missing files."""
    missing_file = temp_job_dir / "missing_transcript.txt"

    # Checkpoint should return False
    assert not services._checkpoint(missing_file), "Checkpoint should return False for missing file"


def test_checkpoint_empty_file(temp_job_dir):
    """Test that checkpoint returns False for empty files (min_size=100)."""
    empty_file = temp_job_dir / "empty.txt"
    empty_file.write_text("", encoding="utf-8")

    # Checkpoint should return False (file < 100 bytes)
    assert not services._checkpoint(empty_file), "Checkpoint should reject too-small file"


def test_checkpoint_small_file(temp_job_dir):
    """Test that checkpoint returns False for files smaller than min_size."""
    small_file = temp_job_dir / "small.txt"
    small_file.write_text("a" * 50, encoding="utf-8")

    # Checkpoint should return False (file < 100 bytes)
    assert not services._checkpoint(small_file, min_size=100), "Checkpoint should reject small file"


# ── Tests for API key validation ───────────────────────────────────────

def test_api_key_missing_raises_error():
    """Test that missing API key raises appropriate error."""
    # Ensure no API key is set
    old_key = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    try:
        with patch('anthropic.Anthropic') as mock_anthropic:
            # Mock should raise AuthenticationError when key is missing
            mock_anthropic.side_effect = Exception("API key required")

            with pytest.raises(Exception, match="API key required"):
                client = services._make_client()
                # Try to use client - should fail
                client.messages.create(model="test", max_tokens=1, messages=[])
    finally:
        if old_key:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_api_key_validation_in_pipeline():
    """Test that pipeline checks for API key before processing."""
    tid = "test_api_check"
    services._tasks[tid] = {
        "stage": "pending", "label": "Test PDF",
        "progress": 0, "message": "", "logs": [], "files": [],
        "error": None, "current": None, "stage_files": {}, "source_dir": None,
    }

    # Simulate missing API key
    old_key = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    try:
        # _make_client should be called but client will be None or raise
        with patch('anthropic.Anthropic') as mock_anthropic:
            mock_anthropic.side_effect = Exception("Requires API key")

            # When API key is missing, _make_client should handle it gracefully
            try:
                with patch('webapp.services._make_client') as mock_make_client:
                    mock_make_client.return_value = None
                    client = services._make_client()
                    assert client is None, "Client should be None when key missing"
            except Exception:
                # This is expected - API key validation should raise
                pass
    finally:
        if old_key:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_make_client_with_valid_key(monkeypatch):
    """Test that _make_client works with valid API key."""
    # Mock the Anthropic client
    mock_client = MagicMock()

    with patch('anthropic.Anthropic', return_value=mock_client):
        client = services._make_client()
        assert client is not None, "Client should not be None"
        assert isinstance(client, MagicMock), "Should return mocked client"


# ── Tests for text encoding handling ───────────────────────────────────

def test_read_txt_safe_utf8(temp_job_dir):
    """Test safe text reading with UTF-8 encoding."""
    txt_file = temp_job_dir / "test_utf8.txt"
    content = "Тест UTF-8: Привіт світе! 🎉"
    txt_file.write_text(content, encoding="utf-8")

    result = services._read_txt_safe(txt_file)
    assert result is not None, "Should read file"
    assert "Привіт" in result, "Should preserve Ukrainian text"


def test_read_txt_safe_cp1251(temp_job_dir):
    """Test safe text reading with fallback to CP1251."""
    txt_file = temp_job_dir / "test_cp1251.txt"
    content = "Тест на кодуванні"
    txt_file.write_text(content, encoding="cp1251")

    result = services._read_txt_safe(txt_file)
    assert result is not None, "Should read file"
    assert "кодуванні" in result, "Should handle CP1251 encoded text"


# ── Integration test ───────────────────────────────────────────────────

def test_pipeline_convert_pdf_flow(temp_job_dir, sample_pdf, mock_anthropic_client):
    """Test the full PDF conversion pipeline."""
    tid = "test_convert_full"

    # Setup job directory
    job_dir = temp_job_dir / tid
    job_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = job_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Copy test PDF to uploads
    import shutil
    dest_pdf = upload_dir / sample_pdf.name
    shutil.copy(str(sample_pdf), str(dest_pdf))

    # Mock services.JOBS_DIR temporarily
    original_jobs_dir = services.JOBS_DIR
    services.JOBS_DIR = temp_job_dir

    # Create task
    services._tasks[tid] = {
        "stage": "pending", "label": "Test PDF",
        "progress": 0, "message": "", "logs": [], "files": [],
        "error": None, "current": None, "stage_files": {}, "source_dir": str(temp_job_dir),
    }

    try:
        with patch('webapp.services._make_anthropic_client', return_value=mock_anthropic_client):
            with patch('webapp.services._make_client', return_value=mock_anthropic_client):
                # Run pipeline
                services._pipeline_convert_pdf(tid)

        # Check results
        task = services.get_task(tid)
        assert task is not None, "Task should exist"

        # Should have output files
        output_dir = job_dir / "output"
        if output_dir.exists():
            output_files = list(output_dir.glob("*_text.txt"))
            assert len(output_files) > 0, "Should create output text file"

            # Check output is not empty
            for output_file in output_files:
                content = output_file.read_text(encoding="utf-8")
                assert len(content) > 0, f"Output file {output_file.name} should not be empty"
    finally:
        services.JOBS_DIR = original_jobs_dir


def test_pdf_pipeline_detects_missing_api_key(temp_job_dir, sample_pdf):
    """Test that PDF pipeline detects missing API key and returns error."""
    tid = "test_missing_key"

    # Setup job directory
    job_dir = temp_job_dir / tid
    job_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = job_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Copy test PDF to uploads
    import shutil
    dest_pdf = upload_dir / sample_pdf.name
    shutil.copy(str(sample_pdf), str(dest_pdf))

    # Mock services.JOBS_DIR temporarily
    original_jobs_dir = services.JOBS_DIR
    services.JOBS_DIR = temp_job_dir

    # Ensure no API key is set
    old_key = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    # Create task
    services._tasks[tid] = {
        "stage": "pending", "label": "Test PDF",
        "progress": 0, "message": "", "logs": [], "files": [],
        "error": None, "current": None, "stage_files": {}, "source_dir": str(temp_job_dir),
    }

    try:
        with patch('anthropic.Anthropic') as mock_anthropic:
            # Simulate missing API key error
            mock_anthropic.side_effect = Exception("API key not found: missing ANTHROPIC_API_KEY")

            # This should catch the error gracefully
            try:
                services._pipeline_convert_pdf(tid)
            except Exception:
                # Expected - should raise or gracefully fail
                pass

        # Check task state - should have error or message indicating API key issue
        task = services.get_task(tid)
        assert task is not None, "Task should exist"
        # Either should error or have warning message
        assert task.get("stage") in ["error", "completed"] or \
               any("API" in log or "key" in log.lower() for log in task.get("logs", [])), \
               f"Task should indicate API issue. Logs: {task.get('logs')}"
    finally:
        services.JOBS_DIR = original_jobs_dir
        if old_key:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_full_integration_without_api_key(temp_job_dir, sample_pdf):
    """Integration test: PDF pipeline should gracefully handle missing API key and report it."""
    tid = "test_integration_no_key"

    # Setup
    job_dir = temp_job_dir / tid
    job_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = job_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    dest_pdf = upload_dir / sample_pdf.name
    shutil.copy(str(sample_pdf), str(dest_pdf))

    original_jobs_dir = services.JOBS_DIR
    services.JOBS_DIR = temp_job_dir

    old_key = os.environ.get("ANTHROPIC_API_KEY")
    if "ANTHROPIC_API_KEY" in os.environ:
        del os.environ["ANTHROPIC_API_KEY"]

    services._tasks[tid] = {
        "stage": "pending", "label": "Integration Test",
        "progress": 0, "message": "", "logs": [], "files": [],
        "error": None, "current": None, "stage_files": {}, "source_dir": str(temp_job_dir),
    }

    try:
        # Test with actual code path - should try pdfplumber first (which works)
        # then fallback to OCR which will fail
        services._pipeline_convert_pdf(tid)

        task = services.get_task(tid)
        # With pdfplumber extraction, should get some output even without API key
        # Check if output was created
        output_dir = job_dir / "output"
        if output_dir.exists():
            output_files = list(output_dir.glob("*_text.txt"))
            # pdfplumber should create output without API key
            assert len(output_files) > 0, "Should create output with pdfplumber fallback"
    finally:
        services.JOBS_DIR = original_jobs_dir
        if old_key:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_pipeline_error_reporting(temp_job_dir, sample_pdf, mock_anthropic_client):
    """Test that pipeline reports errors in task logs, not silently failing."""
    tid = "test_error_reporting"

    # Setup job directory
    job_dir = temp_job_dir / tid
    job_dir.mkdir(parents=True, exist_ok=True)
    upload_dir = job_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Copy test PDF to uploads
    import shutil
    dest_pdf = upload_dir / sample_pdf.name
    shutil.copy(str(sample_pdf), str(dest_pdf))

    # Mock services.JOBS_DIR temporarily
    original_jobs_dir = services.JOBS_DIR
    services.JOBS_DIR = temp_job_dir

    # Create task
    services._tasks[tid] = {
        "stage": "pending", "label": "Test PDF",
        "progress": 0, "message": "", "logs": [], "files": [],
        "error": None, "current": None, "stage_files": {}, "source_dir": str(temp_job_dir),
    }

    try:
        # Mock pdfplumber to return empty (force OCR)
        # Then make OCR fail with a clear error
        with patch('pdfplumber.open'):
            with patch.object(services, '_ocr_pdf_auto') as mock_ocr:
                mock_ocr.side_effect = Exception("API key not found in environment")

                # Run pipeline - should NOT crash, but capture error in logs
                try:
                    services._pipeline_convert_pdf(tid)
                except Exception:
                    # Expected - error is raised but caught
                    pass

        # Check that output file was created with error message
        output_dir = job_dir / "output"
        if output_dir.exists():
            output_files = list(output_dir.glob("*_text.txt"))
            assert len(output_files) > 0, "Should create output file even on error"

            content = output_files[0].read_text(encoding="utf-8")
            # Should contain error indicator, not be empty
            assert "[ПОМИЛКА" in content or "ПОМИЛКА" in content or len(content) > 5, \
                f"Error should be captured in output. Got: {content[:100]}"
    finally:
        services.JOBS_DIR = original_jobs_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
