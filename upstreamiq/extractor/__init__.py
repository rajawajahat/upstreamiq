"""ExtractorRegistry: tries each extractor in priority order, merges results."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from upstreamiq.graph.models import EndpointDef, ExtractedSurface, TypeDef

from .base import BaseExtractor
from .generic import GenericExtractor
from .openapi import OpenAPIExtractor
from .python_extractor import PythonExtractor
from .typescript import TypeScriptExtractor


class ExtractorRegistry:
    def __init__(self):
        self._extractors: list[BaseExtractor] = [
            OpenAPIExtractor(),
            TypeScriptExtractor(),
            PythonExtractor(),
            GenericExtractor(),
        ]

    def extract(self, repo_path: Path) -> ExtractedSurface:
        merged = ExtractedSurface(
            repo_name=repo_path.name,
            commit_sha=self._get_sha(repo_path),
            extracted_at=datetime.now(timezone.utc).isoformat(),
        )

        has_openapi_endpoints = False

        for extractor in self._extractors:
            if not extractor.can_handle(repo_path):
                continue
            try:
                surface = extractor.extract(repo_path, merged.commit_sha)
            except Exception:
                continue

            # OpenAPI is highest quality for endpoints
            if isinstance(extractor, OpenAPIExtractor) and surface.endpoints:
                has_openapi_endpoints = True
                merged.endpoints = _merge_endpoints(merged.endpoints, surface.endpoints)
            elif isinstance(extractor, (TypeScriptExtractor, PythonExtractor)):
                merged.exported_types = _merge_types(merged.exported_types, surface.exported_types)
                if not has_openapi_endpoints:
                    merged.endpoints = _merge_endpoints(merged.endpoints, surface.endpoints)
                merged.package_exports.extend(surface.package_exports)
            elif isinstance(extractor, GenericExtractor):
                # Generic always merges as fallback
                merged.exported_types = _merge_types(merged.exported_types, surface.exported_types)
                if not has_openapi_endpoints:
                    merged.endpoints = _merge_endpoints(merged.endpoints, surface.endpoints)

            # Merge conventions
            for conv in surface.consumer_conventions:
                if conv not in merged.consumer_conventions:
                    merged.consumer_conventions.append(conv)

        return merged

    def _get_sha(self, repo_path: Path) -> str:
        try:
            import git
            repo = git.Repo(repo_path, search_parent_directories=True)
            return repo.head.commit.hexsha[:12]
        except Exception:
            return "unknown"


def _merge_types(existing: list[TypeDef], new: list[TypeDef]) -> list[TypeDef]:
    existing_names = {t.name for t in existing}
    result = list(existing)
    for t in new:
        if t.name not in existing_names:
            result.append(t)
            existing_names.add(t.name)
    return result


def _merge_endpoints(existing: list[EndpointDef], new: list[EndpointDef]) -> list[EndpointDef]:
    existing_keys = {(e.method.upper(), e.path) for e in existing}
    result = list(existing)
    for e in new:
        key = (e.method.upper(), e.path)
        if key not in existing_keys:
            result.append(e)
            existing_keys.add(key)
    return result
