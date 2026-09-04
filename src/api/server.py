from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import os
import sqlite3

app = FastAPI(title="Lead Discovery Engine V3")

# We will serve the static index.html
app.mount("/static", StaticFiles(directory="src/api/static"), name="static")

# Mock reference to a global job manager for simplicity in this file
global_job_manager = None
active_job = None

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("src/api/static/index.html", "r") as f:
        return f.read()

@app.get("/api/status")
async def get_status():
    if not active_job:
        return {"status": "STOPPED", "message": "No active job"}
    
    return {
        "job_id": active_job.id,
        "query": active_job.query,
        "location": active_job.location,
        "status": active_job.status,
        "discovered": active_job.discovered_count,
        "enriched": active_job.enriched_count,
        "emails": active_job.email_count,
        "runtime_seconds": (active_job.updated_at - active_job.started_at).total_seconds() if active_job.started_at else 0
    }

@app.post("/api/start")
async def start_job(background_tasks: BackgroundTasks, query: str, location: str, duration_seconds: int = None, target: int = None):
    global active_job
    if active_job and active_job.status == "running":
        return {"error": "A job is already running"}
        
    # In a real app, we would initialize the full JobManager and Orchestrator here
    # For now, we mock the start for UI demonstration
    # active_job = await global_job_manager.create_and_run_job(...)
    return {"message": "Job started mock", "query": query, "location": location}

@app.post("/api/stop")
async def stop_job():
    global active_job
    if active_job and active_job.status == "running":
        active_job.status = "stopped"
        return {"message": "Job stopping"}
    return {"message": "No running job"}
