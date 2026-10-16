"""Source-preserving context selection. Never turn a character slice into a clause."""
from collections import OrderedDict
from typing import Any, TypeVar

T = TypeVar("T")


def select_complete_evidence(clauses: list[T], max_chars: int = 40000) -> tuple[list[T], list[str]]:
    selected, omitted, seen = [], [], set()
    used = 0
    for clause in clauses:
        key = (clause.policy_id, clause.clause_id, clause.page_number)
        if key in seen:
            continue
        seen.add(key)
        cost = len(clause.text) + 300  # reserve delimiters and source metadata
        if used + cost > max_chars:
            omitted.append(f"{clause.policy_id}/{clause.clause_id} (PDF page {clause.page_number})")
            continue
        selected.append(clause)
        used += cost
    limitations = []
    if omitted:
        limitations.append("Context budget omitted whole source clauses: " + ", ".join(omitted)
            + ". These excerpts cannot establish a complete coverage position.")
    return selected, limitations


def _bundle_key(clause: Any) -> tuple[Any, ...]:
    scope = getattr(clause, "scope", "unknown")
    path = tuple(getattr(clause, "section_path", None) or ())
    if scope == "document_wide":
        return ("document_wide", path) if path else ("document_wide_clause", clause.document_hash, clause.clause_id, clause.page_number)
    if path:
        return ("section", path[:1])
    return ("clause", clause.document_hash, clause.clause_id, clause.page_number)


def select_section_bundles(
    relevant_by_event: dict[str, list[Any]],
    source_clauses: list[Any],
    max_chars: int = 40000,
    document_wide_share: float = 0.25,
    *,
    source_policy_id: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> tuple[list[Any], list[str]]:
    """Select complete source sections; resolve references only within their document.

    Extracted clauses have no policy ID. Their document hash supplies identity unless
    the caller explicitly supplies the owning policy. Never alias another policy's IDs.
    """
    from app.services.policy_extraction_validation import is_clause_evidence_eligible

    def owner(clause):
        return (getattr(clause, "policy_id", None) or source_policy_id,
                clause.document_hash)

    def key(clause):
        return (owner(clause), _bundle_key(clause))

    bundles = OrderedDict()
    by_id = {}
    for clause in source_clauses:
        if not is_clause_evidence_eligible(clause):
            continue
        bundles.setdefault(key(clause), []).append(clause)
        by_id.setdefault(clause.clause_id, []).append(clause)

    def resolve(seed, identifier):
        candidates = by_id.get(identifier, [])
        pid = getattr(seed, "policy_id", None)
        doc = getattr(seed, "document_hash", None)
        candidates = [c for c in candidates
                      if (not doc or c.document_hash == doc)
                      and (not owner(c)[0] or not pid or owner(c)[0] == pid)]
        return candidates[0] if len(candidates) == 1 else None

    def label(k):
        first = bundles[k][0]
        return " > ".join(first.section_path) or f"source clause {first.clause_id}"

    selected, selected_keys, limitations = [], set(), []
    used = 0
    global_budget = int(max_chars * min(max(document_wide_share, 0.0), 1.0))
    seeds = [seed for values in relevant_by_event.values() for seed in values]
    def in_requested_source(k):
        pid, doc = k[0]
        if source_policy_id and pid and pid != source_policy_id:
            return False
        return any((not getattr(seed, "policy_id", None) or not pid or seed.policy_id == pid)
                   and (not getattr(seed, "document_hash", None) or seed.document_hash == doc)
                   for seed in seeds)
    global_keys = [k for k in bundles if k[1][0].startswith("document_wide") and in_requested_source(k)]
    for k in global_keys:
        cost = sum(len(c.text) + 300 for c in bundles[k])
        if used + cost <= max(global_budget, max_chars // 2):
            selected.extend(bundles[k]); selected_keys.add(k); used += cost
        else:
            limitations.append(f"Document-wide evidence bundle omitted by its configured context share: {label(k)}")

    event_keys = {}
    for event, seeds in relevant_by_event.items():
        keys, visited = [], set()
        pending = [(seed, seed.clause_id) for seed in seeds]
        while pending:
            seed, identifier = pending.pop(0)
            source = resolve(seed, identifier)
            if source is None:
                continue
            k = key(source)
            if k in visited:
                continue
            visited.add(k)
            keys.append(k)
            # References on any member of a selected section matter, including limits.
            for member in bundles[k]:
                pending.extend((source, target) for target in member.related_clause_ids)
        event_keys[event] = list(dict.fromkeys([*global_keys, *keys]))
    event_items = list(event_keys.items())
    ranked = [(event, k) for rank in range(max((len(keys) for _, keys in event_items), default=0))
              for event, keys in event_items if rank < len(keys) for k in [keys[rank]]]
    for event, k in ranked:
        if k in selected_keys or k in global_keys:
            continue
        cost = sum(len(c.text) + 300 for c in bundles[k])
        if used + cost > max_chars:
            limitations.append(f"Event {event}: complete section bundle omitted by context budget: {label(k)}")
        else:
            selected.extend(bundles[k]); selected_keys.add(k); used += cost

    if diagnostics is not None:
        for event, keys in event_keys.items():
            def describe(k):
                return {"document_hash": k[0][1], "section_path": list(bundles[k][0].section_path),
                        "clause_ids": [c.clause_id for c in bundles[k]],
                        "chars": sum(len(c.text) + 300 for c in bundles[k])}
            diagnostics[event] = {
                "kept": [describe(k) for k in keys if k in selected_keys],
                "dropped": [describe(k) for k in keys if k not in selected_keys],
                "budget_chars": max_chars,
            }
    return selected, limitations
