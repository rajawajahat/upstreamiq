"""Background watch loop that polls git repos for new commits."""
from __future__ import annotations

import time
from pathlib import Path

from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from upstreamiq.extractor import ExtractorRegistry
from upstreamiq.generator.capsule import generate_capsule
from upstreamiq.graph.store import GraphStore
from upstreamiq.utils.console import console
from upstreamiq.watcher.change_analyzer import analyze_diff
from upstreamiq.watcher.git_watcher import GitWatcher


def run_watch_loop(interval: int = 30, once: bool = False) -> None:
    store = GraphStore()
    watcher = GitWatcher()
    registry = ExtractorRegistry()

    repos = store.list_repos()
    if not repos:
        console.print("[yellow]⚠[/yellow] No repos registered. Run: repolink add NAME PATH")
        store.close()
        return

    # Track last known SHA per repo
    last_shas: dict[str, str] = {}
    for repo in repos:
        sha, _, _ = watcher.get_latest_commit(repo.abs_path)
        last_shas[repo.name] = sha

    console.print(
        Panel(
            f"[bold]RepoLink — Watch Mode[/bold]\n"
            f"Watching [cyan]{len(repos)}[/cyan] repos | Interval: {interval}s\n"
            "[dim]Ctrl+C to stop[/dim]",
            border_style="blue",
        )
    )

    if once:
        _check_cycle(store, watcher, registry, repos, last_shas)
        store.close()
        return

    try:
        while True:
            check_time = time.strftime("%H:%M:%S")
            _check_cycle(store, watcher, registry, repos, last_shas)
            console.print(f"[dim]Checked at {check_time} — sleeping {interval}s[/dim]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")
    finally:
        store.close()


def _check_cycle(
    store: GraphStore,
    watcher: GitWatcher,
    registry: ExtractorRegistry,
    repos,
    last_shas: dict[str, str],
) -> None:
    all_links = store.list_links()
    repo_map = {r.name: r for r in repos}
    downstream_names = {l.downstream for l in all_links}

    for repo in repos:
        try:
            sha, msg, ts = watcher.get_latest_commit(repo.abs_path)
        except Exception:
            continue

        if sha == last_shas.get(repo.name):
            continue

        console.print(f"\n[yellow]⚡[/yellow] [bold]{repo.name}[/bold] changed (commit {sha}: {msg[:60]})")

        # Re-extract
        old_surface = store.get_surface(repo.name)
        new_surface = registry.extract(repo.abs_path)
        new_surface.repo_name = repo.name
        store.save_surface(new_surface)

        # Detect changes
        if old_surface:
            downstream_of_this = [l.downstream for l in all_links if l.upstream == repo.name]
            changes = analyze_diff(
                old_surface=old_surface,
                new_surface=new_surface,
                commit_sha=sha,
                commit_message=msg,
                affected_downstream=downstream_of_this,
            )
            for change in changes:
                store.record_change(change)
                kind_label = f"[red bold]{change.kind.value.upper()}[/red bold]" if change.kind.value == "breaking" else f"[green]{change.kind.value}[/green]"
                console.print(f"   Detected: {kind_label} change in [bold]{change.affected_symbol}[/bold]")
                if change.before and change.after:
                    console.print(f"     Before: {change.before}")
                    console.print(f"     After:  {change.after}")

        # Re-sync all downstreams that depend on this upstream
        for link in all_links:
            if link.upstream != repo.name:
                continue
            down_repo = repo_map.get(link.downstream)
            if not down_repo:
                continue
            upstream_links = [l for l in all_links if l.downstream == link.downstream]
            surfaces = {}
            for ul in upstream_links:
                s = store.get_surface(ul.upstream)
                if s:
                    surfaces[ul.upstream] = s
            recent_changes = {}
            for ul in upstream_links:
                ch = store.get_recent_changes(ul.upstream, limit=10)
                if ch:
                    recent_changes[ul.upstream] = ch
            content = generate_capsule(
                downstream_repo=down_repo,
                upstream_links=upstream_links,
                surfaces=surfaces,
                recent_changes=recent_changes,
            )
            down_repo.claude_upstream_path.write_text(content, encoding="utf-8")
            console.print(f"   [green]✓[/green] {link.downstream}/CLAUDE.upstream.md updated")

        last_shas[repo.name] = sha
