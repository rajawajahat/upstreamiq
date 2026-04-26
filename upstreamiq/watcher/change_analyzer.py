"""Analyzes differences between two ExtractedSurfaces to detect breaking changes."""
from __future__ import annotations

from upstreamiq.graph.models import (
    ChangeEvent,
    ChangeKind,
    EndpointDef,
    ExtractedSurface,
    TypeDef,
)


def analyze_diff(
    old_surface: ExtractedSurface,
    new_surface: ExtractedSurface,
    commit_sha: str,
    commit_message: str,
    affected_downstream: list[str],
) -> list[ChangeEvent]:
    """Compare two surfaces and return detected ChangeEvents."""
    changes: list[ChangeEvent] = []

    changes.extend(_diff_types(old_surface, new_surface, commit_sha, commit_message, affected_downstream))
    changes.extend(_diff_endpoints(old_surface, new_surface, commit_sha, commit_message, affected_downstream))

    return changes


def _diff_types(
    old: ExtractedSurface,
    new: ExtractedSurface,
    sha: str,
    msg: str,
    downstream: list[str],
) -> list[ChangeEvent]:
    changes = []
    old_map = {t.name: t for t in old.exported_types}
    new_map = {t.name: t for t in new.exported_types}

    # Removed types → BREAKING
    for name, typedef in old_map.items():
        if name not in new_map:
            changes.append(ChangeEvent(
                upstream_repo=old.repo_name,
                commit_sha=sha,
                commit_message=msg,
                committed_at=new.extracted_at,
                kind=ChangeKind.BREAKING,
                affected_symbol=name,
                before=typedef.definition[:200],
                after="",
                affected_downstream=downstream,
            ))

    # New types → ADDITIVE
    for name, typedef in new_map.items():
        if name not in old_map:
            changes.append(ChangeEvent(
                upstream_repo=old.repo_name,
                commit_sha=sha,
                commit_message=msg,
                committed_at=new.extracted_at,
                kind=ChangeKind.ADDITIVE,
                affected_symbol=name,
                before="",
                after=typedef.definition[:200],
                affected_downstream=downstream,
            ))

    # Changed types → analyze fields
    for name in old_map:
        if name not in new_map:
            continue
        old_def = old_map[name].definition
        new_def = new_map[name].definition

        if old_def.strip() == new_def.strip():
            continue

        old_fields = _parse_fields(old_def)
        new_fields = _parse_fields(new_def)

        # Removed fields → BREAKING
        for field_name, field_type in old_fields.items():
            if field_name not in new_fields:
                changes.append(ChangeEvent(
                    upstream_repo=old.repo_name,
                    commit_sha=sha,
                    commit_message=msg,
                    committed_at=new.extracted_at,
                    kind=ChangeKind.BREAKING,
                    affected_symbol=name,
                    before=f"{field_name}: {field_type}",
                    after="",
                    affected_downstream=downstream,
                ))
            elif new_fields[field_name] != field_type:
                # Type changed → BREAKING
                changes.append(ChangeEvent(
                    upstream_repo=old.repo_name,
                    commit_sha=sha,
                    commit_message=msg,
                    committed_at=new.extracted_at,
                    kind=ChangeKind.BREAKING,
                    affected_symbol=name,
                    before=f"{field_name}: {field_type}",
                    after=f"{field_name}: {new_fields[field_name]}",
                    affected_downstream=downstream,
                ))

        # Added fields → ADDITIVE
        for field_name, field_type in new_fields.items():
            if field_name not in old_fields:
                changes.append(ChangeEvent(
                    upstream_repo=old.repo_name,
                    commit_sha=sha,
                    commit_message=msg,
                    committed_at=new.extracted_at,
                    kind=ChangeKind.ADDITIVE,
                    affected_symbol=name,
                    before="",
                    after=f"{field_name}: {field_type}",
                    affected_downstream=downstream,
                ))

    return changes


def _diff_endpoints(
    old: ExtractedSurface,
    new: ExtractedSurface,
    sha: str,
    msg: str,
    downstream: list[str],
) -> list[ChangeEvent]:
    changes = []
    old_map = {(e.method.upper(), e.path): e for e in old.endpoints}
    new_map = {(e.method.upper(), e.path): e for e in new.endpoints}

    # Removed endpoints → BREAKING
    for key, ep in old_map.items():
        if key not in new_map:
            changes.append(ChangeEvent(
                upstream_repo=old.repo_name,
                commit_sha=sha,
                commit_message=msg,
                committed_at=new.extracted_at,
                kind=ChangeKind.BREAKING,
                affected_symbol=f"{ep.method.upper()} {ep.path}",
                before=f"response: {ep.response_schema}",
                after="",
                affected_downstream=downstream,
            ))

    # New endpoints → ADDITIVE
    for key, ep in new_map.items():
        if key not in old_map:
            changes.append(ChangeEvent(
                upstream_repo=old.repo_name,
                commit_sha=sha,
                commit_message=msg,
                committed_at=new.extracted_at,
                kind=ChangeKind.ADDITIVE,
                affected_symbol=f"{ep.method.upper()} {ep.path}",
                before="",
                after=f"response: {ep.response_schema}",
                affected_downstream=downstream,
            ))

    # Changed response schema → check for BREAKING
    for key in old_map:
        if key not in new_map:
            continue
        old_ep = old_map[key]
        new_ep = new_map[key]
        if old_ep.response_schema and new_ep.response_schema and old_ep.response_schema != new_ep.response_schema:
            changes.append(ChangeEvent(
                upstream_repo=old.repo_name,
                commit_sha=sha,
                commit_message=msg,
                committed_at=new.extracted_at,
                kind=ChangeKind.BREAKING,
                affected_symbol=f"{old_ep.method.upper()} {old_ep.path}",
                before=old_ep.response_schema,
                after=new_ep.response_schema,
                affected_downstream=downstream,
            ))

    return changes


def _parse_fields(definition: str) -> dict[str, str]:
    """Parse field names and types from a compact type definition."""
    import re
    fields: dict[str, str] = {}
    # Match patterns like:  fieldName: TypeName  or  fieldName?: TypeName
    pattern = re.compile(r"^\s+(\w+)\??\s*:\s*(.+?)(?:;|,)?\s*$", re.MULTILINE)
    for match in pattern.finditer(definition):
        name = match.group(1)
        type_str = match.group(2).strip()
        # Skip comment lines
        if name.startswith("//") or name.startswith("#"):
            continue
        fields[name] = type_str
    return fields
