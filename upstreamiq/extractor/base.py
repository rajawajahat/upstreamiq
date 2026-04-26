from abc import ABC, abstractmethod
from pathlib import Path

from upstreamiq.graph.models import ExtractedSurface


class BaseExtractor(ABC):
    """Extracts the public API surface from a repository."""

    @abstractmethod
    def can_handle(self, repo_path: Path) -> bool:
        """Return True if this extractor applies to the given repo."""
        ...

    @abstractmethod
    def extract(self, repo_path: Path, commit_sha: str) -> ExtractedSurface:
        """Extract the public interface from the repo. Never raise."""
        ...

    def _get_commit_sha(self, repo_path: Path) -> str:
        try:
            import git
            repo = git.Repo(repo_path, search_parent_directories=True)
            return repo.head.commit.hexsha[:12]
        except Exception:
            return "unknown"
