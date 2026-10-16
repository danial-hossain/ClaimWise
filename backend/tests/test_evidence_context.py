from app.schemas.policy import ExtractedClause
from app.services.retrieval.evidence_context import select_section_bundles


def make_clause(clause_id: str, section_path: list[str], text: str, *, scope: str = "section", links=None):
    return ExtractedClause(
        clause_id=clause_id,
        page_number=1,
        section_path=section_path,
        scope=scope,
        text=text,
        token_count=len(text.split()),
        document_hash="document-hash",
        related_clause_ids=links or [],
    )


def test_selector_includes_global_clauses_and_entire_relevant_section():
    global_clause = make_clause("G1", ["Global terms"], "Global exclusion wording", scope="document_wide")
    benefit = make_clause("B1", ["Section 2", "Baggage"], "Affirmative baggage wording")
    limit = make_clause("B2", ["Section 2", "Baggage"], "Baggage limit table row")
    unrelated = make_clause("U1", ["Section 9", "Medical"], "Unrelated medical benefit")
    seed = type("Seed", (), {"policy_id": "p", "clause_id": "B1"})()
    selected, limitations = select_section_bundles({"theft": [seed]}, [global_clause, benefit, limit, unrelated], max_chars=10000, document_wide_share=0.3)

    assert {item.clause_id for item in selected} == {"G1", "B1", "B2"}
    assert limitations == []


def test_selector_never_selects_only_part_of_a_section():
    first = make_clause("S1", ["Section A"], "A" * 300)
    second = make_clause("S2", ["Section A"], "B" * 300)
    seed = type("Seed", (), {"policy_id": "p", "clause_id": "S1"})()

    selected, limitations = select_section_bundles({"event one": [seed]}, [first, second], max_chars=950, document_wide_share=0)

    assert selected == []
    assert limitations and "event one" in limitations[0]


def test_selector_follows_cross_reference_into_target_section():
    referring = make_clause("R1", ["Section A"], "See section B for the applicable excess.", links=["B1"])
    linked = make_clause("B1", ["Section B"], "Applicable excess and table.")
    linked_limit = make_clause("B2", ["Section B"], "The section maximum amount applies.")
    seed = type("Seed", (), {"policy_id": "p", "clause_id": "R1"})()

    selected, _ = select_section_bundles({"event one": [seed]}, [referring, linked, linked_limit], max_chars=10000, document_wide_share=0)

    assert {item.clause_id for item in selected} == {"R1", "B1", "B2"}

def test_policy_ids_cannot_alias_same_clause_id():
    from app.schemas.qa import RetrievedClause
    def owned(pid, text):
        return RetrievedClause(**make_clause("same", ["Shared heading"], text).model_dump(),
                               policy_id=pid, fused_rank=1, rrf_score=0.1)
    a, b = owned("a", "Source A"), owned("b", "Source B")
    selected, _ = select_section_bundles({"loss": [a]}, [a, b])
    assert selected == [a]


def test_explicit_source_policy_rejects_foreign_seed():
    seed = type("Seed", (), {"policy_id": "other", "clause_id": "S1"})()
    selected, _ = select_section_bundles({"loss": [seed]},
        [make_clause("S1", ["Cover"], "Source text")], source_policy_id="owner")
    assert selected == []


def test_references_on_non_seed_section_members_expand_and_report_budget():
    first = make_clause("S1", ["Cover"], "Insured benefit")
    condition = make_clause("S2", ["Cover"], "See separate terms", links=["T1"])
    target = make_clause("T1", ["Terms"], "Applicable conditions")
    diagnostics = {}
    selected, _ = select_section_bundles({"loss": [first]}, [first, condition, target],
        max_chars=700, diagnostics=diagnostics)
    assert {c.clause_id for c in selected} == {"S1", "S2"}
    assert diagnostics["loss"]["kept"][0]["clause_ids"] == ["S1", "S2"]
    assert diagnostics["loss"]["dropped"][0]["clause_ids"] == ["T1"]


def test_document_wide_clauses_cannot_cross_policy_boundary():
    from app.schemas.qa import RetrievedClause
    def owned(pid, identifier, scope):
        c = make_clause(identifier, ["Terms"], "Operative terms", scope=scope)
        return RetrievedClause(**c.model_dump(), policy_id=pid, fused_rank=1, rrf_score=0.1)
    seed = owned("a", "S", "section")
    own_global = owned("a", "G", "document_wide")
    foreign_global = owned("b", "G", "document_wide")
    selected, _ = select_section_bundles({"loss": [seed]}, [seed, own_global, foreign_global])
    assert selected == [own_global, seed]
