"""
FastAPI веб-оркестратор
Запуск: python start_app.py  →  http://localhost:8000
"""
import os
from pathlib import Path
from typing import List
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from . import services

WEBAPP_DIR = Path(__file__).parent

app = FastAPI(title="Court Defense System", version="2.0")
app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR / "static")), name="static")


@app.get("/")
def index():
    return FileResponse(str(WEBAPP_DIR / "static" / "index.html"))


@app.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    api_key: str = Form(""),
):
    """Upload one or more files (audio + docs) and start pipeline."""
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    names = [Path(f.filename).name for f in files]
    label = ", ".join(names[:2]) + (f" +{len(names)-2} ін." if len(names) > 2 else "")
    tid = services.create_task(label)

    upload_dir = services.JOBS_DIR / tid / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    total_kb = 0
    saved = []
    for f in files:
        content = await f.read()
        dest = upload_dir / Path(f.filename).name  # Path().name prevents traversal
        dest.write_bytes(content)
        total_kb += len(content) // 1024
        saved.append(dest.name)

    services._upd(tid, stage="uploaded", progress=5,
                  message=f"Збережено {len(saved)} файл(ів) ({total_kb} KB): {', '.join(saved[:3])}")
    background_tasks.add_task(services.start_pipeline, tid)
    return {"task_id": tid, "files": len(saved), "total_kb": total_kb, "names": saved}


@app.post("/convert-pdf")
async def convert_pdf(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    api_key: str = Form(""),
):
    """Upload PDF(s) and convert to text (OCR if scanned)."""
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    names = [Path(f.filename).name for f in files]
    tid = services.create_task("PDF → Текст: " + ", ".join(names[:2]))

    upload_dir = services.JOBS_DIR / tid / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        content = await f.read()
        (upload_dir / Path(f.filename).name).write_bytes(content)

    services._upd(tid, stage="uploaded", progress=5,
                  message=f"Завантажено {len(files)} PDF файл(ів)")
    background_tasks.add_task(services.start_convert_pdf, tid)
    return {"task_id": tid, "files": len(files)}


@app.get("/pick-folder")
def pick_folder():
    """Open native OS folder picker on the server machine, return selected path."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Вибери папку зі справою")
        root.destroy()
        return {"path": path or None}
    except Exception as e:
        raise HTTPException(500, f"Не вдалося відкрити picker: {e}")


@app.get("/scan-folder")
def scan_folder_preview(folder_path: str):
    result = services.scan_folder(folder_path)
    if result["error"]:
        raise HTTPException(400, result["error"])
    return {
        "total":       result["total"],
        "audio":       [str(f) for f in result["audio"]],
        "docs":        [str(f) for f in result["docs"]],
        "audio_count": len(result["audio"]),
        "docs_count":  len(result["docs"]),
    }


@app.get("/check-folder")
def check_folder(folder_path: str):
    """Scan folder and check which audio files already have transcripts."""
    from pathlib import Path
    result = services.scan_folder(folder_path)
    if result["error"]:
        raise HTTPException(400, result["error"])

    audio_files = result["audio"]
    sorted_dir  = services._find_sorted_dir(Path(folder_path))
    check       = services.check_audio_transcripts(audio_files, sorted_dir)

    return {
        "audio_count": len(audio_files),
        "docs_count":  len(result["docs"]),
        "done_count":  check["done_count"],
        "todo_count":  check["todo_count"],
        "sorted_dir":  check["sorted_dir"],
        "done_names":  [f.name for f in check["done"]],
        "todo_names":  [f.name for f in check["todo"]],
    }


@app.post("/run-folder")
async def run_folder(
    background_tasks: BackgroundTasks,
    folder_path: str = Form(...),
    api_key: str = Form(""),
    skip_existing: str = Form("true"),   # "true" | "false"
):
    """Run pipeline on all files in a local folder (no upload needed)."""
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    skip = skip_existing.lower() != "false"

    result = services.scan_folder(folder_path)
    if result["error"]:
        raise HTTPException(400, result["error"])
    if result["total"] == 0:
        raise HTTPException(400, f"Підтримуваних файлів не знайдено у: {folder_path}")

    folder_name = Path(folder_path).name
    tid = services.create_task(f"📁 {folder_name}")
    services._upd(tid, stage="uploaded", progress=3,
                  message=f"Папка: {folder_path} | skip_existing={skip}")
    background_tasks.add_task(services.start_folder_pipeline, tid, folder_path, skip)
    return {
        "task_id":      tid,
        "folder":       folder_path,
        "audio_count":  len(result["audio"]),
        "docs_count":   len(result["docs"]),
        "skip_existing": skip,
    }


@app.post("/cancel/{task_id}")
def cancel(task_id: str):
    task = services.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    services.cancel_task(task_id)
    return {"ok": True, "task_id": task_id}


@app.get("/status/{task_id}")
def status(task_id: str):
    task = services.get_task(task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return task


@app.get("/tasks")
def tasks():
    return services.all_tasks()


@app.get("/results")
def results():
    return {"files": services.list_results()}


@app.get("/download")
def download(path: str):
    """Download a file by absolute or relative path."""
    p = Path(path)
    if not p.is_absolute():
        p = services.SCRIPT_DIR / path.replace("/", os.sep)
    p = p.resolve()
    if not p.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(str(p), filename=p.name, media_type="text/plain; charset=utf-8")
