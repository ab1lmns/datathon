import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .schemas import AnalysisResult


class QueueFull(Exception):
    pass


class Store:
    def __init__(self, database: Path):
        self.database = database

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL CHECK (state IN ('queued','running','done','failed')),
                    created_at REAL NOT NULL,
                    deadline REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    result TEXT,
                    error TEXT
                )
            """)

    def enqueue(self, job_id: str, created_at: float, deadline: float, limit: int) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute(
                "SELECT count(*) FROM jobs WHERE state IN ('queued','running')"
            ).fetchone()[0]
            if pending >= limit:
                raise QueueFull
            db.execute(
                "INSERT INTO jobs VALUES (?, 'queued', ?, ?, ?, NULL, NULL)",
                (job_id, created_at, deadline, time.time()),
            )

    def get(self, job_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def claim(self) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE state = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row:
                db.execute(
                    "UPDATE jobs SET state = 'running', updated_at = ? WHERE job_id = ?",
                    (time.time(), row["job_id"]),
                )
        return dict(row) if row else None

    def fail(self, job_id: str, error: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state='failed', error=?, updated_at=? "
                "WHERE job_id=? AND state IN ('queued','running')",
                (error, time.time(), job_id),
            )

    def complete(self, job_id: str, result: AnalysisResult) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state='done', result=?, updated_at=? "
                "WHERE job_id=? AND state='running' AND deadline > ?",
                (result.model_dump_json(exclude_none=True), time.time(), job_id, time.time()),
            )

    def recover(self) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state='failed', error=?, updated_at=? WHERE state='running'",
                ("Обработка прервана перезапуском сервера. Загрузите видео повторно.", time.time()),
            )

    def expire(self) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state='failed', error=?, updated_at=? "
                "WHERE state IN ('queued','running') AND deadline <= ?",
                ("Превышено время ожидания обработки.", time.time(), time.time()),
            )

    def cleanup(self, upload_dir: Path, retention_hours: int) -> None:
        cutoff = time.time() - retention_hours * 3600
        with self.connect() as db:
            rows = db.execute(
                "SELECT job_id FROM jobs WHERE state IN ('done','failed') AND updated_at < ?",
                (cutoff,),
            ).fetchall()
            for row in rows:
                (upload_dir / f"{row['job_id']}.mov").unlink(missing_ok=True)
                db.execute("DELETE FROM jobs WHERE job_id=?", (row["job_id"],))

    @staticmethod
    def response(row: dict) -> dict:
        job_id = row["job_id"]
        if row["state"] == "done":
            return {"job_id": job_id, "status": "done", **json.loads(row["result"])}
        if row["state"] == "failed":
            return {"job_id": job_id, "status": "failed", "error": row["error"]}
        return {"job_id": job_id, "status": "processing"}
