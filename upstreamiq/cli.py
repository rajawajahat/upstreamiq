"""RepoLink CLI — all Typer commands."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from upstreamiq import version
from upstreamiq.graph.models import Link, LinkType, Repo
from upstreamiq.graph.store import GraphStore
from upstreamiq.utils.console import console
from upstreamiq.utils.fs import detect_api_spec, detect_language, relative_time

app = typer.Typer(
    name="repolink",
    help="Cross-repo context bridge for AI coding agents.",
    add_completion=False,
)


def _get_store() -> GraphStore:
    return GraphStore()


# ── repolink version ──────────────────────────────────────────────────────────

@app.command("version")
def cmd_version():
    """Show version + Python version + registered repo count."""
    store = _get_store()
    repos = store.list_repos()
    store.close()
    console.print(
        f"[bold]repolink[/bold] v{version}  "
        f"Python {sys.version.split()[0]}  "
        f"[dim]{len(repos)} repo{'s' if len(repos) != 1 else ''} registered[/dim]"
    )


# ── repolink add ──────────────────────────────────────────────────────────────

@app.command("add")
def cmd_add(
    name: str = typer.Argument(..., help="Repo name, e.g. 'api-service'"),
    path: str = typer.Argument(..., help="Absolute or relative path to the repo"),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Language override"),
    desc: Optional[str] = typer.Option("", "--desc", "-d", help="Short description"),
):
    """Register a single repo with RepoLink."""
    abs_path = Path(path).expanduser().resolve()
    if not abs_path.exists():
        console.print(f"[red]✗ Path does not exist:[/red] {abs_path}")
        raise typer.Exit(1)

    language = lang or detect_language(abs_path)
    api_spec = detect_api_spec(abs_path)

    store = _get_store()
    existing = store.get_repo(name)
    if existing:
        console.print(f"[yellow]⚠[/yellow] Repo [bold]{name}[/bold] already registered — updating.")

    repo = Repo(
        name=name,
        path=str(abs_path),
        language=language,
        description=desc or "",
        api_spec_path=api_spec,
    )
    store.add_repo(repo)
    store.close()

    spec_note = f"  [dim](API spec: {api_spec})[/dim]" if api_spec else ""
    console.print(
        f"[green]✓[/green] Registered: [bold]{name}[/bold] "
        f"([cyan]{language}[/cyan]) at [dim]{abs_path}[/dim]{spec_note}"
    )


# ── repolink remove ───────────────────────────────────────────────────────────

@app.command("remove")
def cmd_remove(
    name: str = typer.Argument(..., help="Repo name to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Unregister a repo and remove all its links."""
    store = _get_store()
    repo = store.get_repo(name)
    if not repo:
        console.print(f"[red]✗ Repo not found:[/red] {name}")
        store.close()
        raise typer.Exit(1)

    if not yes:
        confirm = typer.confirm(f"Remove '{name}' and all its links?")
        if not confirm:
            console.print("[dim]Aborted.[/dim]")
            store.close()
            return

    store.remove_repo(name)
    store.close()
    console.print(f"[green]✓[/green] Removed: [bold]{name}[/bold] (and all its links)")


# ── repolink link ─────────────────────────────────────────────────────────────

@app.command("link")
def cmd_link(
    downstream: str = typer.Argument(..., help="Downstream repo (the consumer)"),
    consumes: str = typer.Option(..., "--consumes", help="Upstream repo being consumed"),
    link_type: Optional[str] = typer.Option(
        None, "--type", "-t",
        help="Link type: imports_types | calls_rest | calls_grpc | runs_package | shares_schema"
    ),
    desc: str = typer.Option("", "--desc", "-d", help="Optional description"),
):
    """Define a dependency: DOWNSTREAM consumes UPSTREAM."""
    store = _get_store()

    down_repo = store.get_repo(downstream)
    up_repo = store.get_repo(consumes)

    if not down_repo:
        console.print(f"[red]✗ Downstream repo not found:[/red] {downstream}")
        store.close()
        raise typer.Exit(1)
    if not up_repo:
        console.print(f"[red]✗ Upstream repo not found:[/red] {consumes}")
        store.close()
        raise typer.Exit(1)

    # Auto-detect link type if not specified
    if link_type:
        try:
            lt = LinkType(link_type)
        except ValueError:
            console.print(f"[red]✗ Invalid link type:[/red] {link_type}")
            console.print(f"  Valid types: {', '.join(t.value for t in LinkType)}")
            store.close()
            raise typer.Exit(1)
    else:
        lt = _infer_link_type(down_repo.language, up_repo.language)

    link = Link(downstream=downstream, upstream=consumes, link_type=lt, description=desc)
    store.add_link(link)
    store.close()
    console.print(f"[green]✓[/green] Linked: [bold]{downstream}[/bold] → [bold]{consumes}[/bold] ([cyan]{lt.value}[/cyan])")


