from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.core.config import get_settings
from app.core.schemas import AgentRunResult, FeedbackRecord, FeedbackRequest


def _db_path_from_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    return "./data/content_growth.db"


class Database:
    def __init__(self) -> None:
        settings = get_settings()
        self.db_path = Path(_db_path_from_url(settings.database_url))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    run_id INTEGER NOT NULL,
                    idea_id TEXT NOT NULL,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    leads INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    engagement_rate REAL DEFAULT 0,
                    conversion_rate REAL DEFAULT 0,
                    FOREIGN KEY(run_id) REFERENCES agent_runs(id)
                )
                """
            )

    def save_run(self, result: AgentRunResult) -> AgentRunResult:
        payload = result.model_dump(mode="json")
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO agent_runs(created_at, request_json, result_json) VALUES (?, ?, ?)",
                (
                    result.created_at.isoformat(),
                    json.dumps(payload["request"], ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            result.run_id = int(cursor.lastrowid)
            payload["run_id"] = result.run_id
            conn.execute("UPDATE agent_runs SET result_json = ? WHERE id = ?", (json.dumps(payload, ensure_ascii=False), result.run_id))
        return result

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, created_at, request_json FROM agent_runs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        records: list[dict] = []
        for row in rows:
            request = json.loads(row["request_json"])
            records.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "brand_name": request.get("brand_name"),
                    "platform": request.get("platform"),
                    "goal": request.get("goal"),
                }
            )
        return records

    def get_run(self, run_id: int) -> AgentRunResult | None:
        with self.connect() as conn:
            row = conn.execute("SELECT result_json FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return AgentRunResult.model_validate_json(row["result_json"])

    def save_feedback(self, feedback: FeedbackRequest) -> FeedbackRecord:
        engagement_rate = 0.0 if feedback.views == 0 else round((feedback.likes + feedback.comments + feedback.shares) / feedback.views, 4)
        conversion_rate = 0.0 if feedback.views == 0 else round(feedback.leads / feedback.views, 4)
        created_at = datetime.utcnow()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO feedback(created_at, run_id, idea_id, views, likes, comments, shares, leads, notes, engagement_rate, conversion_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at.isoformat(),
                    feedback.run_id,
                    feedback.idea_id,
                    feedback.views,
                    feedback.likes,
                    feedback.comments,
                    feedback.shares,
                    feedback.leads,
                    feedback.notes,
                    engagement_rate,
                    conversion_rate,
                ),
            )
            record_id = int(cursor.lastrowid)
        return FeedbackRecord(
            id=record_id,
            created_at=created_at,
            engagement_rate=engagement_rate,
            conversion_rate=conversion_rate,
            **feedback.model_dump(),
        )

    def get_feedback_for_brand(self, brand_name: str, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT f.*
                FROM feedback f
                JOIN agent_runs r ON f.run_id = r.id
                WHERE json_extract(r.request_json, '$.brand_name') = ?
                ORDER BY f.id DESC
                LIMIT ?
                """,
                (brand_name, limit),
            ).fetchall()
        return [dict(row) for row in rows]


db = Database()
