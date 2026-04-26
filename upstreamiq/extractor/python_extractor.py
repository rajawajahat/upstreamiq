"""Python extractor using the ast stdlib module."""
from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from pathlib import Path

from upstreamiq.graph.models import EndpointDef, ExtractedSurface, TypeDef

from .base import BaseExtractor

SKIP_PATTERNS = {"test_", "_test.py", "migration", "conftest", "__pycache__", "alembic"}

PYDANTIC_BASES = {"BaseModel", "Schema", "BaseSchema"}
DATACLASS_DECORATOR = "dataclass"


class PythonExtractor(BaseExtractor):

    def can_handle(self, repo_path: Path) -> bool:
        return (
            (repo_path / "requirements.txt").exists()
            or (repo_path / "pyproject.toml").exists()
        )

    def extract(self, repo_path: Path, commit_sha: str) -> ExtractedSurface:
        surface = ExtractedSurface(
            repo_name=repo_path.name,
            commit_sha=commit_sha,
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )
        for py_file in self._collect_py_files(repo_path):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                rel = str(py_file.relative_to(repo_path))
                tree = ast.parse(content, filename=str(py_file))
                surface.exported_types.extend(self._extract_models(tree, rel, content))
                surface.endpoints.extend(self._extract_routes(tree, rel))
            except SyntaxError:
                continue
            except Exception:
                continue
        return surface

    def _collect_py_files(self, root: Path) -> list[Path]:
        results = []
        for f in root.rglob("*.py"):
            parts = f.parts
            if any(skip in f.name for skip in SKIP_PATTERNS):
                continue
            if "__pycache__" in parts:
                continue
            results.append(f)
        return results

    def _extract_models(self, tree: ast.Module, file_path: str, source: str) -> list[TypeDef]:
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            is_pydantic = any(
                (isinstance(b, ast.Name) and b.id in PYDANTIC_BASES)
                or (isinstance(b, ast.Attribute) and b.attr in PYDANTIC_BASES)
                for b in node.bases
            )
            is_dataclass = any(
                (isinstance(d, ast.Name) and d.id == DATACLASS_DECORATOR)
                or (isinstance(d, ast.Attribute) and d.attr == DATACLASS_DECORATOR)
                for d in node.decorator_list
            )

            if not (is_pydantic or is_dataclass):
                continue

            fields = self._extract_fields(node)
            definition = self._build_definition(node.name, fields, is_pydantic)
            results.append(TypeDef(name=node.name, definition=definition, file_path=file_path))

        return results

    def _extract_fields(self, node: ast.ClassDef) -> list[str]:
        fields = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                try:
                    annotation = ast.unparse(item.annotation)
                    field_name = ast.unparse(item.target) if hasattr(ast, "unparse") else str(item.target)
                    if item.value:
                        default = ast.unparse(item.value)
                        fields.append(f"    {field_name}: {annotation} = {default}")
                    else:
                        fields.append(f"    {field_name}: {annotation}")
                except Exception:
                    continue
        return fields

    def _build_definition(self, name: str, fields: list[str], is_pydantic: bool) -> str:
        base = "BaseModel" if is_pydantic else ""
        header = f"class {name}({base}):" if base else f"class {name}:"
        if not fields:
            return f"{header}\n    pass"
        max_fields = 8
        lines = [header]
        if len(fields) > max_fields:
            lines.extend(fields[:max_fields])
            lines.append(f"    # ... {len(fields) - max_fields} more fields")
        else:
            lines.extend(fields)
        return "\n".join(lines)

    def _extract_routes(self, tree: ast.Module, file_path: str) -> list[EndpointDef]:
        results = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                endpoint = self._parse_route_decorator(decorator, node)
                if endpoint:
                    results.append(endpoint)
        return results

    def _parse_route_decorator(
        self, decorator: ast.expr, func: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> EndpointDef | None:
        # FastAPI/Flask: @app.get('/path'), @router.post('/path')
        if isinstance(decorator, ast.Call):
            func_node = decorator.func
            method = None
            path = None

            if isinstance(func_node, ast.Attribute):
                attr = func_node.attr.upper()
                if attr in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                    method = attr
                elif attr == "ROUTE":
                    # Flask @app.route('/path', methods=['GET'])
                    method = self._extract_flask_method(decorator)

            if method and decorator.args:
                try:
                    path_node = decorator.args[0]
                    if isinstance(path_node, ast.Constant):
                        path = str(path_node.value)
                except Exception:
                    pass

            if method and path:
                # Extract response type annotation if present
                response_schema = ""
                if func.returns:
                    try:
                        response_schema = ast.unparse(func.returns)
                    except Exception:
                        pass
                # Normalize path params: {user_id} → :user_id already OK in FastAPI style
                return EndpointDef(method=method, path=path, response_schema=response_schema)

        return None

    def _extract_flask_method(self, decorator: ast.Call) -> str | None:
        for kw in decorator.keywords:
            if kw.arg == "methods" and isinstance(kw.value, ast.List):
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Constant):
                        return str(elt.value).upper()
        return "GET"
