def test_capsule_is_under_200_lines(tmp_path, graph_store):
    from upstreamiq.graph.models import (
        EndpointDef, ExtractedSurface, Link, LinkType, Repo, TypeDef,
    )
    from upstreamiq.generator.capsule import generate_capsule
    from datetime import datetime, timezone

    upstream = Repo(name="api-service", path=str(tmp_path / "api"), language="python")
    downstream = Repo(name="frontend", path=str(tmp_path / "frontend"), language="typescript")
    link = Link(downstream="frontend", upstream="api-service", link_type=LinkType.CALLS_REST)

    surface = ExtractedSurface(
        repo_name="api-service",
        commit_sha="abc123",
        extracted_at=datetime.now(timezone.utc).isoformat(),
        exported_types=[TypeDef(name="User", definition="{ id: str; email: str }", file_path="models.py")],
        endpoints=[EndpointDef(method="GET", path="/api/users", response_schema="User[]")],
    )

    content = generate_capsule(
        downstream_repo=downstream,
        upstream_links=[link],
        surfaces={"api-service": surface},
        recent_changes={},
    )

    lines = content.split("\n")
    assert len(lines) <= 200, f"Capsule too long: {len(lines)} lines"
    assert "api-service" in content
    assert "User" in content
    assert "/api/users" in content
    assert "AUTO-GENERATED" in content


def test_capsule_highlights_breaking_changes(tmp_path):
    from upstreamiq.graph.models import (
        ChangeEvent, ChangeKind, ExtractedSurface, Link, LinkType, Repo, TypeDef,
    )
    from upstreamiq.generator.capsule import generate_capsule
    from datetime import datetime, timezone

    upstream = Repo(name="api-service", path=str(tmp_path / "api"), language="python")
    downstream = Repo(name="frontend", path=str(tmp_path / "frontend"), language="typescript")
    link = Link(downstream="frontend", upstream="api-service", link_type=LinkType.CALLS_REST)

    surface = ExtractedSurface(
        repo_name="api-service",
        commit_sha="def456",
        extracted_at=datetime.now(timezone.utc).isoformat(),
        exported_types=[TypeDef(name="User", definition="{ id: str; emails: list[str] }", file_path="models.py")],
        endpoints=[],
    )

    breaking = ChangeEvent(
        upstream_repo="api-service",
        commit_sha="def456",
        commit_message="refactor: User.email -> emails[]",
        committed_at=datetime.now(timezone.utc).isoformat(),
        kind=ChangeKind.BREAKING,
        affected_symbol="User",
        before="email: string",
        after="emails: string[]",
        affected_downstream=["frontend"],
    )

    content = generate_capsule(
        downstream_repo=downstream,
        upstream_links=[link],
        surfaces={"api-service": surface},
        recent_changes={"api-service": [breaking]},
    )

    assert "BREAKING" in content
    assert "email" in content
    assert "emails" in content


def test_task_planner_topological_order(graph_store):
    from upstreamiq.graph.models import Link, LinkType, Repo
    from upstreamiq.generator.task_planner import generate_task_plan

    repos = [
        Repo(name="shared-types", path="/tmp/shared-types", language="typescript"),
        Repo(name="api-service", path="/tmp/api-service", language="python"),
        Repo(name="frontend", path="/tmp/frontend", language="typescript"),
        Repo(name="mobile", path="/tmp/mobile", language="typescript"),
    ]
    links = [
        Link("api-service", "shared-types", LinkType.IMPORTS_TYPES),
        Link("frontend", "api-service", LinkType.CALLS_REST),
        Link("frontend", "shared-types", LinkType.IMPORTS_TYPES),
        Link("mobile", "api-service", LinkType.CALLS_REST),
        Link("mobile", "shared-types", LinkType.IMPORTS_TYPES),
    ]

    plan = generate_task_plan(
        task_description="add phone number to user profiles",
        all_repos=repos,
        all_links=links,
        surfaces={},
    )

    assert "shared-types" in plan
    assert "api-service" in plan
    assert "frontend" in plan

    shared_pos = plan.index("shared-types")
    api_pos = plan.index("api-service")
    frontend_pos = plan.index("frontend")
    assert shared_pos < api_pos < frontend_pos, "Wrong topological order"
