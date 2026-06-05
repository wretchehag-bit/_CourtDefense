#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start FastAPI web server.

Run: python start_app.py  →  http://localhost:8000
Opens browser and runs uvicorn server.
"""
import os
import sys
from pathlib import Path
import webbrowser

# Add src/ to path for court_defense imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[!] ANTHROPIC_API_KEY not set.")
        print("    Set: $env:ANTHROPIC_API_KEY='sk-ant-...'")
        print("    Or enter in UI after startup.\n")

    print("=" * 56)
    print("         COURT DEFENSE AI SYSTEM")
    print("=" * 56)
    print("  http://localhost:8000")
    print("=" * 56)
    webbrowser.open("http://localhost:8000")
    uvicorn.run("court_defense.api.main:app", host="0.0.0.0", port=8000, reload=False)
