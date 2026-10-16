"""Owned coverage records and conversations in the existing PostgreSQL database."""
import json
import threading
from app.db.local_store import local_store

class WorkflowRepository:
    def __init__(self):
        self._initialized = False
        self._schema_lock = threading.Lock()

    def _table(self, conn):
        if self._initialized:
            return
        with self._schema_lock:
            if self._initialized:
                return
            # Serialize first-use DDL across workers as well as local threads.
            # CREATE IF NOT EXISTS alone can race in PostgreSQL's system catalogs.
            conn.execute("SELECT pg_advisory_xact_lock(984621021)")
            conn.execute("""CREATE TABLE IF NOT EXISTS coverage_analyses (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, policy_id TEXT NOT NULL,
                data JSONB NOT NULL, messages JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_coverage_analyses_owner_policy ON coverage_analyses(user_id,policy_id,created_at DESC)")
            conn.commit()
            self._initialized = True

    def save(self, result, user_id):
        with local_store._connection() as conn:
            self._table(conn)
            conn.execute("INSERT INTO coverage_analyses(id,user_id,policy_id,data) VALUES (%s,%s,%s,%s::jsonb)",
                         (result.id, user_id, result.policy_id, result.model_dump_json()))
            conn.commit()

    def get(self, analysis_id, user_id):
        with local_store._connection() as conn:
            self._table(conn)
            row = conn.execute("SELECT data,messages FROM coverage_analyses WHERE id=%s AND user_id=%s", (analysis_id,user_id)).fetchone()
            return {"analysis": row[0], "messages": row[1]} if row else None

    def list(self, user_id, policy_id):
        with local_store._connection() as conn:
            self._table(conn)
            return [row[0] for row in conn.execute("SELECT data FROM coverage_analyses WHERE user_id=%s AND policy_id=%s ORDER BY created_at DESC LIMIT 100", (user_id,policy_id)).fetchall()]

    def append(self, analysis_id, user_id, messages):
        with local_store._connection() as conn:
            self._table(conn)
            conn.execute("UPDATE coverage_analyses SET messages=messages || %s::jsonb WHERE id=%s AND user_id=%s", (json.dumps(messages),analysis_id,user_id))
            conn.commit()

workflow_repo = WorkflowRepository()
