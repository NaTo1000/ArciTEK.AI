"""SQLite persistence shared by engineering projects and expert plans."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at REAL NOT NULL,
    current_revision INTEGER NOT NULL,
    domain TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS revisions (
    project_id TEXT NOT NULL REFERENCES projects(id),
    number INTEGER NOT NULL,
    parent INTEGER,
    created_at REAL NOT NULL,
    author TEXT NOT NULL,
    message TEXT NOT NULL,
    content_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (project_id, number),
    FOREIGN KEY (project_id, parent) REFERENCES revisions(project_id, number)
);

CREATE TABLE IF NOT EXISTS revision_approvals (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    approver TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    comment TEXT NOT NULL,
    timestamp REAL NOT NULL,
    FOREIGN KEY (project_id, revision) REFERENCES revisions(project_id, number)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    project_id TEXT NOT NULL REFERENCES projects(id),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    revision INTEGER NOT NULL,
    requested_by TEXT NOT NULL,
    created_at REAL NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY (project_id, revision) REFERENCES revisions(project_id, number)
);

CREATE TABLE IF NOT EXISTS plan_tasks (
    plan_id TEXT NOT NULL REFERENCES plans(id),
    role TEXT NOT NULL,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    depends_on_json TEXT NOT NULL,
    status TEXT NOT NULL,
    output_json TEXT,
    started_at REAL,
    completed_at REAL,
    PRIMARY KEY (plan_id, role)
);

CREATE TABLE IF NOT EXISTS plan_approvals (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    approver TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    comment TEXT NOT NULL,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_activity (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    timestamp REAL NOT NULL,
    action TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS builds (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    knowledge_snapshot_hash TEXT NOT NULL,
    FOREIGN KEY (project_id, revision) REFERENCES revisions(project_id, number)
);

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    canonical_uri TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_records (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    build_id TEXT REFERENCES builds(id),
    parent_id TEXT REFERENCES knowledge_records(id),
    supersedes_id TEXT REFERENCES knowledge_records(id),
    source_id TEXT REFERENCES knowledge_sources(id),
    agent_run_id TEXT REFERENCES agent_runs(id),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    record_type TEXT NOT NULL,
    content_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    confidence REAL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS knowledge_record_tags (
    record_id TEXT NOT NULL REFERENCES knowledge_records(id),
    tag_id TEXT NOT NULL REFERENCES knowledge_tags(id),
    PRIMARY KEY (record_id, tag_id)
);

CREATE TABLE IF NOT EXISTS citations (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES knowledge_records(id),
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id),
    locator TEXT NOT NULL,
    quote_hash TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_relationships (
    id TEXT PRIMARY KEY,
    from_record_id TEXT NOT NULL REFERENCES knowledge_records(id),
    to_record_id TEXT NOT NULL REFERENCES knowledge_records(id),
    relationship_type TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    build_id TEXT REFERENCES builds(id),
    role TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    status TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    response_json TEXT,
    confidence REAL,
    started_at REAL NOT NULL,
    completed_at REAL
);

CREATE TABLE IF NOT EXISTS council_messages (
    id TEXT PRIMARY KEY,
    agent_run_id TEXT NOT NULL REFERENCES agent_runs(id),
    parent_id TEXT REFERENCES council_messages(id),
    message_type TEXT NOT NULL,
    content_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS council_decisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    build_id TEXT REFERENCES builds(id),
    proposal_record_id TEXT REFERENCES knowledge_records(id),
    status TEXT NOT NULL,
    quorum_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS revisions_parent_idx
    ON revisions(project_id, parent);
CREATE INDEX IF NOT EXISTS revision_approvals_lookup_idx
    ON revision_approvals(project_id, revision, timestamp);
CREATE INDEX IF NOT EXISTS audit_events_project_idx
    ON audit_events(project_id, timestamp);
CREATE INDEX IF NOT EXISTS plans_project_idx
    ON plans(project_id, created_at);
CREATE INDEX IF NOT EXISTS plan_activity_plan_idx
    ON plan_activity(plan_id, timestamp);
CREATE INDEX IF NOT EXISTS knowledge_records_timeline_idx
    ON knowledge_records(project_id, created_at);

CREATE TRIGGER IF NOT EXISTS revisions_no_update
BEFORE UPDATE ON revisions BEGIN
    SELECT RAISE(ABORT, 'revisions are immutable');
END;
CREATE TRIGGER IF NOT EXISTS revisions_no_delete
BEFORE DELETE ON revisions BEGIN
    SELECT RAISE(ABORT, 'revisions are immutable');
END;
CREATE TRIGGER IF NOT EXISTS projects_revision_forward_only
BEFORE UPDATE OF current_revision ON projects
WHEN NEW.current_revision <= OLD.current_revision BEGIN
    SELECT RAISE(ABORT, 'current revision must move forward');
END;
CREATE TRIGGER IF NOT EXISTS approvals_no_update
BEFORE UPDATE ON revision_approvals BEGIN
    SELECT RAISE(ABORT, 'revision approvals are append-only');
END;
CREATE TRIGGER IF NOT EXISTS approvals_no_delete
BEFORE DELETE ON revision_approvals BEGIN
    SELECT RAISE(ABORT, 'revision approvals are append-only');
END;
CREATE TRIGGER IF NOT EXISTS audit_no_update
BEFORE UPDATE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete
BEFORE DELETE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS plan_approvals_no_update
BEFORE UPDATE ON plan_approvals BEGIN
    SELECT RAISE(ABORT, 'plan approvals are append-only');
END;
CREATE TRIGGER IF NOT EXISTS plan_approvals_no_delete
BEFORE DELETE ON plan_approvals BEGIN
    SELECT RAISE(ABORT, 'plan approvals are append-only');
END;
CREATE TRIGGER IF NOT EXISTS plan_activity_no_update
BEFORE UPDATE ON plan_activity BEGIN
    SELECT RAISE(ABORT, 'plan activity is append-only');
END;
CREATE TRIGGER IF NOT EXISTS plan_activity_no_delete
BEFORE DELETE ON plan_activity BEGIN
    SELECT RAISE(ABORT, 'plan activity is append-only');
END;
CREATE TRIGGER IF NOT EXISTS knowledge_records_no_update
BEFORE UPDATE ON knowledge_records BEGIN
    SELECT RAISE(ABORT, 'knowledge records are immutable');
END;
CREATE TRIGGER IF NOT EXISTS knowledge_records_no_delete
BEFORE DELETE ON knowledge_records BEGIN
    SELECT RAISE(ABORT, 'knowledge records are immutable');
END;
CREATE TRIGGER IF NOT EXISTS knowledge_sources_no_update
BEFORE UPDATE ON knowledge_sources BEGIN
    SELECT RAISE(ABORT, 'knowledge sources are immutable');
END;
CREATE TRIGGER IF NOT EXISTS knowledge_sources_no_delete
BEFORE DELETE ON knowledge_sources BEGIN
    SELECT RAISE(ABORT, 'knowledge sources are immutable');
END;
CREATE TRIGGER IF NOT EXISTS citations_no_update
BEFORE UPDATE ON citations BEGIN
    SELECT RAISE(ABORT, 'citations are append-only');
END;
CREATE TRIGGER IF NOT EXISTS citations_no_delete
BEFORE DELETE ON citations BEGIN
    SELECT RAISE(ABORT, 'citations are append-only');
END;
CREATE TRIGGER IF NOT EXISTS relationships_no_update
BEFORE UPDATE ON knowledge_relationships BEGIN
    SELECT RAISE(ABORT, 'knowledge relationships are append-only');
END;
CREATE TRIGGER IF NOT EXISTS relationships_no_delete
BEFORE DELETE ON knowledge_relationships BEGIN
    SELECT RAISE(ABORT, 'knowledge relationships are append-only');
END;
CREATE TRIGGER IF NOT EXISTS record_tags_no_update
BEFORE UPDATE ON knowledge_record_tags BEGIN
    SELECT RAISE(ABORT, 'knowledge record tags are append-only');
END;
CREATE TRIGGER IF NOT EXISTS record_tags_no_delete
BEFORE DELETE ON knowledge_record_tags BEGIN
    SELECT RAISE(ABORT, 'knowledge record tags are append-only');
END;
"""


class SQLiteStore:
    """Thread-safe SQLite connection and transaction boundary."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            isolation_level=None,
            timeout=30,
        )
        self.connection.row_factory = sqlite3.Row
        with self.lock:
            self.connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in self.connection.execute(
                    "PRAGMA table_info(knowledge_records)"
                ).fetchall()
            }
            if "agent_run_id" not in columns:
                self.connection.execute(
                    "ALTER TABLE knowledge_records ADD COLUMN agent_run_id TEXT"
                )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
            except Exception:
                self.connection.rollback()
                raise
            else:
                self.connection.commit()

    def close(self) -> None:
        with self.lock:
            self.connection.close()
