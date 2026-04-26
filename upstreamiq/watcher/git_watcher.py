"""Polls git repos for new commits."""
from __future__ import annotations

from pathlib import Path


class GitWatcher:

    def get_latest_commit(self, repo_path: Path) -> tuple[str, str, str]:
        """Returns (sha, message, iso_timestamp) for HEAD commit."""
        import git
        try:
            repo = git.Repo(repo_path, search_parent_directories=True)
            commit = repo.head.commit
            return (
                commit.hexsha[:12],
                commit.message.strip().split("\n")[0],
                commit.committed_datetime.isoformat(),
            )
        except Exception:
            return ("unknown", "", "")

    def get_commits_since(self, repo_path: Path, since_sha: str) -> list[tuple[str, str, str]]:
        """Returns list of (sha, message, timestamp) for commits after since_sha."""
        import git
        try:
            repo = git.Repo(repo_path, search_parent_directories=True)
            commits = []
            for commit in repo.iter_commits("HEAD", max_count=50):
                if commit.hexsha[:12] == since_sha or commit.hexsha == since_sha:
                    break
                commits.append((
                    commit.hexsha[:12],
                    commit.message.strip().split("\n")[0],
                    commit.committed_datetime.isoformat(),
                ))
            return commits
        except Exception:
            return []

    def get_diff_for_commit(self, repo_path: Path, commit_sha: str) -> str:
        """Returns unified diff string for a single commit."""
        import git
        try:
            repo = git.Repo(repo_path, search_parent_directories=True)
            commit = repo.commit(commit_sha)
            if not commit.parents:
                return ""
            parent = commit.parents[0]
            diff = parent.diff(commit, create_patch=True)
            return "\n".join(
                d.diff.decode("utf-8", errors="ignore") for d in diff
            )
        except Exception:
            return ""
