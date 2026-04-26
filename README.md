# upstreamiq

**Upstream intelligence for AI coding agents.**

> Your Claude Code / Cursor session is blind about your other repos. upstreamiq fixes that in 60 seconds.

```bash
pip install upstreamiq
```

---

## The problem

You work across 3 repos: `frontend` · `api-service` · `shared-types`

Every AI coding session starts from zero:
- Claude has no idea what `api-service` exports
- It uses `User.email` — which changed to `emails[]` three weeks ago
- You spend 10 minutes re-explaining the same types. Every. Single. Session.

## The fix

upstreamiq extracts the **public interface** of your upstream repos — types, endpoints, OpenAPI contracts — and writes a surgical `CLAUDE.upstream.md` into each downstream repo. Always fresh. Always under 200 lines. Zero manual work.

```
shared-types ──► api-service ──► frontend
                            └──► mobile
```

Each downstream repo gets a `CLAUDE.upstream.md` like this:

```markdown
## api-service  [calls_rest]
> Last synced: a3f9c2b · 2 hours ago
> ⚠ BREAKING CHANGE: User.email → User.emails[]  (commit a3f9c2b)

### Exported types
class User(BaseModel):
    id: str
    emails: list[str]   # changed from: email: str
    name: str

### API endpoints
GET  /api/users/{user_id}  →  User
POST /api/users             →  User
```

Your AI agent reads this at the start of every session. It already knows the upstream shape. It already sees the breaking change. **You write correct code the first time.**

---

## Quickstart

```bash
# 1. Register your repos
upstreamiq add api-service ~/projects/api-service
upstreamiq add shared-types ~/projects/shared-types
upstreamiq add frontend ~/projects/frontend

# 2. Define relationships
upstreamiq link frontend --consumes api-service
upstreamiq link frontend --consumes shared-types --type imports_types
upstreamiq link api-service --consumes shared-types --type imports_types

# 3. Generate upstream context
upstreamiq sync
# → writes CLAUDE.upstream.md into frontend/

# 4. Keep it fresh automatically
upstreamiq watch
# → polls git every 30s, re-syncs on every upstream commit
```

Then add one line to your `CLAUDE.md`:

```
@CLAUDE.upstream.md
```

Done. Claude Code reads the upstream context at the start of every session.

---

## Cross-repo task planning

Working on a feature that spans multiple repos? upstreamiq figures out the right order automatically:

```bash
upstreamiq task "add phone number to user profiles"
```

Output:
```
Step 1: shared-types  → add PhoneNumber type       (no upstreams — start here)
Step 2: api-service   → add field + endpoint        (depends on shared-types)
Step 3: frontend      → update form UI              (depends on api-service)
Step 4: mobile        → update form UI              (depends on api-service)
```

Each step includes the exact instruction to paste into Claude Code. Run `upstreamiq sync` between steps — every session picks up where the last left off.

---

## Commands

| Command | What it does |
|---|---|
| `upstreamiq add NAME PATH` | Register a repo |
| `upstreamiq link A --consumes B` | Define that A depends on B |
| `upstreamiq sync` | Generate CLAUDE.upstream.md for all downstream repos |
| `upstreamiq watch` | Watch for upstream changes and auto-sync |
| `upstreamiq extract [REPO]` | Extract the API surface from a repo |
| `upstreamiq changes` | Show recent breaking changes detected |
| `upstreamiq task "description"` | Generate a cross-repo task plan |
| `upstreamiq init [PATH]` | Scan a directory and register all git repos |
| `upstreamiq list` | Show repos and dependency graph |
| `upstreamiq show REPO` | Show the full extracted surface for a repo |
| `upstreamiq status` | Health check of your setup |

---

## What gets extracted

| Language | Types | Routes |
|---|---|---|
| TypeScript / JavaScript | `export interface`, `export type` | Express, Next.js App Router |
| Python | Pydantic `BaseModel`, `@dataclass` | FastAPI, Flask, Django |
| Any | OpenAPI `components/schemas` | OpenAPI/Swagger YAML or JSON |
| Go, Rust, Ruby, etc. | — | URL pattern scan (fallback) |

---

## How it works

```
git commit in api-service
        │
        ▼
upstreamiq detects new commit (watch mode, every 30s)
        │
        ▼
re-extracts public surface → types + endpoints
        │
        ▼
compares with previous surface → finds breaking changes
        │
        ▼
rewrites CLAUDE.upstream.md in frontend/ and mobile/
with ⚠ BREAKING CHANGE notices at the top
        │
        ▼
you open Claude Code → it already knows
```

---

## Configuration (optional)

Add a `.upstreamiq.toml` to any repo for fine-grained control:

```toml
[repo]
name = "api-service"
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

---

## License

MIT · Built by [Raja Wajahat](https://github.com/rajawajahat)
