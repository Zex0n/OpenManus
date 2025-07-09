import json
import os
import sqlite3
from contextlib import contextmanager

# База будет лежать в корне проекта
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app_data.db"))


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.execute(
            """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            prompt TEXT,
            created_at TEXT,
            status TEXT,
            steps TEXT,
            result TEXT
        )
        """
        )


def add_task(task):
    with get_db() as db:
        db.execute(
            "INSERT INTO tasks (id, prompt, created_at, status, steps, result) VALUES (?, ?, ?, ?, ?, ?)",
            (
                task.id,
                task.prompt,
                task.created_at.isoformat(),
                task.status,
                json.dumps(task.steps),
                "",
            ),
        )


def update_task(task_id, status=None, steps=None, result=None):
    with get_db() as db:
        task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return
        new_status = status if status is not None else task["status"]
        new_steps = json.dumps(steps) if steps is not None else task["steps"]
        new_result = result if result is not None else task["result"]
        db.execute(
            "UPDATE tasks SET status = ?, steps = ?, result = ? WHERE id = ?",
            (new_status, new_steps, new_result, task_id),
        )


def get_task(task_id):
    with get_db() as db:
        task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            return None
        return dict(task)


def get_all_tasks():
    with get_db() as db:
        tasks = db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in tasks]
