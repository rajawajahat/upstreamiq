def test_add_and_get_repo(graph_store):
    from upstreamiq.graph.models import Repo
    repo = Repo(name="test-repo", path="/tmp/test", language="typescript")
    graph_store.add_repo(repo)
    fetched = graph_store.get_repo("test-repo")
    assert fetched is not None
    assert fetched.name == "test-repo"
    assert fetched.language == "typescript"


def test_add_and_query_link(graph_store):
    from upstreamiq.graph.models import Link, LinkType, Repo
    graph_store.add_repo(Repo(name="upstream", path="/tmp/up", language="python"))
    graph_store.add_repo(Repo(name="downstream", path="/tmp/down", language="typescript"))
    link = Link(downstream="downstream", upstream="upstream", link_type=LinkType.CALLS_REST)
    graph_store.add_link(link)

    links = graph_store.get_links_for_downstream("downstream")
    assert len(links) == 1
    assert links[0].upstream == "upstream"

    upstream_links = graph_store.get_links_for_upstream("upstream")
    assert len(upstream_links) == 1


def test_record_and_fetch_change(graph_store):
    from upstreamiq.graph.models import ChangeEvent, ChangeKind
    from datetime import datetime, timezone
    event = ChangeEvent(
        upstream_repo="api-service",
        commit_sha="abc123",
        commit_message="breaking change",
        committed_at=datetime.now(timezone.utc).isoformat(),
        kind=ChangeKind.BREAKING,
        affected_symbol="User",
        before="email: string",
        after="emails: string[]",
    )
    graph_store.record_change(event)
    changes = graph_store.get_recent_changes("api-service")
    assert len(changes) == 1
    assert changes[0].kind == ChangeKind.BREAKING


def test_list_repos_empty(graph_store):
    repos = graph_store.list_repos()
    assert repos == []


def test_remove_repo_removes_links(graph_store):
    from upstreamiq.graph.models import Link, LinkType, Repo
    graph_store.add_repo(Repo(name="up", path="/tmp/up", language="python"))
    graph_store.add_repo(Repo(name="down", path="/tmp/down", language="typescript"))
    graph_store.add_link(Link(downstream="down", upstream="up", link_type=LinkType.CALLS_REST))

    graph_store.remove_repo("up")
    assert graph_store.get_repo("up") is None
    links = graph_store.get_links_for_downstream("down")
    assert links == []


def test_surface_save_and_load(graph_store, tmp_path):
    from upstreamiq.graph.models import EndpointDef, ExtractedSurface, TypeDef
    from datetime import datetime, timezone

    surface = ExtractedSurface(
        repo_name="my-api",
        commit_sha="abc123",
        extracted_at=datetime.now(timezone.utc).isoformat(),
        exported_types=[TypeDef(name="User", definition="{ id: string }", file_path="types.ts")],
        endpoints=[EndpointDef(method="GET", path="/api/users", response_schema="User[]")],
    )
    graph_store.save_surface(surface)
    loaded = graph_store.get_surface("my-api")
    assert loaded is not None
    assert loaded.repo_name == "my-api"
    assert len(loaded.exported_types) == 1
    assert loaded.exported_types[0].name == "User"
    assert len(loaded.endpoints) == 1
    assert loaded.endpoints[0].path == "/api/users"
