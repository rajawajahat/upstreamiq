"""TypeScript/JavaScript extractor using regex-based parsing."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from upstreamiq.graph.models import EndpointDef, ExtractedSurface, TypeDef

from .base import BaseExtractor

SKIP_DIRS = {
    "node_modules", ".next", "dist", "build", ".git", "__pycache__",
    "coverage", ".turbo", "out", ".vercel", ".cache", "vendor",
}

# Patterns
RE_EXPORTED_TYPE = re.compile(
    r"export\s+(?:interface|type)\s+(\w+)(?:<[^{]*>)?\s*[={]"
)
RE_EXPORTED_FUNC = re.compile(
    r"export\s+(?:async\s+)?function\s+(\w+)\s*(<[^(]*)?\("
)
RE_EXPORTED_CLASS = re.compile(
    r"export\s+(?:default\s+)?class\s+(\w+)"
)
RE_NEXTJS_ROUTE = re.compile(
    r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\s*\("
)
RE_EXPRESS_ROUTE = re.compile(
    r"(?:app|router|server)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"
)
RE_FETCH_CALL = re.compile(
    r"fetch\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*\{[^}]*method\s*:\s*['\"](\w+)['\"])?"
)
RE_AXIOS_CALL = re.compile(
    r"axios\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]"
)


class TypeScriptExtractor(BaseExtractor):

    def can_handle(self, repo_path: Path) -> bool:
        if not (repo_path / "package.json").exists():
            return False
        return any(True for _ in self._ts_files_iter(repo_path))

    def extract(self, repo_path: Path, commit_sha: str) -> ExtractedSurface:
        surface = ExtractedSurface(
            repo_name=repo_path.name,
            commit_sha=commit_sha,
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )
        for f in self._collect_ts_files(repo_path):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                rel = str(f.relative_to(repo_path))
                surface.exported_types.extend(self._extract_types(content, rel))
                surface.endpoints.extend(self._extract_endpoints(content, rel))
            except Exception:
                continue
        return surface

    def _ts_files_iter(self, root: Path):
        for pattern in ("*.ts", "*.tsx"):
            for f in root.rglob(pattern):
                if not any(skip in f.parts for skip in SKIP_DIRS):
                    yield f

    def _collect_ts_files(self, root: Path) -> list[Path]:
        return list(self._ts_files_iter(root))

    def _extract_types(self, content: str, file_path: str) -> list[TypeDef]:
        results = []
        for match in RE_EXPORTED_TYPE.finditer(content):
            name = match.group(1)
            start = match.start()
            definition = self._extract_block(content, start)
            if definition:
                compact = self._compact_definition(definition)
                results.append(TypeDef(name=name, definition=compact, file_path=file_path))
        return results

    def _extract_block(self, content: str, start: int) -> str:
        """Extract from 'export ...' to the matching closing brace."""
        # Find the opening brace
        brace_pos = content.find("{", start)
        if brace_pos == -1:
            # Might be a simple type alias: export type Foo = string | number
            line_end = content.find("\n", start)
            if line_end == -1:
                line_end = len(content)
            return content[start:line_end].strip()

        # Check if there's a '=' before '{' (type alias with object)
        between = content[start:brace_pos]
        if "=" not in between and "interface" not in between and "type" not in between:
            return ""

        # Brace counting to find the end
        depth = 0
        i = brace_pos
        while i < len(content):
            c = content[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return content[start : i + 1].strip()
            i += 1
        return content[start:].strip()

    def _compact_definition(self, definition: str) -> str:
        """Compact a multi-line type definition to max 10 lines."""
        lines = definition.splitlines()
        if len(lines) <= 10:
            return definition

        # Keep first line (export interface Foo {) and last line (})
        # Show up to 8 fields then truncate
        kept = [lines[0]]
        field_lines = [l for l in lines[1:-1] if l.strip()]
        max_fields = 8
        if len(field_lines) > max_fields:
            kept.extend(field_lines[:max_fields])
            kept.append(f"  // ... {len(field_lines) - max_fields} more fields")
        else:
            kept.extend(field_lines)
        kept.append(lines[-1])
        return "\n".join(kept)

    def _extract_endpoints(self, content: str, file_path: str) -> list[EndpointDef]:
        results = []

        # Next.js App Router handlers
        for match in RE_NEXTJS_ROUTE.finditer(content):
            method = match.group(1).upper()
            # Infer path from file path: app/api/users/route.ts → /api/users
            path = self._nextjs_path_from_file(file_path)
            if path:
                results.append(EndpointDef(method=method, path=path))

        # Express/Fastify routes
        for match in RE_EXPRESS_ROUTE.finditer(content):
            method = match.group(1).upper()
            path = match.group(2)
            results.append(EndpointDef(method=method, path=path))

        return results

    def _nextjs_path_from_file(self, file_path: str) -> str:
        """Convert Next.js route file path to API path."""
        # app/api/users/route.ts → /api/users
        # pages/api/users.ts → /api/users
        normalized = file_path.replace("\\", "/")
        if "app/" in normalized and "route." in normalized:
            # Find 'app/' and take everything after, remove '/route.ts'
            after_app = normalized[normalized.find("app/") + 4:]
            path = "/" + after_app.rsplit("/route.", 1)[0]
            # Replace [param] with :param
            path = re.sub(r"\[([^\]]+)\]", r":\1", path)
            return path
        if "pages/api/" in normalized:
            after = normalized[normalized.find("pages/api/") + 10:]
            path = "/api/" + re.sub(r"\[([^\]]+)\]", r":\1", after.rsplit(".", 1)[0])
            return path
        return ""
