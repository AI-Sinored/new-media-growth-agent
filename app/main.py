from __future__ import annotations

import csv
import io

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.agents import pipeline
from app.core.config import get_settings
from app.core.database import db
from app.core.schemas import AgentRunResult, ContentRequest, FeedbackRecord, FeedbackRequest

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@app.post("/api/run", response_model=AgentRunResult)
async def run_agent(request: ContentRequest) -> AgentRunResult:
    return await pipeline.run(request, persist=True)


@app.get("/api/runs")
def list_runs(limit: int = 20) -> list[dict]:
    return db.list_runs(limit=limit)


@app.get("/api/runs/{run_id}", response_model=AgentRunResult)
def get_run(run_id: int) -> AgentRunResult:
    result = db.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@app.post("/api/feedback", response_model=FeedbackRecord)
def save_feedback(feedback: FeedbackRequest) -> FeedbackRecord:
    existing = db.get_run(feedback.run_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Run not found")
    if feedback.idea_id not in {idea.idea_id for idea in existing.ideas}:
        raise HTTPException(status_code=400, detail="idea_id does not belong to this run")
    return db.save_feedback(feedback)


@app.get("/api/export/{run_id}.csv")
def export_csv(run_id: int) -> StreamingResponse:
    result = db.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "idea_id",
        "score",
        "publish_slot",
        "topic",
        "angle",
        "target_user_pain",
        "title_1",
        "title_2",
        "cover_copy",
        "hook",
        "caption",
        "hashtags",
        "cta",
        "production_notes",
    ])
    for idea in result.ideas:
        writer.writerow([
            idea.idea_id,
            idea.score,
            idea.publish_slot,
            idea.topic,
            idea.angle,
            idea.target_user_pain,
            idea.titles[0] if idea.titles else "",
            idea.titles[1] if len(idea.titles) > 1 else "",
            idea.cover_copy,
            idea.hook,
            idea.caption,
            " ".join(idea.hashtags),
            idea.cta,
            idea.production_notes,
        ])
    buffer.seek(0)
    filename = f"content_growth_run_{run_id}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
