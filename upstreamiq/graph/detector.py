"""Auto-detect dependency relationships between repos."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Link, LinkType, Repo


def detect_relationships(repos: list[Repo]) -> list[Link]:
    """
    Heuristically detect dependency relationships between repos.
    Returns suggested links (not auto-applied).
    """
    suggestions: list[Link] = []
    seen: set[tuple[str, str]] = set()

    for repo in repos:
        for other in repos:
            if repo.name == other.name:
                continue
            if (repo.name, other.name) in seen:
                continue

            link = _detect_link(repo, other, repos)
            if link:
                suggestions.append(link)
                seen.add((link.downstream, link.upstream))

    return suggestions


def _detect_link(downstream: Repo, upstream: Repo, all_repos: list[Repo]) -> Link | None:
    """Check if downstream depends on upstream."""
    # 1. package.json dependency check
    pkg_json = downstream.abs_path / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            all_deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }
            for dep_name in all_deps:
                if upstream.name in dep_name or dep_name in upstream.name:
                    return Link(
                        downstream=downstream.name,
                        upstream=upstream.name,
                        link_type=LinkType.RUNS_PACKAGE,
                        description=f"package.json dependency: {dep_name}",
                    )
        except Exception:
            pass

    # 2. HTTP call scan — look for URL patterns matching upstream name
    upstream_slug = upstream.name.lower().replace("-", "[-_]?").replace("_", "[-_]?")
    pattern = re.compile(upstream_slug, re.IGNORECASE)

    source_exts = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".rb"}
    skip_dirs = {"node_modules", ".git", "__pycache__", "dist", "build"}

    for f in downstream.abs_path.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in source_exts:
            continue
        if any(skip in f.parts for skip in skip_dirs):
            continue
        if f.stat().st_size > 100_000:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(content):
                # Check if it's in a fetch/HTTP call context
                if re.search(r"(fetch|axios|requests?|http|url|endpoint)", content, re.IGNORECASE):
                    return Link(
                        downstream=downstream.name,
                        upstream=upstream.name,
                        link_type=LinkType.CALLS_REST,
                        description=f"HTTP call detected in {f.name}",
                    )
        except Exception:
            continue

    return None
