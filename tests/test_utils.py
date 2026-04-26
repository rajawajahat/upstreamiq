"""Tests for utils and coverage gap-filling."""
from pathlib import Path
from datetime import datetime, timezone, timedelta


# ── fs.py ────────────────────────────────────────────────────────────────────

def test_detect_language_typescript(tmp_path):
    from upstreamiq.utils.fs import detect_language
    (tmp_path / "package.json").write_text("{}")
    (tmp_path / "tsconfig.json").write_text("{}")
    assert detect_language(tmp_path) == "typescript"


def test_detect_language_javascript(tmp_path):
    from upstreamiq.utils.fs import detect_language
    (tmp_path / "package.json").write_text("{}")
    assert detect_language(tmp_path) == "javascript"


def test_detect_language_python_requirements(tmp_path):
    from upstreamiq.utils.fs import detect_language
    (tmp_path / "requirements.txt").write_text("fastapi\n")
    assert detect_language(tmp_path) == "python"


def test_detect_language_python_pyproject(tmp_path):
    from upstreamiq.utils.fs import detect_language
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    assert detect_language(tmp_path) == "python"


def test_detect_language_go(tmp_path):
    from upstreamiq.utils.fs import detect_language
    (tmp_path / "go.mod").write_text("module example.com/m\n")
    assert detect_language(tmp_path) == "go"


def test_detect_language_rust(tmp_path):
    from upstreamiq.utils.fs import detect_language
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    assert detect_language(tmp_path) == "rust"


def test_detect_language_ruby(tmp_path):
    from upstreamiq.utils.fs import detect_language
    (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n")
    assert detect_language(tmp_path) == "ruby"


def test_detect_language_unknown(tmp_path):
    from upstreamiq.utils.fs import detect_language
    assert detect_language(tmp_path) == "unknown"


def test_detect_api_spec_root(tmp_path):
    from upstreamiq.utils.fs import detect_api_spec
    (tmp_path / "openapi.yaml").write_text("openapi: '3.0.0'\n")
    assert detect_api_spec(tmp_path) == "openapi.yaml"


def test_detect_api_spec_subdir(tmp_path):
    from upstreamiq.utils.fs import detect_api_spec
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "openapi.yaml").write_text("openapi: '3.0.0'\n")
    assert detect_api_spec(tmp_path) == "docs/openapi.yaml"


def test_detect_api_spec_none(tmp_path):
    from upstreamiq.utils.fs import detect_api_spec
    assert detect_api_spec(tmp_path) == ""


def test_relative_time_seconds():
    from upstreamiq.utils.fs import relative_time
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(seconds=30)).isoformat()
    result = relative_time(ts)
    assert "second" in result


def test_relative_time_minutes():
    from upstreamiq.utils.fs import relative_time
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(minutes=5)).isoformat()
    result = relative_time(ts)
    assert "minute" in result


def test_relative_time_hours():
    from upstreamiq.utils.fs import relative_time
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=3)).isoformat()
    result = relative_time(ts)
    assert "hour" in result


def test_relative_time_days():
    from upstreamiq.utils.fs import relative_time
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(days=5)).isoformat()
    result = relative_time(ts)
    assert "day" in result


def test_relative_time_weeks():
    from upstreamiq.utils.fs import relative_time
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(weeks=5)).isoformat()
    result = relative_time(ts)
    assert "week" in result or "month" in result


def test_relative_time_months():
    from upstreamiq.utils.fs import relative_time
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(days=90)).isoformat()
    result = relative_time(ts)
    assert "month" in result


def test_relative_time_invalid():
    from upstreamiq.utils.fs import relative_time
    result = relative_time("not-a-timestamp")
    assert result == "not-a-timestamp"


# ── change_analyzer.py ───────────────────────────────────────────────────────

def test_analyzer_field_type_changed():
    from upstreamiq.graph.models import ChangeKind, ExtractedSurface, TypeDef
    from upstreamiq.watcher.change_analyzer import analyze_diff
    now = datetime.now(timezone.utc).isoformat()

    old = ExtractedSurface(
        repo_name="api", commit_sha="abc", extracted_at=now,
        exported_types=[TypeDef(name="User", definition="interface User {\n  email: string;\n}", file_path="t.ts")],
    )
    new = ExtractedSurface(
        repo_name="api", commit_sha="def", extracted_at=now,
        exported_types=[TypeDef(name="User", definition="interface User {\n  email: string[];\n}", file_path="t.ts")],
    )
    changes = analyze_diff(old, new, "def123", "change email type", ["frontend"])
    breaking = [c for c in changes if c.kind == ChangeKind.BREAKING]
    assert any("email" in c.affected_symbol or "email" in c.before for c in breaking)


def test_analyzer_no_changes():
    from upstreamiq.graph.models import ExtractedSurface, TypeDef
    from upstreamiq.watcher.change_analyzer import analyze_diff
    now = datetime.now(timezone.utc).isoformat()

    definition = "interface User {\n  id: string;\n}"
    old = ExtractedSurface(
        repo_name="api", commit_sha="abc", extracted_at=now,
        exported_types=[TypeDef(name="User", definition=definition, file_path="t.ts")],
    )
    new = ExtractedSurface(
        repo_name="api", commit_sha="abc", extracted_at=now,
        exported_types=[TypeDef(name="User", definition=definition, file_path="t.ts")],
    )
    changes = analyze_diff(old, new, "abc", "no change", [])
    assert changes == []


