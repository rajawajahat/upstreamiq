"""OpenAPI/Swagger extractor."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from upstreamiq.graph.models import EndpointDef, ExtractedSurface, TypeDef

from .base import BaseExtractor

SPEC_FILENAMES = {
    "openapi.yaml", "openapi.json", "openapi.yml",
    "swagger.yaml", "swagger.json", "swagger.yml",
    "api.yaml", "api.json", "schema.yaml",
}


class OpenAPIExtractor(BaseExtractor):

    def can_handle(self, repo_path: Path) -> bool:
        return bool(self._find_spec(repo_path))

    def extract(self, repo_path: Path, commit_sha: str) -> ExtractedSurface:
        surface = ExtractedSurface(
            repo_name=repo_path.name,
            commit_sha=commit_sha,
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )
        spec_path = self._find_spec(repo_path)
        if not spec_path:
            return surface

        try:
            spec = self._load_spec(spec_path)
        except Exception:
            return surface

        # Resolve internal $refs
        schemas = self._get_schemas(spec)

        # Extract endpoints from paths
        for path, path_item in spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
                    continue
                if not isinstance(operation, dict):
                    continue

                request_schema = self._extract_request_schema(operation, schemas)
                response_schema = self._extract_response_schema(operation, schemas)
                description = operation.get("summary", operation.get("description", ""))

                surface.endpoints.append(EndpointDef(
                    method=method.upper(),
                    path=path,
                    request_schema=request_schema,
                    response_schema=response_schema,
                    description=description[:100] if description else "",
                ))

        # Extract schema definitions
        for name, schema_def in schemas.items():
            if not isinstance(schema_def, dict):
                continue
            definition = self._schema_to_definition(name, schema_def, schemas)
            surface.exported_types.append(TypeDef(
                name=name,
                definition=definition,
                file_path=str(spec_path.relative_to(repo_path)),
            ))

        return surface

    def _find_spec(self, repo_path: Path) -> Path | None:
        for name in SPEC_FILENAMES:
            if (repo_path / name).exists():
                return repo_path / name
        for subdir in ["docs", "api", "spec"]:
            for name in SPEC_FILENAMES:
                p = repo_path / subdir / name
                if p.exists():
                    return p
        return None

    def _load_spec(self, path: Path) -> dict:
        content = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            return yaml.safe_load(content) or {}
        return json.loads(content)

    def _get_schemas(self, spec: dict) -> dict:
        # OpenAPI 3.x
        components = spec.get("components", {})
        if components:
            return components.get("schemas", {})
        # Swagger 2.x
        return spec.get("definitions", {})

    def _resolve_ref(self, ref: str, schemas: dict) -> dict | None:
        """Resolve a simple local $ref like '#/components/schemas/User'."""
        if not ref.startswith("#"):
            return None
        parts = ref.lstrip("#/").split("/")
        # parts e.g.: ['components', 'schemas', 'User'] or ['definitions', 'User']
        if len(parts) >= 2:
            name = parts[-1]
            return schemas.get(name)
        return None

    def _extract_request_schema(self, operation: dict, schemas: dict) -> str:
        body = operation.get("requestBody", {})
        if not body:
            return ""
        content = body.get("content", {})
        for mime_type in ("application/json", "application/x-www-form-urlencoded"):
            schema = content.get(mime_type, {}).get("schema", {})
            if schema:
                return self._schema_ref_name(schema)
        return ""

    def _extract_response_schema(self, operation: dict, schemas: dict) -> str:
        responses = operation.get("responses", {})
        for code in ("200", "201", "default"):
            resp = responses.get(code, {})
            if not resp:
                continue
            content = resp.get("content", {})
            schema = content.get("application/json", {}).get("schema", {})
            if schema:
                return self._schema_ref_name(schema)
        return ""

    def _schema_ref_name(self, schema: dict) -> str:
        if "$ref" in schema:
            return schema["$ref"].split("/")[-1]
        schema_type = schema.get("type", "")
        if schema_type == "array":
            items = schema.get("items", {})
            item_name = items.get("$ref", "").split("/")[-1] if "$ref" in items else items.get("type", "object")
            return f"{item_name}[]"
        return schema_type or "object"

    def _schema_to_definition(self, name: str, schema: dict, schemas: dict) -> str:
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines = [f"type {name} = {{"]
        prop_items = list(props.items())
        max_props = 8
        shown = prop_items[:max_props]
        for prop_name, prop_schema in shown:
            prop_type = self._prop_type(prop_schema)
            optional = "" if prop_name in required else "?"
            lines.append(f"  {prop_name}{optional}: {prop_type};")
        if len(prop_items) > max_props:
            lines.append(f"  // ... {len(prop_items) - max_props} more properties")
        lines.append("}")
        return "\n".join(lines)

    def _prop_type(self, schema: dict) -> str:
        if "$ref" in schema:
            return schema["$ref"].split("/")[-1]
        t = schema.get("type", "")
        fmt = schema.get("format", "")
        if t == "string":
            return fmt if fmt in ("date", "date-time", "uuid") else "string"
        if t == "integer":
            return "number"
        if t == "number":
            return "number"
        if t == "boolean":
            return "boolean"
        if t == "array":
            items = schema.get("items", {})
            return self._prop_type(items) + "[]"
        if t == "object":
            return "object"
        return t or "unknown"
