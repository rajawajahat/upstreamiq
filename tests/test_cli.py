"""CLI integration tests using Typer's test runner."""
import pytest
from pathlib import Path
from typer.testing import CliRunner

from upstreamiq.cli import app
from upstreamiq.graph.store import GraphStore

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect all CLI commands to a temp DB so tests don't touch ~/.repolink."""
    db_path = tmp_path / "test.db"

    original_get_store = None

    def patched_get_store():
        return GraphStore(db_path=db_path)

    import upstreamiq.cli as cli_module
    monkeypatch.setattr(cli_module, "_get_store", patched_get_store)
    return db_path


@pytest.fixture
def api_repo(tmp_path):
    p = tmp_path / "api-service"
    p.mkdir()
    (p / "requirements.txt").write_text("fastapi\npydantic\n")
    (p / "main.py").write_text("""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    id: str
    email: str

@app.get("/api/users")
async def list_users() -> list:
    pass
""")
    return p


@pytest.fixture
def ts_repo(tmp_path):
    p = tmp_path / "frontend"
    p.mkdir()
    (p / "package.json").write_text('{"name": "frontend"}')
    src = p / "src"
    src.mkdir()
    (src / "types.ts").write_text("""
export interface User {
  id: string;
  email: string;
}
""")
    return p


# ── version ──────────────────────────────────────────────────────────────────

def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "repolink" in result.output
    assert "0.1.0" in result.output


# ── add ───────────────────────────────────────────────────────────────────────

def test_add_repo(api_repo):
    result = runner.invoke(app, ["add", "api-service", str(api_repo)])
    assert result.exit_code == 0
    assert "Registered" in result.output
    assert "api-service" in result.output


def test_add_repo_with_lang_override(api_repo):
    result = runner.invoke(app, ["add", "api-service", str(api_repo), "--lang", "go"])
    assert result.exit_code == 0
    assert "go" in result.output


def test_add_repo_with_desc(api_repo):
    result = runner.invoke(app, ["add", "api-service", str(api_repo), "--desc", "My API"])
    assert result.exit_code == 0
    assert "Registered" in result.output


def test_add_nonexistent_path():
    result = runner.invoke(app, ["add", "api-service", "/nonexistent/path/xyz"])
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_add_duplicate_shows_updating(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["add", "api-service", str(api_repo)])
    assert result.exit_code == 0
    assert "already registered" in result.output


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_empty():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No repos" in result.output


