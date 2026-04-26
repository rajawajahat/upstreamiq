"""
SQLite-backed store for the dependency graph.
Database lives at: ~/.repolink/repolink.db by default.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import (
    ChangeEvent,
    ChangeKind,
    ExtractedSurface,
    EndpointDef,
    ExportDef,
    Link,
    LinkType,
    Repo,
    TypeDef,
)

DEFAULT_DB_PATH = Path.home() / ".repolink" / "repolink.db"


class GraphStore:
    def __init__(self, db_path: Path | None = None):
        self._db_path = db_path or DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS repos (
                name         TEXT PRIMARY KEY,
                path         TEXT NOT NULL,
                language     TEXT NOT NULL DEFAULT 'unknown',
                description  TEXT NOT NULL DEFAULT '',
                api_spec_path TEXT NOT NULL DEFAULT '',
                registered_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS links (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                downstream   TEXT NOT NULL,
                upstream     TEXT NOT NULL,
                link_type    TEXT NOT NULL,
                description  TEXT NOT NULL DEFAULT '',
                created_at   TEXT NOT NULL DEFAULT '',
                UNIQUE(downstream, upstream)
            );

            CREATE TABLE IF NOT EXISTS surfaces (
                repo_name    TEXT PRIMARY KEY,
                commit_sha   TEXT NOT NULL,
                extracted_at TEXT NOT NULL,
                data         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS changes (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                upstream_repo       TEXT NOT NULL,
                commit_sha          TEXT NOT NULL,
                commit_message      TEXT NOT NULL,
                committed_at        TEXT NOT NULL,
                kind                TEXT NOT NULL,
                affected_symbol     TEXT NOT NULL,
                before_text         TEXT NOT NULL DEFAULT '',
                after_text          TEXT NOT NULL DEFAULT '',
                affected_downstream TEXT NOT NULL DEFAULT '[]'
            );
        """)
        self._conn.commit()

    # ── Repo CRUD ────────────────────────────────────────────────────────────

    def add_repo(self, repo: Repo) -> None:
        if not repo.registered_at:
            repo.registered_at = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO repos VALUES (?,?,?,?,?,?)",
            (repo.name, repo.path, repo.language, repo.description,
             repo.api_spec_path, repo.registered_at),
        )
        self._conn.commit()

    def get_repo(self, name: str) -> Repo | None:
        row = self._conn.execute(
            "SELECT * FROM repos WHERE name = ?", (name,)
        ).fetchone()
        return self._row_to_repo(row) if row else None

    def list_repos(self) -> list[Repo]:
        rows = self._conn.execute("SELECT * FROM repos ORDER BY name").fetchall()
        return [self._row_to_repo(r) for r in rows]

    def remove_repo(self, name: str) -> None:
        self._conn.execute("DELETE FROM repos WHERE name = ?", (name,))
        self._conn.execute(
            "DELETE FROM links WHERE downstream = ? OR upstream = ?", (name, name)
        )
        self._conn.execute("DELETE FROM surfaces WHERE repo_name = ?", (name,))
        self._conn.commit()

    def update_repo(self, repo: Repo) -> None:
        self._conn.execute(
            """UPDATE repos SET path=?, language=?, description=?,
               api_spec_path=?, registered_at=? WHERE name=?""",
            (repo.path, repo.language, repo.description,
             repo.api_spec_path, repo.registered_at, repo.name),
        )
        self._conn.commit()

    def _row_to_repo(self, row: sqlite3.Row) -> Repo:
        return Repo(
            name=row["name"],
            path=row["path"],
            language=row["language"],
            description=row["description"],
            api_spec_path=row["api_spec_path"],
            registered_at=row["registered_at"],
        )

    # ── Link CRUD ────────────────────────────────────────────────────────────

    def add_link(self, link: Link) -> None:
        if not link.created_at:
            link.created_at = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO links (downstream, upstream, link_type, description, created_at) VALUES (?,?,?,?,?)",
            (link.downstream, link.upstream, link.link_type.value,
             link.description, link.created_at),
        )
        self._conn.commit()

    def get_links_for_downstream(self, downstream: str) -> list[Link]:
        rows = self._conn.execute(
            "SELECT * FROM links WHERE downstream = ?", (downstream,)
        ).fetchall()
        return [self._row_to_link(r) for r in rows]

    def get_links_for_upstream(self, upstream: str) -> list[Link]:
        rows = self._conn.execute(
            "SELECT * FROM links WHERE upstream = ?", (upstream,)
        ).fetchall()
        return [self._row_to_link(r) for r in rows]

    def remove_link(self, downstream: str, upstream: str) -> None:
        self._conn.execute(
            "DELETE FROM links WHERE downstream = ? AND upstream = ?",
            (downstream, upstream),
        )
        self._conn.commit()

    def list_links(self) -> list[Link]:
        rows = self._conn.execute("SELECT * FROM links").fetchall()
        return [self._row_to_link(r) for r in rows]

    def _row_to_link(self, row: sqlite3.Row) -> Link:
        return Link(
            downstream=row["downstream"],
            upstream=row["upstream"],
            link_type=LinkType(row["link_type"]),
            description=row["description"],
            created_at=row["created_at"],
        )

    # ── Surface cache ────────────────────────────────────────────────────────

    def save_surface(self, surface: ExtractedSurface) -> None:
        data = json.dumps(self._surface_to_dict(surface))
        self._conn.execute(
            "INSERT OR REPLACE INTO surfaces VALUES (?,?,?,?)",
            (surface.repo_name, surface.commit_sha, surface.extracted_at, data),
        )
        self._conn.commit()

    def get_surface(self, repo_name: str) -> ExtractedSurface | None:
        row = self._conn.execute(
            "SELECT * FROM surfaces WHERE repo_name = ?", (repo_name,)
        ).fetchone()
        if not row:
            return None
        return self._dict_to_surface(json.loads(row["data"]))

    def _surface_to_dict(self, s: ExtractedSurface) -> dict:
        return {
            "repo_name": s.repo_name,
            "commit_sha": s.commit_sha,
            "extracted_at": s.extracted_at,
            "exported_types": [
                {"name": t.name, "definition": t.definition, "file_path": t.file_path,
                 "is_exported": t.is_exported, "deprecated": t.deprecated, "change_note": t.change_note}
                for t in s.exported_types
            ],
            "endpoints": [
                {"method": e.method, "path": e.path, "request_schema": e.request_schema,
                 "response_schema": e.response_schema, "description": e.description,
                 "change_note": e.change_note}
                for e in s.endpoints
            ],
            "package_exports": [
                {"name": x.name, "signature": x.signature, "description": x.description}
                for x in s.package_exports
            ],
            "consumer_conventions": s.consumer_conventions,
        }

    def _dict_to_surface(self, d: dict) -> ExtractedSurface:
        return ExtractedSurface(
            repo_name=d["repo_name"],
            commit_sha=d["commit_sha"],
            extracted_at=d["extracted_at"],
            exported_types=[
                TypeDef(name=t["name"], definition=t["definition"], file_path=t["file_path"],
                        is_exported=t.get("is_exported", True), deprecated=t.get("deprecated", False),
                        change_note=t.get("change_note", ""))
                for t in d.get("exported_types", [])
            ],
            endpoints=[
                EndpointDef(method=e["method"], path=e["path"],
                            request_schema=e.get("request_schema", ""),
                            response_schema=e.get("response_schema", ""),
                            description=e.get("description", ""),
                            change_note=e.get("change_note", ""))
                for e in d.get("endpoints", [])
            ],
            package_exports=[
                ExportDef(name=x["name"], signature=x["signature"],
                          description=x.get("description", ""))
                for x in d.get("package_exports", [])
            ],
            consumer_conventions=d.get("consumer_conventions", []),
        )

    # ── Change history ───────────────────────────────────────────────────────

    def record_change(self, change: ChangeEvent) -> None:
        self._conn.execute(
            """INSERT INTO changes
               (upstream_repo, commit_sha, commit_message, committed_at,
                kind, affected_symbol, before_text, after_text, affected_downstream)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (change.upstream_repo, change.commit_sha, change.commit_message,
             change.committed_at, change.kind.value, change.affected_symbol,
             change.before, change.after,
             json.dumps(change.affected_downstream)),
        )
        self._conn.commit()

    def get_recent_changes(self, upstream: str, limit: int = 10) -> list[ChangeEvent]:
        rows = self._conn.execute(
            """SELECT * FROM changes WHERE upstream_repo = ?
               ORDER BY id DESC LIMIT ?""",
            (upstream, limit),
        ).fetchall()
        return [self._row_to_change(r) for r in rows]

    def get_unacknowledged_changes(self, downstream: str) -> list[ChangeEvent]:
        """Return breaking changes for upstreams that this downstream depends on."""
        links = self.get_links_for_downstream(downstream)
        results = []
        for link in links:
            rows = self._conn.execute(
                """SELECT * FROM changes WHERE upstream_repo = ? AND kind = ?
                   ORDER BY id DESC LIMIT 20""",
                (link.upstream, ChangeKind.BREAKING.value),
            ).fetchall()
            for row in rows:
                change = self._row_to_change(row)
                if downstream in change.affected_downstream:
                    results.append(change)
        return results

    def _row_to_change(self, row: sqlite3.Row) -> ChangeEvent:
        return ChangeEvent(
            upstream_repo=row["upstream_repo"],
            commit_sha=row["commit_sha"],
            commit_message=row["commit_message"],
            committed_at=row["committed_at"],
            kind=ChangeKind(row["kind"]),
            affected_symbol=row["affected_symbol"],
            before=row["before_text"],
            after=row["after_text"],
            affected_downstream=json.loads(row["affected_downstream"]),
        )

    def close(self) -> None:
        self._conn.close()
