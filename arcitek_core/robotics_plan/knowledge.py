"""Append-only temporal knowledge repository with provenance retrieval."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from .storage import SQLiteStore
from .validation import (
    MAX_LIST_ITEMS,
    MAX_NAME_LENGTH,
    MAX_TEXT_LENGTH,
    ValidationError,
    validate_dict,
    validate_identifier,
    validate_list,
    validate_number,
    validate_string,
)

MAX_JSON_BYTES = 65_536
RELATIONSHIP_TYPES = {
    "supports",
    "contradicts",
    "extends",
    "derived_from",
    "applies_to",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _json_dump(value: Any, field: str) -> str:
    try:
        serialized = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must contain JSON-compatible values") from exc
    if len(serialized.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValidationError(f"{field} must be at most {MAX_JSON_BYTES} bytes")
    return serialized


class KnowledgeRepository:
    """Stores immutable knowledge versions and returns bounded evidence packets."""

    def __init__(
        self,
        database: str | Path = ":memory:",
        *,
        store: SQLiteStore | None = None,
    ) -> None:
        self.store = store or SQLiteStore(database)

    def add_source(
        self,
        *,
        source_type: str,
        canonical_uri: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source_type = validate_string(source_type, "source_type", max_len=80)
        canonical_uri = validate_string(
            canonical_uri, "canonical_uri", max_len=2_000
        )
        title = validate_string(title, "title", max_len=MAX_NAME_LENGTH)
        metadata_json = _json_dump(
            validate_dict(metadata, "metadata"), "metadata"
        )
        with self.store.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM knowledge_sources WHERE canonical_uri = ?",
                (canonical_uri,),
            ).fetchone()
            if existing is not None:
                return self._source_from_row(existing)
            source_id = _new_id("src")
            created_at = time.time()
            connection.execute(
                """
                INSERT INTO knowledge_sources
                    (id, source_type, canonical_uri, title, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    source_type,
                    canonical_uri,
                    title,
                    metadata_json,
                    created_at,
                ),
            )
        return {
            "id": source_id,
            "source_type": source_type,
            "canonical_uri": canonical_uri,
            "title": title,
            "metadata": json.loads(metadata_json),
            "created_at": created_at,
        }

    def list_sources(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1_000))
        with self.store.lock:
            rows = self.store.connection.execute(
                """
                SELECT * FROM knowledge_sources
                ORDER BY created_at, rowid LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._source_from_row(row) for row in rows]

    def append_record(
        self,
        *,
        project_id: str,
        actor: str,
        reason: str,
        record_type: str,
        content: dict[str, Any],
        parent_id: str | None = None,
        supersedes_id: str | None = None,
        source_id: str | None = None,
        build_id: str | None = None,
        agent_run_id: str | None = None,
        confidence: float | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        project_id = validate_identifier(project_id, "project_id")
        actor = validate_string(actor, "actor", max_len=MAX_NAME_LENGTH)
        reason = validate_string(reason, "reason", max_len=MAX_TEXT_LENGTH)
        record_type = validate_string(record_type, "record_type", max_len=80)
        content_json = _json_dump(validate_dict(content, "content"), "content")
        confidence = validate_number(
            confidence,
            "confidence",
            minimum=0,
            maximum=1,
            required=False,
        )
        normalized_tags = self._validate_tags(tags)
        for field, value in (
            ("parent_id", parent_id),
            ("supersedes_id", supersedes_id),
            ("source_id", source_id),
            ("build_id", build_id),
            ("agent_run_id", agent_run_id),
        ):
            if value is not None:
                validate_identifier(value, field)

        with self.store.transaction() as connection:
            self._require_row(connection, "projects", project_id, "project")
            self._validate_record_link(
                connection, project_id, parent_id, "parent_id"
            )
            self._validate_record_link(
                connection, project_id, supersedes_id, "supersedes_id"
            )
            if source_id is not None:
                self._require_row(
                    connection, "knowledge_sources", source_id, "source"
                )
            if build_id is not None:
                self._require_row(connection, "builds", build_id, "build")
            if agent_run_id is not None:
                self._require_row(
                    connection, "agent_runs", agent_run_id, "agent run"
                )

            record_id = _new_id("kn")
            created_at = time.time()
            content_hash = hashlib.sha256(content_json.encode("utf-8")).hexdigest()
            connection.execute(
                """
                INSERT INTO knowledge_records
                    (id, project_id, build_id, parent_id, supersedes_id,
                     source_id, agent_run_id, actor, reason, record_type,
                     content_json, content_hash, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    project_id,
                    build_id,
                    parent_id,
                    supersedes_id,
                    source_id,
                    agent_run_id,
                    actor,
                    reason,
                    record_type,
                    content_json,
                    content_hash,
                    confidence,
                    created_at,
                ),
            )
            for tag in normalized_tags:
                tag_row = connection.execute(
                    "SELECT id FROM knowledge_tags WHERE name = ?", (tag,)
                ).fetchone()
                tag_id = tag_row["id"] if tag_row else _new_id("tag")
                if tag_row is None:
                    connection.execute(
                        "INSERT INTO knowledge_tags (id, name) VALUES (?, ?)",
                        (tag_id, tag),
                    )
                connection.execute(
                    """
                    INSERT INTO knowledge_record_tags (record_id, tag_id)
                    VALUES (?, ?)
                    """,
                    (record_id, tag_id),
                )
        return self.get_record(record_id)

    def add_citation(
        self,
        record_id: str,
        *,
        source_id: str,
        locator: str,
        quote: str | None = None,
    ) -> dict[str, Any]:
        record_id = validate_identifier(record_id, "record_id")
        source_id = validate_identifier(source_id, "source_id")
        locator = validate_string(locator, "locator", max_len=MAX_TEXT_LENGTH)
        if quote is not None:
            quote = validate_string(quote, "quote", max_len=MAX_TEXT_LENGTH)
        citation = {
            "id": _new_id("cite"),
            "record_id": record_id,
            "source_id": source_id,
            "locator": locator,
            "quote_hash": (
                hashlib.sha256(quote.encode("utf-8")).hexdigest()
                if quote is not None
                else None
            ),
            "created_at": time.time(),
        }
        with self.store.transaction() as connection:
            self._require_row(
                connection, "knowledge_records", record_id, "knowledge record"
            )
            self._require_row(
                connection, "knowledge_sources", source_id, "source"
            )
            connection.execute(
                """
                INSERT INTO citations
                    (id, record_id, source_id, locator, quote_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                tuple(citation.values()),
            )
        return citation

    def add_relationship(
        self,
        from_record_id: str,
        to_record_id: str,
        relationship_type: str,
    ) -> dict[str, Any]:
        from_record_id = validate_identifier(from_record_id, "from_record_id")
        to_record_id = validate_identifier(to_record_id, "to_record_id")
        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValidationError(
                f"relationship_type must be one of {sorted(RELATIONSHIP_TYPES)}"
            )
        relationship = {
            "id": _new_id("rel"),
            "from_record_id": from_record_id,
            "to_record_id": to_record_id,
            "relationship_type": relationship_type,
            "created_at": time.time(),
        }
        with self.store.transaction() as connection:
            source = self._require_row(
                connection, "knowledge_records", from_record_id, "knowledge record"
            )
            target = self._require_row(
                connection, "knowledge_records", to_record_id, "knowledge record"
            )
            if source["project_id"] != target["project_id"]:
                raise ValidationError(
                    "knowledge relationships must stay within one project"
                )
            connection.execute(
                """
                INSERT INTO knowledge_relationships
                    (id, from_record_id, to_record_id, relationship_type, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                tuple(relationship.values()),
            )
        return relationship

    def get_record(self, record_id: str) -> dict[str, Any]:
        record_id = validate_identifier(record_id, "record_id")
        with self.store.lock:
            row = self.store.connection.execute(
                "SELECT * FROM knowledge_records WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown knowledge record '{record_id}'")
            return self._record_from_row(self.store.connection, row)

    def timeline(
        self,
        project_id: str,
        *,
        tag: str | None = None,
        source_id: str | None = None,
        build_id: str | None = None,
        agent_run_id: str | None = None,
        record_type: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        project_id = validate_identifier(project_id, "project_id")
        limit = max(1, min(int(limit), 1_000))
        for field, value in (
            ("source_id", source_id),
            ("build_id", build_id),
            ("agent_run_id", agent_run_id),
        ):
            if value is not None:
                validate_identifier(value, field)
        if record_type is not None:
            record_type = validate_string(
                record_type, "record_type", max_len=80
            )
        sql = "SELECT DISTINCT kr.* FROM knowledge_records kr"
        params: list[Any] = []
        if tag is not None:
            tag = validate_string(tag, "tag", max_len=80).strip().lower()
            sql += """
                JOIN knowledge_record_tags krt ON krt.record_id = kr.id
                JOIN knowledge_tags kt ON kt.id = krt.tag_id
            """
        clauses = ["kr.project_id = ?"]
        params.append(project_id)
        for column, value in (
            ("kt.name", tag),
            ("kr.source_id", source_id),
            ("kr.build_id", build_id),
            ("kr.agent_run_id", agent_run_id),
            ("kr.record_type", record_type),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY kr.created_at, kr.rowid LIMIT ?"
        params.append(limit)
        with self.store.lock:
            connection = self.store.connection
            if connection.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise KeyError(f"Unknown project '{project_id}'")
            rows = connection.execute(sql, params).fetchall()
            return [self._record_from_row(connection, row) for row in rows]

    def context_packet(
        self,
        project_id: str,
        *,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        requested_tags = self._validate_tags(tags)
        limit = max(1, min(int(limit), 200))
        records = self.timeline(project_id, limit=1_000)
        if requested_tags:
            wanted = set(requested_tags)
            records = [
                record for record in records if wanted.intersection(record["tags"])
            ]
        truncated = len(records) > limit
        records = records[-limit:]
        record_ids = {record["id"] for record in records}
        with self.store.lock:
            relationships = [
                dict(row)
                for row in self.store.connection.execute(
                    """
                    SELECT id, from_record_id, to_record_id,
                           relationship_type, created_at
                    FROM knowledge_relationships
                    WHERE from_record_id IN (
                        SELECT id FROM knowledge_records WHERE project_id = ?
                    )
                    ORDER BY created_at, rowid
                    """,
                    (project_id,),
                ).fetchall()
                if row["from_record_id"] in record_ids
                and row["to_record_id"] in record_ids
            ]
        return {
            "project_id": project_id,
            "record_count": len(records),
            "records": records,
            "relationships": relationships,
            "conflicts": [
                relationship
                for relationship in relationships
                if relationship["relationship_type"] == "contradicts"
            ],
            "tags": requested_tags,
            "truncated": truncated,
        }

    @staticmethod
    def _validate_tags(tags: list[str] | None) -> list[str]:
        values = validate_list(tags, "tags", max_items=MAX_LIST_ITEMS)
        normalized: list[str] = []
        for index, tag in enumerate(values):
            value = validate_string(
                tag, f"tags[{index}]", max_len=80
            ).strip().lower()
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def _require_row(
        connection: sqlite3.Connection,
        table: str,
        item_id: str,
        label: str,
    ) -> sqlite3.Row:
        allowed_tables = {
            "projects",
            "knowledge_sources",
            "knowledge_records",
            "builds",
            "agent_runs",
        }
        if table not in allowed_tables:
            raise RuntimeError("Unsupported table lookup")
        row = connection.execute(
            f"SELECT * FROM {table} WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise ValidationError(f"Unknown {label} '{item_id}'")
        return row

    @classmethod
    def _validate_record_link(
        cls,
        connection: sqlite3.Connection,
        project_id: str,
        record_id: str | None,
        field: str,
    ) -> None:
        if record_id is None:
            return
        row = cls._require_row(
            connection, "knowledge_records", record_id, "knowledge record"
        )
        if row["project_id"] != project_id:
            raise ValidationError(f"{field} must reference the same project")

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_type": row["source_type"],
            "canonical_uri": row["canonical_uri"],
            "title": row["title"],
            "metadata": json.loads(row["metadata_json"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _record_from_row(
        connection: sqlite3.Connection, row: sqlite3.Row
    ) -> dict[str, Any]:
        tags = [
            tag["name"]
            for tag in connection.execute(
                """
                SELECT kt.name FROM knowledge_tags kt
                JOIN knowledge_record_tags krt ON krt.tag_id = kt.id
                WHERE krt.record_id = ? ORDER BY kt.name
                """,
                (row["id"],),
            ).fetchall()
        ]
        citations = [
            dict(citation)
            for citation in connection.execute(
                """
                SELECT id, record_id, source_id, locator, quote_hash, created_at
                FROM citations WHERE record_id = ? ORDER BY created_at, rowid
                """,
                (row["id"],),
            ).fetchall()
        ]
        return {
            "id": row["id"],
            "project_id": row["project_id"],
            "build_id": row["build_id"],
            "parent_id": row["parent_id"],
            "supersedes_id": row["supersedes_id"],
            "source_id": row["source_id"],
            "agent_run_id": row["agent_run_id"],
            "actor": row["actor"],
            "reason": row["reason"],
            "record_type": row["record_type"],
            "content": json.loads(row["content_json"]),
            "content_hash": row["content_hash"],
            "confidence": row["confidence"],
            "created_at": row["created_at"],
            "tags": tags,
            "citations": citations,
        }