def test_list_with_repos(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "api-service" in result.output
    assert "frontend" in result.output


def test_list_shows_dependency_tree(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "api-service" in result.output
    assert "frontend" in result.output
    assert "consumed by" in result.output


# ── link ──────────────────────────────────────────────────────────────────────

def test_link_repos(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    result = runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    assert result.exit_code == 0
    assert "Linked" in result.output
    assert "frontend" in result.output
    assert "api-service" in result.output


def test_link_with_explicit_type(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    result = runner.invoke(app, ["link", "frontend", "--consumes", "api-service", "--type", "calls_rest"])
    assert result.exit_code == 0
    assert "calls_rest" in result.output


def test_link_invalid_type(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    result = runner.invoke(app, ["link", "frontend", "--consumes", "api-service", "--type", "invalid_type"])
    assert result.exit_code == 1
    assert "Invalid link type" in result.output


def test_link_missing_downstream(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["link", "nonexistent", "--consumes", "api-service"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_link_missing_upstream(ts_repo):
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    result = runner.invoke(app, ["link", "frontend", "--consumes", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


# ── unlink ────────────────────────────────────────────────────────────────────

def test_unlink(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    result = runner.invoke(app, ["unlink", "frontend", "--from", "api-service"])
    assert result.exit_code == 0
    assert "Removed link" in result.output


# ── remove ────────────────────────────────────────────────────────────────────

def test_remove_repo(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["remove", "api-service", "--yes"])
    assert result.exit_code == 0
    assert "Removed" in result.output


def test_remove_nonexistent():
    result = runner.invoke(app, ["remove", "nonexistent", "--yes"])
    assert result.exit_code == 1
    assert "not found" in result.output


# ── extract ───────────────────────────────────────────────────────────────────

def test_extract_all(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    result = runner.invoke(app, ["extract"])
    assert result.exit_code == 0
    assert "api-service" in result.output
    assert "frontend" in result.output


def test_extract_single(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["extract", "api-service"])
    assert result.exit_code == 0
    assert "api-service" in result.output
    assert "types" in result.output


def test_extract_verbose(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["extract", "api-service", "--verbose"])
    assert result.exit_code == 0


def test_extract_nonexistent():
    result = runner.invoke(app, ["extract", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_extract_no_repos():
    result = runner.invoke(app, ["extract"])
    assert result.exit_code == 0
    assert "No repos" in result.output


# ── sync ──────────────────────────────────────────────────────────────────────

def test_sync_no_links(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "No downstream" in result.output


def test_sync_generates_upstream_md(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    result = runner.invoke(app, ["sync"])
    assert result.exit_code == 0
    assert "synced" in result.output
    upstream_md = ts_repo / "CLAUDE.upstream.md"
    assert upstream_md.exists()
    content = upstream_md.read_text()
    assert "api-service" in content
    assert "AUTO-GENERATED" in content


def test_sync_dry_run(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    result = runner.invoke(app, ["sync", "--dry-run"])
    assert result.exit_code == 0
    # Should NOT create the file in dry-run
    upstream_md = ts_repo / "CLAUDE.upstream.md"
    assert not upstream_md.exists()


def test_sync_injects_claude_md(api_repo, ts_repo):
    (ts_repo / "CLAUDE.md").write_text("# Frontend\n")
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    runner.invoke(app, ["sync"])
    claude_md = (ts_repo / "CLAUDE.md").read_text()
    assert "@CLAUDE.upstream.md" in claude_md


def test_sync_does_not_duplicate_injection(api_repo, ts_repo):
    (ts_repo / "CLAUDE.md").write_text("# Frontend\n@CLAUDE.upstream.md\n")
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    runner.invoke(app, ["sync"])
    runner.invoke(app, ["sync"])  # second sync
    content = (ts_repo / "CLAUDE.md").read_text()
    assert content.count("@CLAUDE.upstream.md") == 1


def test_sync_single_repo(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    result = runner.invoke(app, ["sync", "frontend"])
    assert result.exit_code == 0
    assert "frontend" in result.output


def test_sync_nonexistent_repo(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["sync", "nonexistent"])
    assert result.exit_code == 1


# ── show ──────────────────────────────────────────────────────────────────────

def test_show_no_surface():
    result = runner.invoke(app, ["show", "nonexistent"])
    assert result.exit_code == 0
    assert "No surface cached" in result.output


def test_show_with_surface(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["extract", "api-service"])
    result = runner.invoke(app, ["show", "api-service"])
    assert result.exit_code == 0


def test_show_types_only(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["extract", "api-service"])
    result = runner.invoke(app, ["show", "api-service", "--types-only"])
    assert result.exit_code == 0


def test_show_endpoints_only(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["extract", "api-service"])
    result = runner.invoke(app, ["show", "api-service", "--endpoints-only"])
    assert result.exit_code == 0


# ── changes ───────────────────────────────────────────────────────────────────

def test_changes_no_upstreams():
    result = runner.invoke(app, ["changes"])
    assert result.exit_code == 0
    assert "No upstream repos" in result.output


def test_changes_empty_history(api_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    result = runner.invoke(app, ["changes", "api-service"])
    assert result.exit_code == 0
    assert "No changes" in result.output


def test_changes_nonexistent_repo():
    result = runner.invoke(app, ["changes", "nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output


# ── task ──────────────────────────────────────────────────────────────────────

def test_task_generates_plan(api_repo, ts_repo, tmp_path):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    out_file = tmp_path / "plan.md"
    result = runner.invoke(app, ["task", "add phone number", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text()
    assert "add phone number" in content
    assert "api-service" in content
    assert "frontend" in content


def test_task_no_repos():
    result = runner.invoke(app, ["task", "do something"])
    assert result.exit_code == 0
    assert "No repos" in result.output


# ── init ──────────────────────────────────────────────────────────────────────

def test_init_empty_dir(tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert "No git repos found" in result.output


def test_init_finds_git_repo(tmp_path):
    # Create a fake git repo
    repo_dir = tmp_path / "my-service"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    (repo_dir / "requirements.txt").write_text("fastapi\n")
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0
    assert "my-service" in result.output


def test_init_nonexistent_path():
    result = runner.invoke(app, ["init", "/nonexistent/xyz/abc"])
    assert result.exit_code == 1
    assert "does not exist" in result.output


# ── status ────────────────────────────────────────────────────────────────────

def test_status_empty():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "repos registered" in result.output


def test_status_with_data(api_repo, ts_repo):
    runner.invoke(app, ["add", "api-service", str(api_repo)])
    runner.invoke(app, ["add", "frontend", str(ts_repo)])
    runner.invoke(app, ["link", "frontend", "--consumes", "api-service"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "2 repos registered" in result.output
    assert "1 links defined" in result.output
