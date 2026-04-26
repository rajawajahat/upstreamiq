def test_change_analyzer_detects_removed_type():
    from upstreamiq.graph.models import ChangeKind, ExtractedSurface, TypeDef
    from upstreamiq.watcher.change_analyzer import analyze_diff
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    old = ExtractedSurface(
        repo_name="api",
        commit_sha="abc",
        extracted_at=now,
        exported_types=[
            TypeDef(name="User", definition="{ id: string; email: string; }", file_path="t.ts"),
            TypeDef(name="Token", definition="{ value: string; }", file_path="t.ts"),
        ],
    )
    new = ExtractedSurface(
        repo_name="api",
        commit_sha="def",
        extracted_at=now,
        exported_types=[
            TypeDef(name="User", definition="{ id: string; email: string; }", file_path="t.ts"),
            # Token removed
        ],
    )
    changes = analyze_diff(old, new, "def123", "remove Token", ["frontend"])
    breaking = [c for c in changes if c.kind == ChangeKind.BREAKING]
    assert any(c.affected_symbol == "Token" for c in breaking)


def test_change_analyzer_detects_new_type():
    from upstreamiq.graph.models import ChangeKind, ExtractedSurface, TypeDef
    from upstreamiq.watcher.change_analyzer import analyze_diff
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    old = ExtractedSurface(repo_name="api", commit_sha="abc", extracted_at=now)
    new = ExtractedSurface(
        repo_name="api",
        commit_sha="def",
        extracted_at=now,
        exported_types=[TypeDef(name="NewType", definition="{ x: string; }", file_path="t.ts")],
    )
    changes = analyze_diff(old, new, "def123", "add NewType", [])
    additive = [c for c in changes if c.kind == ChangeKind.ADDITIVE]
    assert any(c.affected_symbol == "NewType" for c in additive)


def test_change_analyzer_detects_removed_endpoint():
    from upstreamiq.graph.models import ChangeKind, EndpointDef, ExtractedSurface
    from upstreamiq.watcher.change_analyzer import analyze_diff
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    old = ExtractedSurface(
        repo_name="api",
        commit_sha="abc",
        extracted_at=now,
        endpoints=[EndpointDef(method="GET", path="/api/users")],
    )
    new = ExtractedSurface(repo_name="api", commit_sha="def", extracted_at=now)
    changes = analyze_diff(old, new, "def123", "remove endpoint", ["frontend"])
    breaking = [c for c in changes if c.kind == ChangeKind.BREAKING]
    assert any("/api/users" in c.affected_symbol for c in breaking)