def test_analyzer_new_endpoint():
    from upstreamiq.graph.models import ChangeKind, EndpointDef, ExtractedSurface
    from upstreamiq.watcher.change_analyzer import analyze_diff
    now = datetime.now(timezone.utc).isoformat()

    old = ExtractedSurface(repo_name="api", commit_sha="abc", extracted_at=now)
    new = ExtractedSurface(
        repo_name="api", commit_sha="def", extracted_at=now,
        endpoints=[EndpointDef(method="GET", path="/api/v2/users")],
    )
    changes = analyze_diff(old, new, "def123", "add v2", [])
    additive = [c for c in changes if c.kind == ChangeKind.ADDITIVE]
    assert any("/api/v2/users" in c.affected_symbol for c in additive)


def test_analyzer_endpoint_response_changed():
    from upstreamiq.graph.models import ChangeKind, EndpointDef, ExtractedSurface
    from upstreamiq.watcher.change_analyzer import analyze_diff
    now = datetime.now(timezone.utc).isoformat()

    old = ExtractedSurface(
        repo_name="api", commit_sha="abc", extracted_at=now,
        endpoints=[EndpointDef(method="GET", path="/api/users", response_schema="User[]")],
    )
    new = ExtractedSurface(
        repo_name="api", commit_sha="def", extracted_at=now,
        endpoints=[EndpointDef(method="GET", path="/api/users", response_schema="UserV2[]")],
    )
    changes = analyze_diff(old, new, "def123", "change response", ["frontend"])
    breaking = [c for c in changes if c.kind == ChangeKind.BREAKING]
    assert len(breaking) >= 1


# ── capsule.py ───────────────────────────────────────────────────────────────

def test_capsule_no_surface(tmp_path):
    from upstreamiq.graph.models import Link, LinkType, Repo
    from upstreamiq.generator.capsule import generate_capsule

    downstream = Repo(name="frontend", path=str(tmp_path / "frontend"), language="typescript")
    link = Link(downstream="frontend", upstream="api-service", link_type=LinkType.CALLS_REST)

    content = generate_capsule(
        downstream_repo=downstream,
        upstream_links=[link],
        surfaces={},  # no surface cached
        recent_changes={},
    )
    assert "api-service" in content
    assert "Not yet extracted" in content


def test_capsule_with_conventions(tmp_path):
    from upstreamiq.graph.models import ExtractedSurface, Link, LinkType, Repo
    from upstreamiq.generator.capsule import generate_capsule
    now = datetime.now(timezone.utc).isoformat()

    downstream = Repo(name="frontend", path=str(tmp_path), language="typescript")
    link = Link(downstream="frontend", upstream="api", link_type=LinkType.CALLS_REST)
    surface = ExtractedSurface(
        repo_name="api", commit_sha="abc", extracted_at=now,
        consumer_conventions=["All dates are ISO 8601", "Errors use {code, message}"],
    )
    content = generate_capsule(
        downstream_repo=downstream,
        upstream_links=[link],
        surfaces={"api": surface},
        recent_changes={},
    )
    assert "ISO 8601" in content
    assert "Conventions" in content


def test_capsule_lang_detection_python(tmp_path):
    from upstreamiq.graph.models import ExtractedSurface, Link, LinkType, Repo, TypeDef
    from upstreamiq.generator.capsule import generate_capsule
    now = datetime.now(timezone.utc).isoformat()

    downstream = Repo(name="consumer", path=str(tmp_path), language="typescript")
    link = Link(downstream="consumer", upstream="my-python-backend", link_type=LinkType.CALLS_REST)
    surface = ExtractedSurface(
        repo_name="my-python-backend", commit_sha="abc", extracted_at=now,
        exported_types=[TypeDef(name="User", definition="class User(BaseModel):\n    id: str", file_path="m.py")],
    )
    content = generate_capsule(
        downstream_repo=downstream,
        upstream_links=[link],
        surfaces={"my-python-backend": surface},
        recent_changes={},
    )
    assert "```python" in content


def test_capsule_truncation_over_200_lines(tmp_path):
    """Capsule with many types/endpoints should stay ≤200 lines."""
    from upstreamiq.graph.models import EndpointDef, ExtractedSurface, Link, LinkType, Repo, TypeDef
    from upstreamiq.generator.capsule import generate_capsule
    now = datetime.now(timezone.utc).isoformat()

    downstream = Repo(name="frontend", path=str(tmp_path), language="typescript")
    link = Link(downstream="frontend", upstream="big-api", link_type=LinkType.CALLS_REST)

    # Create a surface with many types and endpoints to trigger truncation
    types = [
        TypeDef(
            name=f"Type{i}",
            definition=f"export interface Type{i} {{\n" + "\n".join(f"  field{j}: string;" for j in range(15)) + "\n}}",
            file_path="types.ts"
        )
        for i in range(20)
    ]
    endpoints = [EndpointDef(method="GET", path=f"/api/resource/{i}") for i in range(20)]

    surface = ExtractedSurface(
        repo_name="big-api", commit_sha="abc", extracted_at=now,
        exported_types=types,
        endpoints=endpoints,
    )
    content = generate_capsule(
        downstream_repo=downstream,
        upstream_links=[link],
        surfaces={"big-api": surface},
        recent_changes={},
    )
    lines = content.splitlines()
    assert len(lines) <= 200, f"Capsule too long: {len(lines)} lines"
