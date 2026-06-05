#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Court Defense AI — Native Desktop Application Entry Point.

Run: python run_app.py → pywebview window + FastAPI backend on port 8000
"""
import threading
import time
import sys
import signal
from pathlib import Path

# Add src/ to path for court_defense imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

import webview

# ── Background server thread ─────────────────────────────────────────────────

_server_thread = None
_should_exit = False


def start_backend_server():
    """Start uvicorn server in a background thread."""
    from uvicorn import run as uvicorn_run

    print("[Backend] Starting FastAPI on http://127.0.0.1:8000...")
    try:
        uvicorn_run(
            "court_defense.api.main:app",
            host="127.0.0.1",
            port=8000,
            log_level="info",
            access_log=True,
        )
    except Exception as e:
        print(f"[Backend] Error: {e}")


def verify_server_ready(timeout: int = 30) -> bool:
    """
    Ping server until it responds or timeout.
    Returns True if server is ready, False if timeout.
    """
    import httpx

    url = "http://127.0.0.1:8000/"
    start = time.time()

    while time.time() - start < timeout:
        try:
            with httpx.Client() as client:
                response = client.get(url, timeout=1.0)
                if response.status_code == 200:
                    print("[Startup] OK: Backend is ready")
                    return True
        except Exception:
            pass

        time.sleep(0.5)

    print("[Startup] TIMEOUT: Backend failed to start")
    return False


def on_window_closed():
    """Called when user closes the pywebview window."""
    print("[Shutdown] User closed window, shutting down...")
    global _should_exit
    _should_exit = True
    sys.exit(0)


def main():
    """Initialize and run the desktop app."""
    global _server_thread

    print("=" * 70)
    print("Court Defense AI v2.0 — Desktop Application")
    print("=" * 70)

    # ── Start backend server in background thread ──────────────────────────────
    _server_thread = threading.Thread(target=start_backend_server, daemon=True)
    _server_thread.start()
    print("[Startup] Backend thread started (daemon mode)")

    # ── Wait for server to be ready ────────────────────────────────────────────
    if not verify_server_ready(timeout=30):
        print("[Error] Backend failed to initialize. Exiting.")
        sys.exit(1)

    # ── Create and show pywebview window ───────────────────────────────────────
    print("[UI] Creating pywebview window...")
    window = webview.create_window(
        title="Court Defense AI - Defense Strategy System",
        url="http://127.0.0.1:8000",
        width=1200,
        height=800,
        text_select=True,
    )

    # ── Handle window close event ──────────────────────────────────────────────
    window.events.closed += on_window_closed

    print("[UI] Window opened. Starting main event loop...")
    print("=" * 70)

    try:
        # Start pywebview event loop (blocks until window closed)
        webview.start(debug=False)
    except KeyboardInterrupt:
        print("\n[Shutdown] Keyboard interrupt received")
    except Exception as e:
        print(f"[Error] {e}", file=sys.stderr)
    finally:
        print("[Shutdown] Cleaning up...")
        sys.exit(0)


if __name__ == "__main__":
    main()
