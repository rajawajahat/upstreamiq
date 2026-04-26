"""File system helpers."""
from __future__ import annotations

from pathlib import Path


def detect_language(repo_path: Path) -> str:
    """Detect the primary language of a repository."""
    if (repo_path / "package.json").exists():
        # Check for TypeScript
        if any(repo_path.rglob("*.ts")) or (repo_path / "tsconfig.json").exists():
            return "typescript"
        return "javascript"
    if (repo_path / "go.mod").exists():
        return "go"
    if (repo_path / "Cargo.toml").exists():
        return "rust"
    if (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
        return "python"
    if (repo_path / "Gemfile").exists():
        return "ruby"
    if (repo_path / "pom.xml").exists() or (repo_path / "build.gradle").exists():
        return "java"
    return "unknown"


def detect_api_spec(repo_path: Path) -> str:
    """Detect an OpenAPI spec file relative to repo root."""
    candidates = [
        "openapi.yaml", "openapi.yml", "openapi.json",
        "swagger.yaml", "swagger.yml", "swagger.json",
        "api.yaml", "api.json", "schema.yaml",
    ]
    for name in candidates:
        if (repo_path / name).exists():
            return name
    for subdir in ["docs", "api", "spec"]:
        for name in candidates:
            if (repo_path / subdir / name).exists():
                return f"{subdir}/{name}"
    return ""


def relative_time(iso_timestamp: str) -> str:
    """Convert ISO timestamp to human-readable relative time."""
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt.astimezone(timezone.utc)
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds} seconds ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = hours // 24
        if days < 30:
            return f"{days} day{'s' if days != 1 else ''} ago"
        weeks = days // 7
        if weeks < 8:
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    except Exception:
        return iso_timestamp
