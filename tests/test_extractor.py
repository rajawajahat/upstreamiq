def test_typescript_extractor_finds_interfaces(tmp_ts_repo):
    from upstreamiq.extractor.typescript import TypeScriptExtractor
    extractor = TypeScriptExtractor()
    assert extractor.can_handle(tmp_ts_repo)
    surface = extractor.extract(tmp_ts_repo, "test123")
    type_names = [t.name for t in surface.exported_types]
    assert "User" in type_names
    assert "AuthToken" in type_names
    assert "ApiResponse" in type_names


def test_typescript_extractor_finds_routes(tmp_ts_repo):
    from upstreamiq.extractor.typescript import TypeScriptExtractor
    extractor = TypeScriptExtractor()
    surface = extractor.extract(tmp_ts_repo, "test123")
    paths = [e.path for e in surface.endpoints]
    assert "/api/users" in paths
    assert "/api/users/:id" in paths
    methods = [e.method.upper() for e in surface.endpoints]
    assert "GET" in methods
    assert "POST" in methods


def test_python_extractor_finds_pydantic_models(tmp_python_repo):
    from upstreamiq.extractor.python_extractor import PythonExtractor
    extractor = PythonExtractor()
    assert extractor.can_handle(tmp_python_repo)
    surface = extractor.extract(tmp_python_repo, "test456")
    type_names = [t.name for t in surface.exported_types]
    assert "User" in type_names
    assert "CreateUserRequest" in type_names


def test_python_extractor_finds_fastapi_routes(tmp_python_repo):
    from upstreamiq.extractor.python_extractor import PythonExtractor
    extractor = PythonExtractor()
    surface = extractor.extract(tmp_python_repo, "test456")
    paths = [e.path for e in surface.endpoints]
    assert "/api/users/{user_id}" in paths or "/api/users/:user_id" in paths
    assert "/api/users" in paths


def test_openapi_extractor_finds_endpoints(tmp_openapi_repo):
    from upstreamiq.extractor.openapi import OpenAPIExtractor
    extractor = OpenAPIExtractor()
    assert extractor.can_handle(tmp_openapi_repo)
    surface = extractor.extract(tmp_openapi_repo, "test789")
    assert len(surface.endpoints) >= 2
    assert len(surface.exported_types) >= 2


def test_extractor_registry_uses_openapi_first(tmp_openapi_repo):
    from upstreamiq.extractor import ExtractorRegistry
    registry = ExtractorRegistry()
    surface = registry.extract(tmp_openapi_repo)
    assert surface.repo_name == tmp_openapi_repo.name
    assert len(surface.endpoints) > 0


def test_type_definition_is_compact(tmp_ts_repo):
    from upstreamiq.extractor.typescript import TypeScriptExtractor
    extractor = TypeScriptExtractor()
    surface = extractor.extract(tmp_ts_repo, "abc")
    for t in surface.exported_types:
        lines = t.definition.split("\n")
        assert len(lines) <= 12, f"Type {t.name} definition too long: {len(lines)} lines"
