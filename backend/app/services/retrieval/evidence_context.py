"""Source-preserving context selection. Never turn a character slice into a clause."""
from typing import TypeVar

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
