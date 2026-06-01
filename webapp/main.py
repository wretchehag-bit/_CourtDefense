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


@app.get("/download/{path:path}")
def download(path: str):
    f = services.resolve_file(path)
    if not f:
        raise HTTPException(404, "file not found")
    return FileResponse(str(f), filename=f.name, media_type="text/plain; charset=utf-8")
