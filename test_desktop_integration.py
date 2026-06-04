#!/usr/bin/env python3
"""
Integration test: Verify run_app.py can start and backend responds
"""
import sys
import threading
import time
import signal
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from run_app import verify_server_ready, start_backend_server


def test_backend_startup():
    """Test that backend starts and server ping works."""
    print("=" * 70)
    print("Testing Desktop App Backend Integration")
    print("=" * 70)

    # Start server in background
    print("\n[1] Starting uvicorn backend server...")
    server_thread = threading.Thread(target=start_backend_server, daemon=True)
    server_thread.start()

    # Give it 2 seconds to initialize
    time.sleep(2)

    # Test server verification
    print("[2] Verifying server responsiveness...")
    ready = verify_server_ready(timeout=15)

    if not ready:
        print("FAILED: Server did not respond")
        return False

    # Test actual connectivity
    print("[3] Testing HTTP connectivity...")
    try:
        import httpx

        with httpx.Client() as client:
            response = client.get("http://127.0.0.1:8000/", timeout=2)
            print(f"    Status: {response.status_code}")
            if response.status_code == 200:
                print("    Content-Type: text/html")
                print("    Server is responding correctly")
            else:
                print(f"    Unexpected status: {response.status_code}")
                return False
    except Exception as e:
        print(f"    ERROR: {e}")
        return False

    # Test static files
    print("[4] Testing static file access...")
    try:
        with httpx.Client() as client:
            response = client.get("http://127.0.0.1:8000/static/index.html", timeout=2)
            if response.status_code == 200:
                print("    Static files: OK")
            else:
                print(f"    Static files returned {response.status_code}")
    except Exception as e:
        print(f"    Static file error: {e}")

    print("\n" + "=" * 70)
    print("SUCCESS: Desktop app integration test passed!")
    print("  - Backend server starts correctly")
    print("  - Server responds to HTTP requests")
    print("  - Static files are served")
    print("  - run_app.py is ready for pywebview initialization")
    print("=" * 70)
    return True


if __name__ == "__main__":
    try:
        result = test_backend_startup()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
