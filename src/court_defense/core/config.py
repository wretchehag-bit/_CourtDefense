"""Central configuration: paths, constants, resource resolution.

This module provides:
- PROJECT_ROOT: absolute path to project root
- JOBS_DIR, DATA_DIR, ASSETS_DIR: standard directory paths
- resource_path(): resolve resources for dev and PyInstaller
- resolve_ffmpeg(): cascade FFmpeg resolution (PATH → bundled → fallback)
"""
from pathlib import Path
import sys
import shutil


def _project_root() -> Path:
    """Determine project root path.

    In dev: __file__ is src/court_defense/core/config.py → parents[3] = root
    In PyInstaller: sys.executable is dist/CourtDefense.exe → parent = root
    """
    if getattr(sys, 'frozen', False):  # PyInstaller frozen app
        return Path(sys.executable).parent
    # Dev: __file__ is src/court_defense/core/config.py
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT: Path = _project_root()
JOBS_DIR: Path = PROJECT_ROOT / "jobs"
DATA_DIR: Path = PROJECT_ROOT / "data"
ASSETS_DIR: Path = PROJECT_ROOT / "assets"

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma"}
DOC_EXTENSIONS = {".pdf", ".docx", ".txt"}


def resource_path(relative: str) -> Path:
    """Absolute path to resource; works in dev and PyInstaller .exe.

    Args:
        relative: relative path from project root (e.g., "ffmpeg/bin/ffmpeg.exe")

    Returns:
        Absolute Path object
    """
    if getattr(sys, 'frozen', False):  # PyInstaller
        base = Path(sys._MEIPASS)  # type: ignore
    else:
        base = PROJECT_ROOT
    return base / relative


def resolve_ffmpeg() -> str:
    """Cascade FFmpeg resolution: system PATH → bundled → default.

    Returns:
        Path to FFmpeg executable (str)
    """
    # Try system PATH first
    found = shutil.which("ffmpeg")
    if found:
        return found

    # Try bundled ffmpeg/bin/ffmpeg.exe
    bundled = resource_path("ffmpeg/bin/ffmpeg.exe")
    if bundled.exists():
        return str(bundled)

    # Fallback: hope FFmpeg is in PATH at runtime
    return "ffmpeg"
