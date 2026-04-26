# RepoLink

> Cross-repo context bridge for AI coding agents.

When you work across multiple repos — frontend + api-service + shared-types —
every Claude Code / Cursor / Copilot session starts blind. It has no idea what
changed upstream, what types your API returns, or what contracts your services expose.

RepoLink fixes this by automatically generating a surgical `CLAUDE.upstream.md`
in each downstream repo, containing only what that repo needs to know about its
dependencies. Always fresh. Always minimal. Zero manual maintenance.

## Install

```bash
pip install upstreamiq
```

## Quickstart (5 minutes)

```bash
# 1. Register your repos
upstreamiq add api-service ~/projects/api-service
upstreamiq add shared-types ~/projects/shared-types
upstreamiq add frontend ~/projects/frontend
upstreamiq add mobile ~/projects/mobile

# 2. Define relationships
upstreamiq link frontend --consumes api-service
upstreamiq link frontend --consumes shared-types --type imports_types
upstreamiq link mobile --consumes api-service
upstreamiq link mobile --consumes shared-types --type imports_types
upstreamiq link api-service --consumes shared-types --type imports_types

# 3. Generate upstream context for all downstream repos
upstreamiq sync

# CLAUDE.upstream.md now exists in: frontend/ and mobile/
# Your AI agents already know about the upstream API surface.

# 4. Keep it fresh (auto-syncs on every upstream commit)
upstreamiq watch
```

## The problem it solves

Without RepoLink:
- You open Claude Code in `frontend`
- Claude Code has no idea what `api-service` exports
- You spend 10 minutes explaining the API shape every session
- Claude writes code using the OLD User.email field (it changed to emails[] last week)
- It compiles locally. It crashes in production.

With RepoLink:
- `frontend/CLAUDE.upstream.md` already contains the current API surface
- Claude Code reads it automatically (imported in CLAUDE.md)
- Claude knows `User.emails` is now an array
- It also sees the `⚠ BREAKING CHANGE` notice flagging the recent change
- You write correct code the first time.

## Cross-repo task planning

```bash
upstreamiq task "add phone number to user profiles"
# Generates a TASK.md with:
# Step 1: shared-types (change User type first)
# Step 2: api-service  (add field + migration)
# Step 3: frontend     (update form UI)
# Step 4: mobile       (update form UI)
# Each step has the exact Claude Code instruction to use.
```

## Commands

| Command | What it does |
|---|---|
| `upstreamiq init [PATH]` | Scan directory and register all repos |
| `upstreamiq add NAME PATH` | Register a single repo |
| `upstreamiq link A --consumes B` | Define that A depends on B |
| `upstreamiq list` | Show repos and dependency graph |
| `upstreamiq extract [REPO]` | Extract API surface from repos |
| `upstreamiq sync [REPO]` | Generate/update CLAUDE.upstream.md files |
| `upstreamiq watch` | Watch for changes and auto-sync |
| `upstreamiq changes [UPSTREAM]` | Show recent breaking changes |
| `upstreamiq task "description"` | Generate cross-repo task plan |
| `upstreamiq show REPO` | Show extracted surface for a repo |
| `upstreamiq status` | Health check of your RepoLink setup |

## How it works

1. **Extract** — RepoLink reads your repos and extracts the public interface:
   TypeScript exported types, FastAPI/Express routes, OpenAPI specs.

2. **Watch** — A background process polls git for new commits in upstream repos.
   When something changes, it detects if it's a breaking change.

3. **Sync** — Generates a surgical `CLAUDE.upstream.md` in each downstream repo.
   Max 200 lines. Only what that repo needs to know. Breaking changes highlighted.

4. **Import** — Add `@CLAUDE.upstream.md` to your `CLAUDE.md`.
   Claude Code reads it at the start of every session. Done.

## Configuration

Optionally add a `.upstreamiq.toml` to any repo for fine-grained control:

```toml
[repo]
name = "api-service"
description = "FastAPI REST API for the SaaS platform"
language = "python"
api_spec = "openapi.yaml"

[surface]
include = ["src/", "app/", "models/"]
exclude = ["migrations/", "tests/"]

[conventions]
consumer_notes = [
    "All dates are ISO 8601 strings, never Unix timestamps",
    "Pagination uses cursor-based pagination, not page numbers",
    "Errors follow: { code: str, message: str, details?: dict }",
]
```

## Supported languages

| Language | Types | Routes | Notes |
|---|---|---|---|
| TypeScript / JavaScript | `export interface`, `export type` | Express, Next.js App Router | regex-based |
| Python | Pydantic `BaseModel`, `@dataclass` | FastAPI, Flask, Django | AST-based |
| Any (OpenAPI spec) | `components/schemas` | `paths` | YAML or JSON |
| Go, Rust, Ruby, etc. | — | URL pattern scan | generic fallback |

## License

MIT
