"""
Запуск веб-додатку:  python start_app.py
Відкриє браузер на  http://localhost:8000
"""
import sys, os, webbrowser
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))

if not os.environ.get("ANTHROPIC_API_KEY"):
    print("[!] ANTHROPIC_API_KEY не встановлено.")
    print("    Встанови: $env:ANTHROPIC_API_KEY='sk-ant-...'")
    print("    Або введи в UI після запуску.\n")

import uvicorn

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════╗")
    print("║         COURT DEFENSE AI SYSTEM                      ║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  http://localhost:8000                               ║")
    print("╚══════════════════════════════════════════════════════╝")
    webbrowser.open("http://localhost:8000")
    uvicorn.run("webapp.main:app", host="0.0.0.0", port=8000, reload=False)
