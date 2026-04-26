# 🧠 upstreamiq

**Upstream intelligence for AI coding agents across multiple repos.**

> Claude Code / Cursor starts every session blind about your other repos.
> upstreamiq fixes that — automatically, surgically, in 60 seconds.

[![PyPI version](https://img.shields.io/pypi/v/upstreamiq.svg)](https://pypi.org/project/upstreamiq/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

```bash
pip install upstreamiq
```

---

## 😤 The problem every multi-repo developer hits

You're working across 3 repos:

```
shared-types/     api-service/     frontend/
    User              GET /users       <UserCard>
    AuthToken         POST /users      useAuth()
    ApiResponse       DELETE /users    fetchUser()
```

You open **Claude Code in `frontend`**. You ask it to update the user profile form.

Claude writes code using `user.email` — **which your api-service changed to `user.emails[]` three weeks ago.**

It compiles. It crashes in production.

You spend 10 minutes re-explaining your API shape. Again. Every. Single. Session.

---

## ✅ The fix — upstreamiq

upstreamiq automatically extracts the **public interface** of your upstream repos — types, endpoints, OpenAPI contracts — and writes a surgical `CLAUDE.upstream.md` into each downstream repo.

```
┌─────────────────────────────────────────────────────────┐
│                     Your repo graph                      │
│                                                         │
│   shared-types ──►  api-service  ──►  frontend          │
│        │                         └──►  mobile           │
│        └─────────────────────────────►  frontend        │
│                                                         │
│   upstreamiq watches all of these.                      │
│   When api-service changes → frontend gets updated.     │
│   When shared-types changes → everyone gets updated.    │
└─────────────────────────────────────────────────────────┘
```

Each downstream repo gets a `CLAUDE.upstream.md` — automatically written, always fresh, always under 200 lines:

```markdown
## api-service  [calls_rest]
> Last synced: a3f9c2b · 2 hours ago
> ⚠️ BREAKING CHANGE: User.email → User.emails[]  (commit a3f9c2b: "refactor user model")

### Exported types
class User(BaseModel):
    id: str
    emails: list[str]    # ← changed from: email: str
    name: str
    created_at: str

class CreateUserRequest(BaseModel):
    email: str
    name: str

### API endpoints
GET  /api/users/{user_id}  →  User
POST /api/users             →  User
DELETE /api/users/{user_id} →  204
```

Claude Code reads this at the start of every session. **It already knows. You write correct code the first time.**

---

## 🚀 Quickstart — 5 minutes to full setup

### Step 1 — Install

```bash
pip install upstreamiq
```

### Step 2 — Register your repos

```bash
upstreamiq add api-service ~/projects/api-service
upstreamiq add shared-types ~/projects/shared-types
upstreamiq add frontend ~/projects/frontend
upstreamiq add mobile ~/projects/mobile
```

Output:
```
✓ Registered: api-service (python) at ~/projects/api-service
✓ Registered: shared-types (typescript) at ~/projects/shared-types
✓ Registered: frontend (typescript) at ~/projects/frontend
✓ Registered: mobile (typescript) at ~/projects/mobile
```

### Step 3 — Define relationships

Tell upstreamiq which repo consumes which:

```bash
upstreamiq link frontend --consumes api-service
upstreamiq link frontend --consumes shared-types --type imports_types
upstreamiq link mobile --consumes api-service
upstreamiq link mobile --consumes shared-types --type imports_types
upstreamiq link api-service --consumes shared-types --type imports_types
```

Output:
```
✓ Linked: frontend → api-service (calls_rest)
✓ Linked: frontend → shared-types (imports_types)
✓ Linked: mobile → api-service (calls_rest)
```

### Step 4 — Generate upstream context

```bash
upstreamiq sync
```

Output:
```
Syncing downstream repos...
✓ frontend/CLAUDE.upstream.md  — 2 upstreams, 84 lines  (0.1s)
✓ mobile/CLAUDE.upstream.md   — 2 upstreams, 79 lines  (0.1s)

2 repos synced. Your AI agents have fresh upstream context.
```

### Step 5 — Wire it into Claude Code

Add one line to `frontend/CLAUDE.md`:

```markdown
@CLAUDE.upstream.md
```

That's it. Every Claude Code session in `frontend` now starts with full knowledge of `api-service` and `shared-types`.

### Step 6 — Keep it fresh forever

```bash
upstreamiq watch
```

```
╔══════════════════════════════════════════════╗
║  upstreamiq — Watch Mode                    ║
║  Watching 4 repos | Interval: 30s           ║
║  Ctrl+C to stop                             ║
╠══════════════════════════════════════════════╣
║  api-service    ✓ synced  (14:31:58)        ║
║  shared-types   ✓ synced  (14:31:58)        ║
╚══════════════════════════════════════════════╝

⚡ api-service changed (commit a3f9c2b: "refactor User model")
   Detected: BREAKING change in type User
     Before: email: string
     After:  emails: string[]
✓ frontend/CLAUDE.upstream.md updated (breaking change highlighted)
✓ mobile/CLAUDE.upstream.md updated (breaking change highlighted)
```

---

## 🗺️ Cross-repo task planning

Working on a feature that spans multiple repos? upstreamiq generates the right order automatically:

```bash
upstreamiq task "add phone number to user profiles"
```

Output file `~/repolink-tasks/add-phone-number-to-user-profiles.md`:

```
# Cross-repo task: add phone number to user profiles

## Change sequence

| Step | Repo          | Why this order                         |
|------|---------------|----------------------------------------|
| 1    | shared-types  | Others import from here — change first |
| 2    | api-service   | Depends on shared-types                |
| 3    | frontend      | Depends on api-service                 |
| 4    | mobile        | Depends on api-service                 |

---

## Step 1: shared-types

Open a Claude Code session in: ~/projects/shared-types

Suggested instruction for Claude Code:
  "add phone number to user profiles — start with the shared type definitions.
   Add any new types, update existing ones for backward compatibility."

After completing:
  → Run: upstreamiq sync
  → This updates CLAUDE.upstream.md in api-service, frontend, mobile.
  → Then move to Step 2.
```

Work through one repo at a time. Each step's Claude session has perfect context from the previous step.

---

## 🔍 What gets extracted

upstreamiq is smart about what it reads — it never dumps the whole codebase.

| Language | What it extracts | How |
|---|---|---|
| **TypeScript** | `export interface`, `export type`, Express/Next.js routes | Regex-based |
| **Python** | Pydantic `BaseModel`, `@dataclass`, FastAPI/Flask routes | AST-based |
| **OpenAPI** | All `paths`, all `components/schemas` | YAML/JSON parser |
| **Any language** | URL patterns, README API docs, `.proto`, `.graphql` | Fallback scan |

Priority: if an OpenAPI spec exists → use it first (highest quality). Then layer in language extractors for types.

---

## 🛠️ All commands

```bash
# Setup
upstreamiq add NAME PATH              # Register a repo
upstreamiq link A --consumes B        # Define A depends on B
upstreamiq unlink A --from B          # Remove a dependency
upstreamiq remove NAME                # Unregister a repo
upstreamiq init [PATH]                # Auto-scan directory for git repos

# Core workflow
upstreamiq extract [REPO]             # Extract API surface (run once to seed)
upstreamiq sync [REPO]                # Write/update CLAUDE.upstream.md
upstreamiq watch                      # Watch + auto-sync on every commit

# Inspection
upstreamiq list                       # Show repos + dependency graph
upstreamiq show REPO                  # Show full extracted surface
upstreamiq changes [UPSTREAM]         # Show recent breaking changes
upstreamiq status                     # Health check of your setup

# Planning
upstreamiq task "description"         # Generate cross-repo task plan
```

---

## 📁 How upstreamiq fits into your project

```
your-projects/
├── shared-types/
│   ├── src/types/user.ts
│   └── CLAUDE.md                   ← no upstream context needed (it's the source)
│
├── api-service/
│   ├── main.py
│   ├── CLAUDE.md                   ← add: @CLAUDE.upstream.md
│   └── CLAUDE.upstream.md          ← AUTO-GENERATED by upstreamiq
│                                      contains: shared-types interface
│
├── frontend/
│   ├── src/
│   ├── CLAUDE.md                   ← add: @CLAUDE.upstream.md
│   └── CLAUDE.upstream.md          ← AUTO-GENERATED by upstreamiq
│                                      contains: api-service + shared-types interface
│
└── mobile/
    ├── src/
    ├── CLAUDE.md                   ← add: @CLAUDE.upstream.md
    └── CLAUDE.upstream.md          ← AUTO-GENERATED by upstreamiq
                                       contains: api-service + shared-types interface
```

---

## ⚙️ Optional configuration

Add a `.upstreamiq.toml` to any repo to customise extraction:

```toml
[repo]
name = "api-service"
description = "FastAPI REST API"
language = "python"
api_spec = "openapi.yaml"          # Use this OpenAPI spec (highest quality)

[surface]
include = ["src/", "app/", "models/"]
exclude = ["migrations/", "tests/", "scripts/"]

[conventions]
# These appear in CLAUDE.upstream.md of every downstream repo
consumer_notes = [
    "All dates are ISO 8601 strings, never Unix timestamps",
    "Pagination uses cursor-based pagination, not page numbers",
    "Errors follow: { code: str, message: str, details?: dict }",
    "All endpoints require Bearer token unless marked public",
]
```

---

## 🔄 How it works under the hood

```
┌──────────────────────────────────────────────────────────────┐
│                    upstreamiq watch loop                      │
│                                                              │
│  every 30s:                                                  │
│    for each registered repo:                                 │
│      check git HEAD sha                                      │
│        if changed:                                           │
│          re-extract public surface (types + endpoints)       │
│          diff against cached surface                         │
│          if breaking change detected:                        │
│            record ChangeEvent (BREAKING)                     │
│            add ⚠️ notice to downstream CLAUDE.upstream.md    │
│          else if additive change:                            │
│            update CLAUDE.upstream.md silently                │
│          notify terminal                                     │
└──────────────────────────────────────────────────────────────┘
```

Breaking change detection looks for:
- 🔴 **BREAKING** — field removed, type changed, endpoint removed
- 🟡 **ADDITIVE** — new field, new endpoint (safe, no notice)
- ⚪ **INTERNAL** — implementation change, no interface impact (ignored)

---

## 📦 Requirements

- Python 3.11+
- Git (repos must be git repos for watch mode)
- Works with any AI coding agent that reads `CLAUDE.md` (Claude Code, Cursor, Copilot, etc.)

---

## License

MIT · Built by [Raja Wajahat](https://github.com/rajawajahat)
