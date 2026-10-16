"""Automatic source validation for extracted policy clauses."""

from difflib import SequenceMatcher
import re
from typing import Any


_TOKEN_PATTERN = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)


def is_clause_evidence_eligible(clause: Any) -> bool:
    """Allow only contractual clauses with a passing source check into evidence retrieval.

    Legacy records without validation metadata remain usable, but explicitly rejected
    extraction blocks and non-clause blocks never become evidence.
    """
    if not getattr(clause, "is_clause", True):
        return False
    validation = getattr(clause, "validation", None)
    return not isinstance(validation, dict) or validation.get("verbatim_pass") is True


def _tokens_with_spans(text: str) -> list[tuple[str, int, int]]:
    original = text or ""
    # Keep a map back to the original page after repairing line-wrap hyphens.
    removed = set()
    for match in re.finditer(r"(?<=\w)[-\u2010\u2011\u2013\u2014]\s*\r?\n\s*(?=\w)", original):
        removed.update(range(match.start(), match.end()))
    offsets = [index for index in range(len(original)) if index not in removed]
    repaired = "".join(original[index] for index in offsets)
    return [(match.group(0).casefold(), offsets[match.start()], offsets[match.end() - 1] + 1)
            for match in _TOKEN_PATTERN.finditer(repaired)]



def validate_page_clauses(source_text: str, clauses: list[Any], threshold: float = 0.88) -> dict[str, Any]:
    """Verify each clause against one page and report source text not represented by clauses.

    Matching is ordered token-level similarity, which tolerates PDF whitespace and line-wrap
    changes while rejecting reordered or mostly fabricated wording. Character offsets refer
    to the extracted page text used as the comparison source.
    """
    source_tokens = _tokens_with_spans(source_text)
    source_words = [token for token, _, _ in source_tokens]
    covered = [False] * len(source_tokens)
    pass_count = 0

    for clause in clauses:
        clause_tokens = _tokens_with_spans(clause.text)
        clause_words = [token for token, _, _ in clause_tokens]
        blocks = SequenceMatcher(None, source_words, clause_words, autojunk=False).get_matching_blocks()
        matched = sum(block.size for block in blocks)
        similarity = matched / max(len(clause_words), 1)
        passed = bool(clause_words) and similarity >= threshold
        source_indices: list[int] = []
        if passed:
            pass_count += 1
            for block in blocks:
                source_indices.extend(range(block.a, block.a + block.size))
            for index in source_indices:
                covered[index] = True
        start = min((source_tokens[index][1] for index in source_indices), default=None)
        end = max((source_tokens[index][2] for index in source_indices), default=None)
        if not clause.section_path:
            attribution = "unresolved"
        elif clause.heading_confidence == "high":
            attribution = "structural"
        else:
            attribution = "inherited"
        clause.validation = {
            "verbatim_similarity": round(similarity, 4),
            "verbatim_pass": passed,
            "source_span_start": start,
            "source_span_end": end,
            "attribution_status": attribution,
            "attribution_flagged": attribution == "unresolved",
        }
        if not passed:
            clause.is_clause = False

    uncovered_spans: list[str] = []
    index = 0
    while index < len(source_tokens):
        if covered[index]:
            index += 1
            continue
        start_index = index
        while index < len(source_tokens) and not covered[index]:
            index += 1
        if index - start_index < 3:
            continue
        start = source_tokens[start_index][1]
        end = source_tokens[index - 1][2]
        span = re.sub(r"\s+", " ", (source_text or "")[start:end]).strip()
        if len(span) >= 12:
            uncovered_spans.append(span[:800])

    source_count = len(source_tokens)
    covered_count = sum(covered)
    return {
        "source_token_count": source_count,
        "covered_token_count": covered_count,
        "coverage_ratio": round(covered_count / max(source_count, 1), 4),
        "uncovered_spans": uncovered_spans,
        "verbatim_clause_count": len(clauses),
        "verbatim_pass_count": pass_count,
        "attribution_verified_count": sum(1 for clause in clauses if clause.validation["attribution_status"] == "structural"),
        "attribution_flagged_count": sum(1 for clause in clauses if clause.validation["attribution_flagged"]),
    }