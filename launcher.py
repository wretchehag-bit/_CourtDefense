"""
Court Defense AI — GUI Launcher
Встановлює залежності, запускає сервер, відкриває браузер.
"""
import os, sys, json, time, socket, threading, subprocess, webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

# ── Base directory (works both from source and from PyInstaller exe) ───────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

SETTINGS_FILE  = BASE_DIR / ".launcher_settings.json"
VENV_DIR       = BASE_DIR / ".venv"
SETUP_MARKER   = VENV_DIR / ".setup_done"
REQUIREMENTS   = BASE_DIR / "requirements.txt"

# Palette matching the web UI
C = {
    "bg":      "#0f1117",
    "surface": "#1a1d27",
    "border":  "#2a2d3a",
    "accent":  "#4f8ef7",
    "green":   "#22c55e",
    "yellow":  "#f59e0b",
    "red":     "#ef4444",
    "text":    "#e2e8f0",
    "muted":   "#64748b",
}


# ─────────────────────────────────────────────────────────────────────────────
class Launcher:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Court Defense AI")
        self.root.geometry("720x560")
        self.root.minsize(620, 460)
        self.root.configure(bg=C["bg"])
        try:                                        # taskbar icon
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.server_proc  = None
        self.server_ready = False
        self._stop_event  = threading.Event()

        self.api_key_var  = tk.StringVar()
        self.port_var     = tk.StringVar(value="8000")
        self.status_var   = tk.StringVar(value="⚫  Не запущено")
        self.status_color = tk.StringVar(value=C["muted"])

        self._load_settings()
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Settings ─────────────────────────────────────────────────────────────

    def _load_settings(self):
        try:
            d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            self.api_key_var.set(d.get("api_key", ""))
            self.port_var.set(str(d.get("port", "8000")))
        except Exception:
            pass

    def _save_settings(self):
        try:
            SETTINGS_FILE.write_text(json.dumps({
                "api_key": self.api_key_var.get().strip(),
                "port":    self.port_var.get().strip(),
            }), encoding="utf-8")
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = self.root

        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=C["surface"], pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚖️  Court Defense AI",
                 bg=C["surface"], fg=C["text"],
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=20)
        self.status_lbl = tk.Label(hdr, textvariable=self.status_var,
                                   bg=C["surface"], fg=C["muted"],
                                   font=("Segoe UI", 11))
        self.status_lbl.pack(side="right", padx=20)

        # ── Settings strip ────────────────────────────────────────────────
        sf = tk.Frame(root, bg=C["surface"], padx=16, pady=10)
        sf.pack(fill="x", pady=(1, 0))

        tk.Label(sf, text="API Key:", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=(0, 8))
        key_entry = tk.Entry(sf, textvariable=self.api_key_var, show="•",
                             bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                             relief="flat", bd=0, font=("Consolas", 10), width=42)
        key_entry.grid(row=0, column=1, sticky="ew", ipady=5, padx=(0, 12))
        key_entry.bind("<Return>", lambda _: self._save_settings())
        key_entry.bind("<FocusOut>", lambda _: self._save_settings())

        tk.Label(sf, text="Порт:", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=(0, 6))
        port_entry = tk.Entry(sf, textvariable=self.port_var,
                              bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                              relief="flat", bd=0, font=("Consolas", 10), width=6)
        port_entry.grid(row=0, column=3, ipady=5)
        sf.columnconfigure(1, weight=1)

        # ── Action buttons ────────────────────────────────────────────────
        bf = tk.Frame(root, bg=C["bg"], padx=16, pady=12)
        bf.pack(fill="x")

        self.btn_start = self._btn(bf, "▶  Запустити", C["accent"],
                                   "#fff", self._on_start)
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_stop = self._btn(bf, "■  Зупинити", C["surface"],
                                  C["red"], self._on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 10))

        self.btn_browser = self._btn(bf, "🌐  Відкрити браузер", C["surface"],
                                     C["green"], self._open_browser, state="disabled")
        self.btn_browser.pack(side="left")

        self.btn_install = self._btn(bf, "⚙  Встановити залежності", C["surface"],
                                     C["yellow"], self._on_install)
        self.btn_install.pack(side="right")

        # ── Log area ──────────────────────────────────────────────────────
        lf = tk.Frame(root, bg=C["border"], padx=1, pady=1)
        lf.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        log_header = tk.Frame(lf, bg=C["surface"], pady=6)
        log_header.pack(fill="x")
        tk.Label(log_header, text="📋 Лог", bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=12)
        self.log_btn_clear = tk.Button(log_header, text="Очистити",
                                       bg=C["surface"], fg=C["muted"],
                                       relief="flat", bd=0, cursor="hand2",
                                       font=("Segoe UI", 9),
                                       command=self._clear_log)
        self.log_btn_clear.pack(side="right", padx=12)

        self.log = scrolledtext.ScrolledText(
            lf, bg=C["bg"], fg="#94a3b8",
            insertbackground=C["text"],
            font=("Consolas", 9), relief="flat", bd=0,
            state="disabled", wrap="word",
        )
        self.log.pack(fill="both", expand=True)

        # Configure log colour tags
        self.log.tag_config("ok",  foreground=C["green"])
        self.log.tag_config("err", foreground=C["red"])
        self.log.tag_config("hi",  foreground=C["text"], font=("Consolas", 9, "bold"))
        self.log.tag_config("dim", foreground=C["muted"])

        # ── Footer ────────────────────────────────────────────────────────
        ft = tk.Frame(root, bg=C["surface"], pady=5)
        ft.pack(fill="x")
        tk.Label(ft, text="Court Defense AI v2.0  |  http://localhost:" + self.port_var.get(),
                 bg=C["surface"], fg=C["muted"],
                 font=("Segoe UI", 9)).pack()

        # Auto-start if setup done
        if SETUP_MARKER.exists():
            self.root.after(400, self._on_start)
        else:
            self._log("Залежності не встановлені. Натисни '⚙ Встановити залежності'.", "dim")

    def _btn(self, parent, text, bg, fg, cmd, state="normal"):
        b = tk.Button(parent, text=text, bg=bg, fg=fg,
                      activebackground=bg, activeforeground=fg,
                      relief="flat", bd=0, padx=18, pady=9,
                      font=("Segoe UI", 10, "bold"),
                      cursor="hand2", state=state, command=cmd)
        b.bind("<Enter>", lambda _: b.configure(bg=self._lighten(bg)))
        b.bind("<Leave>", lambda _: b.configure(bg=bg))
        return b

    @staticmethod
    def _lighten(hex_color: str) -> str:
        try:
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            r, g, b = min(r + 20, 255), min(g + 20, 255), min(b + 20, 255)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    # ── Logging ───────────────────────────────────────────────────────────────

    def _log(self, msg: str, tag: str = ""):
        def _do():
            self.log.configure(state="normal")
            self.log.insert("end", msg.rstrip() + "\n", tag)
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(0, _do)

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _set_status(self, text: str, color: str):
        def _do():
            self.status_var.set(text)
            self.status_lbl.configure(fg=color)
        self.root.after(0, _do)

    def _set_buttons(self, running: bool):
        def _do():
            s_start   = "disabled" if running else "normal"
            s_stop    = "normal"   if running else "disabled"
            s_browser = "normal"   if running else "disabled"
            self.btn_start.configure(state=s_start)
            self.btn_stop.configure(state=s_stop)
            self.btn_browser.configure(state=s_browser)
        self.root.after(0, _do)

    # ── Port helper ───────────────────────────────────────────────────────────

    def _port_free(self, port: int) -> bool:
        with socket.socket() as s:
            return s.connect_ex(("127.0.0.1", port)) != 0

    # ── Python / venv helpers ─────────────────────────────────────────────────

    def _python(self) -> str:
        """Return path to the Python executable to use."""
        venv_py = VENV_DIR / "Scripts" / "python.exe"
        if venv_py.exists():
            return str(venv_py)
        return sys.executable

    def _pip(self) -> str:
        venv_pip = VENV_DIR / "Scripts" / "pip.exe"
        if venv_pip.exists():
            return str(venv_pip)
        return str(Path(sys.executable).parent / "pip.exe")

    # ── Install ───────────────────────────────────────────────────────────────

    def _on_install(self):
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        self._set_status("⚙  Встановлення…", C["yellow"])
        self.btn_install.configure(state="disabled")
        self._log("═" * 55, "hi")
        self._log("Встановлення залежностей…", "hi")

        # Create venv if needed
        if not (VENV_DIR / "Scripts" / "python.exe").exists():
            self._log(f"Створюю venv: {VENV_DIR}", "dim")
            r = subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                capture_output=True, text=True
            )
            if r.returncode != 0:
                self._log(f"Помилка venv:\n{r.stderr}", "err")
                self._set_status("❌  Помилка", C["red"])
                self.btn_install.configure(state="normal")
                return
            self._log("✓ venv створено", "ok")

        # Upgrade pip silently
        subprocess.run(
            [self._python(), "-m", "pip", "install", "--upgrade", "pip", "-q"],
            capture_output=True
        )

        # Try CUDA torch first; fall back to CPU if no GPU / download fails
        self._log("Перевіряю GPU…", "dim")
        cuda_ok = False
        try:
            import subprocess as _sp
            r = _sp.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                        capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                gpu_name = r.stdout.strip().splitlines()[0]
                self._log(f"GPU знайдено: {gpu_name} — встановлюю torch+CUDA 12.8…", "ok")
                r2 = subprocess.run(
                    [self._pip(), "install", "torch",
                     "--index-url", "https://download.pytorch.org/whl/cu128",
                     "--progress-bar", "off"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                )
                for line in r2.stdout.splitlines():
                    if line.strip():
                        self._log(line, "dim")
                cuda_ok = (r2.returncode == 0)
                if cuda_ok:
                    self._log("✓ torch+CUDA встановлено — транскрипція буде на GPU", "ok")
                else:
                    self._log("⚠ CUDA torch не вдалося — буде CPU", "err")
        except Exception as e:
            self._log(f"GPU не знайдено або nvidia-smi недоступний: {e}", "dim")

        # Install requirements (torch already installed if cuda_ok)
        self._log("pip install -r requirements.txt…", "dim")
        proc = subprocess.Popen(
            [self._pip(), "install", "-r", str(REQUIREMENTS),
             "--progress-bar", "off"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            tag = "ok" if "Successfully installed" in line else \
                  "err" if "ERROR" in line or "error" in line.lower() else "dim"
            self._log(line, tag)
        proc.wait()

        if proc.returncode == 0:
            SETUP_MARKER.write_text("ok", encoding="utf-8")
            self._log("✅ Всі залежності встановлено!", "ok")
            self._set_status("✅  Готово до запуску", C["green"])
            self.root.after(800, self._on_start)
        else:
            self._log("❌ Встановлення завершилось з помилкою. Перевір лог.", "err")
            self._set_status("❌  Помилка встановлення", C["red"])
            self.btn_install.configure(state="normal")

    # ── Start / Stop ──────────────────────────────────────────────────────────

    def _on_start(self):
        self._save_settings()
        port_str = self.port_var.get().strip()
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Помилка", f"Невірний порт: {port_str}")
            return

        if not self._port_free(port):
            # Maybe server is already running — just open browser
            self._log(f"Порт {port} зайнятий — можливо сервер вже запущено.", "dim")
            self._set_status(f"🟢  localhost:{port}", C["green"])
            self._set_buttons(True)
            self._open_browser()
            return

        if not SETUP_MARKER.exists():
            if messagebox.askyesno("Залежності не встановлені",
                                   "Встановити їх зараз? (перший запуск ~5-15 хв)"):
                self._on_install()
            return

        api_key = self.api_key_var.get().strip()
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

        self._stop_event.clear()
        self.server_ready = False
        self._set_buttons(True)
        self._set_status("🟡  Запускається…", C["yellow"])
        self._log("═" * 55, "hi")
        self._log(f"Запускаю сервер на порту {port}…", "hi")

        threading.Thread(target=self._server_thread, args=(port,), daemon=True).start()

    def _server_thread(self, port: int):
        python = self._python()
        cmd = [
            python, "-m", "uvicorn",
            "webapp.main:app",
            "--host", "0.0.0.0",
            "--port", str(port),
            "--no-access-log",
        ]
        env = {**os.environ, "PYTHONUNBUFFERED": "1",
               "PYTHONPATH": str(BASE_DIR)}

        try:
            self.server_proc = subprocess.Popen(
                cmd, cwd=str(BASE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                env=env,
            )
        except FileNotFoundError:
            self._log("❌ Python/uvicorn не знайдено. Встанови залежності.", "err")
            self._set_status("❌  Помилка", C["red"])
            self._set_buttons(False)
            return

        for line in self.server_proc.stdout:
            if self._stop_event.is_set():
                break
            line = line.rstrip()
            if not line:
                continue
            tag = "ok"  if ("started" in line.lower() or "running" in line.lower()) else \
                  "err" if ("error" in line.lower() or "exception" in line.lower()) else ""
            self._log(line, tag)
            if not self.server_ready and ("running on" in line.lower() or
                                          "application startup" in line.lower()):
                self.server_ready = True
                self._set_status(f"🟢  localhost:{port}", C["green"])
                self.root.after(300, self._open_browser)

        self.server_proc.wait()
        if not self._stop_event.is_set():
            self._log("⚠️ Сервер зупинився несподівано.", "err")
            self._set_status("❌  Сервер впав", C["red"])
            self._set_buttons(False)

    def _on_stop(self):
        self._stop_event.set()
        if self.server_proc and self.server_proc.poll() is None:
            self.server_proc.terminate()
            try:
                self.server_proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.server_proc.kill()
        self.server_proc = None
        self.server_ready = False
        self._set_buttons(False)
        self._set_status("⚫  Не запущено", C["muted"])
        self._log("Сервер зупинено.", "dim")

    # ── Browser ───────────────────────────────────────────────────────────────

    def _open_browser(self):
        port = self.port_var.get().strip()
        webbrowser.open(f"http://localhost:{port}")

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        if self.server_proc and self.server_proc.poll() is None:
            if not messagebox.askyesno("Вихід",
                                       "Сервер запущений. Зупинити і вийти?"):
                return
        self._save_settings()
        self._on_stop()
        self.root.destroy()

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    Launcher().run()