def _infer_link_type(downstream_lang: str, upstream_lang: str) -> LinkType:
    """Infer link type from language combination."""
    if downstream_lang == upstream_lang and downstream_lang in ("typescript", "javascript"):
        return LinkType.IMPORTS_TYPES
    if downstream_lang in ("typescript", "javascript") and upstream_lang == "python":
        return LinkType.CALLS_REST
    if downstream_lang == "python" and upstream_lang == "python":
        return LinkType.IMPORTS_TYPES
    return LinkType.CALLS_REST


# ── repolink unlink ───────────────────────────────────────────────────────────

@app.command("unlink")
def cmd_unlink(
    downstream: str = typer.Argument(..., help="Downstream repo"),
    from_upstream: str = typer.Option(..., "--from", help="Upstream repo to unlink from"),
):
    """Remove a dependency relationship."""
    store = _get_store()
    store.remove_link(downstream, from_upstream)
    store.close()
    console.print(f"[green]✓[/green] Removed link: [bold]{downstream}[/bold] → [bold]{from_upstream}[/bold]")


# ── repolink list ─────────────────────────────────────────────────────────────

@app.command("list")
def cmd_list():
    """Show the current dependency graph."""
    store = _get_store()
    repos = store.list_repos()
    links = store.list_links()
    store.close()

    if not repos:
        console.print("[dim]No repos registered. Run:[/dim] repolink add NAME PATH")
        return

    # Repos table
    table = Table(header_style="bold cyan", title=f"Registered repos ({len(repos)})")
    table.add_column("Name", style="bold")
    table.add_column("Language", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("API Spec")

    for repo in repos:
        table.add_row(
            repo.name,
            repo.language,
            repo.path,
            "[green]Yes[/green]" if repo.api_spec_path else "[dim]No[/dim]",
        )
    console.print(table)

    if not links:
        console.print("\n[dim]No links defined. Run:[/dim] repolink link DOWNSTREAM --consumes UPSTREAM")
        return

    # Build adjacency: upstream → list of (downstream, link_type)
    upstream_map: dict[str, list[tuple[str, str]]] = {}
    for link in links:
        upstream_map.setdefault(link.upstream, []).append((link.downstream, link.link_type.value))

    # Build set of repos that have at least one upstream (they are downstreams)
    downstreams = {link.downstream for link in links}
    pure_upstreams = [r for r in repos if r.name in upstream_map]

    console.print()
    console.rule("[bold blue]Dependency graph[/bold blue]")

    if not pure_upstreams:
        console.print("[dim]No upstream repos with consumers defined.[/dim]")
        return

    for repo in pure_upstreams:
        tree = Tree(f"[bold]{repo.name}[/bold]")
        consumers = upstream_map.get(repo.name, [])
        for i, (downstream, lt) in enumerate(consumers):
            prefix = "└──" if i == len(consumers) - 1 else "├──"
            tree.add(f"consumed by: [cyan]{downstream}[/cyan] ([dim]{lt}[/dim])")
        console.print(tree)


# ── repolink init ─────────────────────────────────────────────────────────────

@app.command("init")
def cmd_init(
    path: str = typer.Argument(".", help="Directory to scan for git repos"),
    depth: int = typer.Option(2, "--depth", help="Directory depth to scan"),
):
    """Scan a directory and register all git repos found."""
    scan_path = Path(path).expanduser().resolve()
    if not scan_path.exists():
        console.print(f"[red]✗ Path does not exist:[/red] {scan_path}")
        raise typer.Exit(1)

    console.rule(f"[bold blue]Scanning {scan_path}[/bold blue]")

    # Find all .git directories up to depth levels
    found: list[Path] = []
    _find_git_repos(scan_path, found, current_depth=0, max_depth=depth)

    if not found:
        console.print(f"[yellow]⚠[/yellow] No git repos found in {scan_path} (depth={depth})")
        return

    store = _get_store()
    table = Table(header_style="bold cyan", title=f"Found {len(found)} repos")
    table.add_column("Name", style="bold")
    table.add_column("Path", style="dim")
    table.add_column("Language", style="cyan")
    table.add_column("API Spec")
    table.add_column("Status")

    for repo_path in found:
        name = repo_path.name
        language = detect_language(repo_path)
        api_spec = detect_api_spec(repo_path)
        existing = store.get_repo(name)
        if existing:
            status = "[dim](already registered)[/dim]"
        else:
            repo = Repo(name=name, path=str(repo_path), language=language, api_spec_path=api_spec)
            store.add_repo(repo)
            status = "[green]✓ registered[/green]"
        table.add_row(
            name, str(repo_path), language,
            "[green]Yes[/green]" if api_spec else "[dim]No[/dim]",
            status,
        )

    store.close()
    console.print(table)
    console.print("\n[dim]Run[/dim] [bold]repolink link[/bold] [dim]to define relationships between repos.[/dim]")


def _find_git_repos(path: Path, results: list[Path], current_depth: int, max_depth: int) -> None:
    if current_depth > max_depth:
        return
    if (path / ".git").exists():
        results.append(path)
        return  # Don't recurse into sub-repos
    if current_depth < max_depth:
        try:
            for child in sorted(path.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    _find_git_repos(child, results, current_depth + 1, max_depth)
        except PermissionError:
            pass


# ── repolink extract ──────────────────────────────────────────────────────────

@app.command("extract")
def cmd_extract(
    repo_name: Optional[str] = typer.Argument(None, help="Repo to extract (default: all)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show extracted items"),
    force: bool = typer.Option(False, "--force", "-f", help="Re-extract even if cache is fresh"),
):
    """Extract the API surface from one or all repos."""
    from upstreamiq.extractor import ExtractorRegistry

    store = _get_store()
    registry = ExtractorRegistry()

    if repo_name:
        repo = store.get_repo(repo_name)
        if not repo:
            console.print(f"[red]✗ Repo not found:[/red] {repo_name}")
            store.close()
            raise typer.Exit(1)
        repos_to_extract = [repo]
    else:
        repos_to_extract = store.list_repos()

    if not repos_to_extract:
        console.print("[dim]No repos registered.[/dim]")
        store.close()
        return

    from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    import time

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        for repo in repos_to_extract:
            task = progress.add_task(f"Extracting [bold]{repo.name}[/bold]...", total=None)
            t0 = time.time()
            try:
                surface = registry.extract(repo.abs_path)
                surface.repo_name = repo.name
                store.save_surface(surface)
                elapsed = time.time() - t0
                progress.update(task, description=f"[green]✓[/green] {repo.name}")
                console.print(
                    f"  [green]✓[/green] [bold]{repo.name}[/bold]: "
                    f"{len(surface.exported_types)} types, "
                    f"{len(surface.endpoints)} endpoints, "
                    f"{len(surface.package_exports)} exports "
                    f"([dim]{elapsed:.1f}s[/dim])"
                )
                if verbose:
                    for t in surface.exported_types:
                        console.print(f"    [dim]type[/dim] {t.name} [dim]({t.file_path})[/dim]")
                    for e in surface.endpoints:
                        console.print(f"    [dim]endpoint[/dim] {e.method} {e.path}")
            except Exception as exc:
                progress.update(task, description=f"[red]✗[/red] {repo.name}")
                console.print(f"  [red]✗[/red] [bold]{repo.name}[/bold]: {exc}")

    store.close()


# ── repolink sync ─────────────────────────────────────────────────────────────

@app.command("sync")
def cmd_sync(
    repo_name: Optional[str] = typer.Argument(None, help="Downstream repo to sync (default: all)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show output without writing files"),
):
    """Generate/update CLAUDE.upstream.md for downstream repos."""
    from upstreamiq.extractor import ExtractorRegistry
    from upstreamiq.generator.capsule import generate_capsule

    store = _get_store()
    registry = ExtractorRegistry()

    all_repos = {r.name: r for r in store.list_repos()}
    all_links = store.list_links()

    # Find downstream repos (repos that have at least one upstream link)
    downstream_names = {link.downstream for link in all_links}

    if repo_name:
        if repo_name not in all_repos:
            console.print(f"[red]✗ Repo not found:[/red] {repo_name}")
            store.close()
            raise typer.Exit(1)
        targets = [repo_name] if repo_name in downstream_names else []
        if not targets:
            console.print(f"[yellow]⚠[/yellow] {repo_name} has no upstream links defined.")
            store.close()
            return
    else:
        targets = sorted(downstream_names)

    if not targets:
        console.print("[dim]No downstream repos to sync. Define links with: repolink link[/dim]")
        store.close()
        return

    console.rule("[bold blue]Syncing downstream repos[/bold blue]")

    import time
    synced = 0

    for target_name in targets:
        downstream_repo = all_repos[target_name]
        upstream_links = [l for l in all_links if l.downstream == target_name]

        # Ensure surfaces are available for all upstreams
        surfaces: dict = {}
        for link in upstream_links:
            up_repo = all_repos.get(link.upstream)
            if not up_repo:
                continue
            surface = store.get_surface(link.upstream)
            if not surface:
                surface = registry.extract(up_repo.abs_path)
                surface.repo_name = link.upstream
                store.save_surface(surface)
            surfaces[link.upstream] = surface

        # Gather recent changes
        recent_changes: dict = {}
        for link in upstream_links:
            changes = store.get_recent_changes(link.upstream, limit=10)
            if changes:
                recent_changes[link.upstream] = changes

        t0 = time.time()
        content = generate_capsule(
            downstream_repo=downstream_repo,
            upstream_links=upstream_links,
            surfaces=surfaces,
            recent_changes=recent_changes,
        )
        line_count = len(content.splitlines())
        elapsed = time.time() - t0

        if dry_run:
            console.print(f"\n[dim]--- {downstream_repo.claude_upstream_path} ---[/dim]")
            from rich.syntax import Syntax
            console.print(Syntax(content, "markdown", theme="monokai"))
        else:
            downstream_repo.claude_upstream_path.write_text(content, encoding="utf-8")
            # Inject @CLAUDE.upstream.md into CLAUDE.md if it exists
            _inject_claude_md(downstream_repo)

        console.print(
            f"[green]✓[/green] [bold]{target_name}[/bold]/CLAUDE.upstream.md "
            f"— {len(upstream_links)} upstream{'s' if len(upstream_links) != 1 else ''}, "
            f"{line_count} lines "
            f"([dim]{elapsed:.1f}s[/dim])"
        )
        synced += 1

    store.close()
    console.print()
    console.print(
        Panel(
            f"[green]{synced} repo{'s' if synced != 1 else ''} synced.[/green] "
            "Your AI agents have fresh upstream context.\n"
            "[dim]Add to your CLAUDE.md:[/dim] [bold]@CLAUDE.upstream.md[/bold]",
            border_style="green",
        )
    )


def _inject_claude_md(repo: Repo) -> None:
    """Add @CLAUDE.upstream.md import to CLAUDE.md if not already present."""
    claude_md = repo.claude_md_path
    if not claude_md.exists():
        return
    content = claude_md.read_text(encoding="utf-8")
    if "@CLAUDE.upstream.md" in content:
        return
    with claude_md.open("a", encoding="utf-8") as f:
        f.write("\n## Upstream context\n@CLAUDE.upstream.md\n")


# ── repolink show ─────────────────────────────────────────────────────────────

@app.command("show")
def cmd_show(
    repo_name: str = typer.Argument(..., help="Repo to show surface for"),
    types_only: bool = typer.Option(False, "--types-only"),
    endpoints_only: bool = typer.Option(False, "--endpoints-only"),
):
    """Show the full extracted surface for a repo."""
    from rich.syntax import Syntax

    store = _get_store()
    surface = store.get_surface(repo_name)
    store.close()

    if not surface:
        console.print(f"[yellow]⚠[/yellow] No surface cached for [bold]{repo_name}[/bold]. Run: repolink extract {repo_name}")
        return

    console.rule(f"[bold blue]Surface: {repo_name}[/bold blue]")
    console.print(f"[dim]Commit:[/dim] {surface.commit_sha}  [dim]Extracted:[/dim] {relative_time(surface.extracted_at)}")

    if not endpoints_only:
        console.print(f"\n[bold cyan]Exported types ({len(surface.exported_types)})[/bold cyan]")
        for t in surface.exported_types:
            console.print(f"  [dim]{t.file_path}[/dim]")
            console.print(Syntax(t.definition, "typescript", theme="monokai"))

    if not types_only:
        console.print(f"\n[bold cyan]Endpoints ({len(surface.endpoints)})[/bold cyan]")
        for e in surface.endpoints:
            method_color = {"GET": "green", "POST": "blue", "PUT": "yellow", "DELETE": "red", "PATCH": "magenta"}.get(e.method.upper(), "white")
            console.print(f"  [{method_color}]{e.method.upper()}[/{method_color}] {e.path}")
            if e.request_schema:
                console.print(f"    Request:  {e.request_schema}")
            if e.response_schema:
                console.print(f"    Response: {e.response_schema}")


# ── repolink changes ──────────────────────────────────────────────────────────

@app.command("changes")
def cmd_changes(
    upstream: Optional[str] = typer.Argument(None, help="Upstream repo to show changes for"),
    since: Optional[str] = typer.Option(None, "--since", help="Show changes since this commit SHA"),
):
    """Show recent changes detected in upstream repos."""
    store = _get_store()

    if upstream:
        repo = store.get_repo(upstream)
        if not repo:
            console.print(f"[red]✗ Repo not found:[/red] {upstream}")
            store.close()
            raise typer.Exit(1)
        upstreams = [upstream]
    else:
        all_links = store.list_links()
        upstreams = list({l.upstream for l in all_links})

    if not upstreams:
        console.print("[dim]No upstream repos tracked.[/dim]")
        store.close()
        return

    from upstreamiq.graph.models import ChangeKind

    for up_name in sorted(upstreams):
        changes = store.get_recent_changes(up_name, limit=20)
        if not changes:
            console.print(f"[dim]No changes recorded for {up_name}.[/dim]")
            continue

        table = Table(header_style="bold cyan", title=f"Recent changes in {up_name}")
        table.add_column("Time", style="dim")
        table.add_column("Commit", style="dim")
        table.add_column("Type")
        table.add_column("Symbol", style="bold")
        table.add_column("Change")

        breaking_count = 0
        for change in changes:
            if change.kind == ChangeKind.BREAKING:
                kind_str = "[red bold]BREAKING[/red bold]"
                breaking_count += 1
            elif change.kind == ChangeKind.ADDITIVE:
                kind_str = "[green]additive[/green]"
            elif change.kind == ChangeKind.DEPRECATION:
                kind_str = "[yellow]deprecation[/yellow]"
            else:
                kind_str = "[dim]internal[/dim]"

            change_desc = f"{change.before} → {change.after}" if change.before and change.after else (change.after or change.before or "—")
            table.add_row(
                relative_time(change.committed_at),
                change.commit_sha[:8],
                kind_str,
                change.affected_symbol,
                change_desc,
            )

        console.print(table)
        console.print(f"  {len(changes)} changes. [red]{breaking_count} BREAKING.[/red]")

    store.close()


# ── repolink watch ────────────────────────────────────────────────────────────

@app.command("watch")
def cmd_watch(
    interval: int = typer.Option(30, "--interval", "-i", help="Polling interval in seconds"),
    once: bool = typer.Option(False, "--once", help="Run one check cycle and exit"),
):
    """Watch upstream repos for changes and auto-sync downstream repos."""
    from upstreamiq.watcher.daemon import run_watch_loop
    run_watch_loop(interval=interval, once=once)


# ── repolink task ─────────────────────────────────────────────────────────────

@app.command("task")
def cmd_task(
    description: str = typer.Argument(..., help="Feature description"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
    repos_filter: Optional[str] = typer.Option(None, "--repos", help="Comma-separated repo names"),
):
    """Generate a cross-repo task plan for a feature."""
    from upstreamiq.generator.task_planner import generate_task_plan

    store = _get_store()
    all_repos = store.list_repos()
    all_links = store.list_links()
    surfaces = {r.name: store.get_surface(r.name) for r in all_repos}
    # Filter out None surfaces
    surfaces = {k: v for k, v in surfaces.items() if v is not None}
    store.close()

    if repos_filter:
        filter_set = set(repos_filter.split(","))
        all_repos = [r for r in all_repos if r.name in filter_set]
        all_links = [l for l in all_links if l.downstream in filter_set and l.upstream in filter_set]

    if not all_repos:
        console.print("[dim]No repos registered.[/dim]")
        return

    plan = generate_task_plan(
        task_description=description,
        all_repos=all_repos,
        all_links=all_links,
        surfaces=surfaces,
    )

    # Determine output path
    if output:
        out_path = Path(output).expanduser().resolve()
    else:
        tasks_dir = Path.home() / "repolink-tasks"
        tasks_dir.mkdir(exist_ok=True)
        slug = description.lower().replace(" ", "-")[:60]
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        out_path = tasks_dir / f"{slug}.md"

    out_path.write_text(plan, encoding="utf-8")
    console.print(f"[green]✓[/green] Generated: [bold]{out_path}[/bold]")

    # Print the step sequence
    lines = plan.splitlines()
    for line in lines:
        if line.startswith("| ") and "Step" not in line and "----" not in line:
            console.print(f"  {line}")


# ── repolink status ───────────────────────────────────────────────────────────

@app.command("status")
def cmd_status():
    """Quick health check of the current RepoLink setup."""
    from datetime import datetime, timezone

    store = _get_store()
    repos = store.list_repos()
    links = store.list_links()

    downstream_names = {l.downstream for l in links}
    synced_count = sum(1 for r in repos if r.name in downstream_names and r.claude_upstream_path.exists())

    # Surface staleness
    surfaces = [store.get_surface(r.name) for r in repos]
    surfaces = [s for s in surfaces if s is not None]
    freshest = None
    stalest = None
    if surfaces:
        times = sorted(s.extracted_at for s in surfaces)
        freshest = relative_time(times[-1])
        stalest = relative_time(times[0])

    # Unacknowledged breaking changes
    breaking_count = 0
    for r in repos:
        if r.name in downstream_names:
            breaking_count += len(store.get_unacknowledged_changes(r.name))

    store.close()

    lines = [
        f"[bold]{len(repos)}[/bold] repos registered",
        f"[bold]{len(links)}[/bold] links defined",
    ]
    if surfaces:
        lines.append(f"[bold]{len(surfaces)}[/bold] surfaces extracted (freshest: {freshest}, stalest: {stalest})")
    else:
        lines.append("[yellow]⚠[/yellow] No surfaces extracted — run: [bold]repolink extract[/bold]")

    lines.append(f"[bold]{synced_count}[/bold] downstream repos with CLAUDE.upstream.md in sync")

    if breaking_count:
        lines.append(f"[red bold]{breaking_count} unacknowledged BREAKING change{'s' if breaking_count != 1 else ''}[/red bold] (run: repolink changes)")
    else:
        lines.append("[green]✓[/green] No unacknowledged breaking changes")

    lines.append("[dim]Watch daemon: not running (run: repolink watch)[/dim]")

    console.print(Panel("\n".join(lines), title="[bold]RepoLink Status[/bold]", border_style="blue"))
