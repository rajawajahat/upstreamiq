from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal


class LinkType(str, Enum):
    IMPORTS_TYPES   = "imports_types"    # Imports TypeScript types / Pydantic models
    CALLS_REST      = "calls_rest"       # Makes HTTP calls to the upstream's API
    CALLS_GRPC      = "calls_grpc"       # gRPC consumer
    RUNS_PACKAGE    = "runs_package"     # npm/pip package dependency
    SHARES_SCHEMA   = "shares_schema"    # Shared database schema / OpenAPI spec


class ChangeKind(str, Enum):
    BREAKING     = "breaking"     # Removed field, changed type, removed endpoint
    ADDITIVE     = "additive"     # Added field, added endpoint (safe)
    DEPRECATION  = "deprecation"  # Marked deprecated (warn only)
    INTERNAL     = "internal"     # Implementation change, no interface impact


@dataclass
class Repo:
    """A single repository registered with RepoLink."""
    name: str                           # Human name, e.g. "api-service"
    path: str                           # Absolute path on disk
    language: str = "unknown"           # "typescript", "python", "go", "rust", "unknown"
    description: str = ""               # Optional one-line description
    api_spec_path: str = ""             # Relative path to openapi.yaml if exists
    registered_at: str = ""             # ISO timestamp

    @property
    def abs_path(self) -> Path:
        return Path(self.path)

    @property
    def claude_upstream_path(self) -> Path:
        return self.abs_path / "CLAUDE.upstream.md"

    @property
    def claude_md_path(self) -> Path:
        return self.abs_path / "CLAUDE.md"


@dataclass
class Link:
    """A directed dependency relationship: downstream consumes upstream."""
    downstream: str        # Repo name that depends on upstream
    upstream: str          # Repo name being depended upon
    link_type: LinkType    # Nature of the dependency
    description: str = ""  # Optional human note, e.g. "calls /api/users"
    created_at: str = ""


@dataclass
class ExtractedSurface:
    """The public API surface extracted from an upstream repo."""
    repo_name: str
    commit_sha: str
    extracted_at: str

    # TypeScript / Python exported types
    exported_types: list[TypeDef] = field(default_factory=list)

    # REST endpoints (inferred or from OpenAPI)
    endpoints: list[EndpointDef] = field(default_factory=list)

    # Package exports (functions, classes)
    package_exports: list[ExportDef] = field(default_factory=list)

    # Cross-cutting conventions relevant to consumers
    consumer_conventions: list[str] = field(default_factory=list)


@dataclass
class TypeDef:
    name: str           # e.g. "User"
    definition: str     # Full type/interface/class body (compact, single-line if short)
    file_path: str      # Relative path where it's defined
    is_exported: bool = True
    deprecated: bool = False
    change_note: str = ""   # Set when this type recently changed


@dataclass
class EndpointDef:
    method: str         # GET, POST, PUT, DELETE, PATCH
    path: str           # e.g. "/api/users/:id"
    request_schema: str = ""   # Compact type representation
    response_schema: str = ""  # Compact type representation
    description: str = ""
    change_note: str = ""      # Set when recently changed


@dataclass
class ExportDef:
    name: str           # Function or class name
    signature: str      # Full signature
    description: str = ""


@dataclass
class ChangeEvent:
    """A detected change in an upstream repo's public surface."""
    upstream_repo: str
    commit_sha: str
    commit_message: str
    committed_at: str
    kind: ChangeKind
    affected_symbol: str     # Type name, endpoint path, or function name
    before: str              # What it looked like before (empty if new)
    after: str               # What it looks like now (empty if removed)
    affected_downstream: list[str] = field(default_factory=list)
