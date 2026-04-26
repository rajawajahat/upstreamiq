"""Generic fallback extractor for any repo language."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from upstreamiq.graph.models import EndpointDef, ExtractedSurface, TypeDef

from .base import BaseExtractor

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".pdf", ".zip", ".tar", ".gz", ".lock", ".min.js",
}

RE_URL_PATTERN = re.compile(
    r"""[\"'`]((?:/api|/v\d+|/graphql)[^\"'`?\s]{0,80})[\"'`]"""
)
RE_HTTP_METHOD = re.compile(
    r"\b(GET|POST|PUT|DELETE|PATCH)\b", re.IGNORECASE
)

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "dist", "build",
    ".next", "vendor", "coverage",
}

TEXT_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".rb",
    ".java", ".kt", ".swift", ".cs", ".php", ".sh", ".yaml", ".yml",
    ".json", ".toml", ".md", ".txt", ".graphql", ".proto",
}


class GenericExtractor(BaseExtractor):

    def can_handle(self, repo_path: Path) -> bool:
        return True  # Always handles as fallback

    def extract(self, repo_path: Path, commit_sha: str) -> ExtractedSurface:
        surface = ExtractedSurface(
            repo_name=repo_path.name,
            commit_sha=commit_sha,
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )

        # Scan for URL patterns
        endpoints = self._scan_url_patterns(repo_path)
        surface.endpoints.extend(endpoints)

        # Scan README for API docs
        readme_conventions = self._scan_readme(repo_path)
        surface.consumer_conventions.extend(readme_conventions)

        # Scan .proto files
        proto_types = self._scan_proto_files(repo_path)
        surface.exported_types.extend(proto_types)

        # Scan .graphql files
        graphql_types = self._scan_graphql_files(repo_path)
        surface.exported_types.extend(graphql_types)

        return surface

    def _scan_url_patterns(self, repo_path: Path) -> list[EndpointDef]:
        found: dict[tuple, EndpointDef] = {}
        for f in repo_path.rglob("*"):
            if not f.is_file():
                continue
            if any(skip in f.parts for skip in SKIP_DIRS):
                continue
            if f.suffix not in TEXT_EXTENSIONS:
                continue
            if f.stat().st_size > 200_000:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for match in RE_URL_PATTERN.finditer(content):
                path = match.group(1)
                # Find method from surrounding 50 chars
                start = max(0, match.start() - 50)
                context = content[start : match.start() + 50]
                method_match = RE_HTTP_METHOD.search(context)
                method = method_match.group(1).upper() if method_match else "GET"
                key = (method, path)
                if key not in found:
                    found[key] = EndpointDef(method=method, path=path)

        return list(found.values())[:20]  # Limit to 20 generic endpoints

    def _scan_readme(self, repo_path: Path) -> list[str]:
        readme = repo_path / "README.md"
        if not readme.exists():
            return []
        try:
            content = readme.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        conventions = []
        # Find sections mentioning API, conventions, notes
        lines = content.splitlines()
        in_api_section = False
        for line in lines:
            lower = line.lower()
            if line.startswith("#") and any(
                kw in lower for kw in ("api", "endpoint", "convention", "note", "usage")
            ):
                in_api_section = True
                continue
            if line.startswith("#") and in_api_section:
                in_api_section = False
            if in_api_section and line.strip().startswith("-"):
                note = line.strip().lstrip("-").strip()
                if note and len(note) < 200:
                    conventions.append(note)
            if len(conventions) >= 5:
                break

        return conventions

    def _scan_proto_files(self, repo_path: Path) -> list[TypeDef]:
        results = []
        for f in repo_path.rglob("*.proto"):
            if any(skip in f.parts for skip in SKIP_DIRS):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                rel = str(f.relative_to(repo_path))
                # Extract message definitions
                for match in re.finditer(r"message\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL):
                    name = match.group(1)
                    body = match.group(0).strip()
                    results.append(TypeDef(name=name, definition=body, file_path=rel))
            except Exception:
                continue
        return results

    def _scan_graphql_files(self, repo_path: Path) -> list[TypeDef]:
        results = []
        for f in repo_path.rglob("*.graphql"):
            if any(skip in f.parts for skip in SKIP_DIRS):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                rel = str(f.relative_to(repo_path))
                for match in re.finditer(r"type\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL):
                    name = match.group(1)
                    if name in ("Query", "Mutation", "Subscription"):
                        continue
                    body = match.group(0).strip()
                    results.append(TypeDef(name=name, definition=body, file_path=rel))
            except Exception:
                continue
        return results
