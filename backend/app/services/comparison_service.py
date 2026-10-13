"""Multi-Policy Comparison Service for ClaimWise.

Provides side-by-side evidence-grounded comparison across 2 to 4 insurance policies.
Tracks explicit attribute status: verified, unknown, conflicting, not_applicable.
Performs deterministic integer-cents illustrative cost calculations using the rules engine.
"Evidence first. If no proof, no answer."
"""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.api.v1.endpoints.policies import _dev_policy_store
from app.schemas.comparison import (
    AttributeStatus,
    ComparisonCostSimulation,
    ComparisonCreateRequest,
    ComparisonRecord,
    CostSimulationAssumption,
    PolicyAttributeEvidence,
    PolicyComparisonCard,
    PolicyCostEstimate,
)
from app.schemas.policy import ExtractedClause, PolicyExtractionResult
from app.schemas.qa import VerifiedCitation
from app.services.retrieval.hybrid_service import hybrid_retrieval_service
from app.services.rules_engine import (
    CostCalculationInput,
    InsuranceRulesEngine,
    cents_to_dollars_str,
    dollars_to_cents,
)

logger = logging.getLogger("claimwise.comparison_service")


class ComparisonService:
    """
    Modular comparison engine evaluating policy terms, exclusions, network rules,
    and deterministic cost sharing for up to 4 authorized policies.
    """

    def create_comparison(
        self,
        request: ComparisonCreateRequest,
        user_id: str = "dev-user-001",
        authorized_policy_store: Optional[Dict[str, PolicyExtractionResult]] = None,
    ) -> ComparisonRecord:
        """
        Build a comprehensive comparison matrix for 2-4 policies.
        
        Validation:
        - Must contain between 2 and 4 policies.
        - Rejects duplicates.
        - Rejects unauthorized or missing policies.
        """
        p_ids = [pid.strip() for pid in request.policy_ids if pid.strip()]
        unique_ids = list(dict.fromkeys(p_ids))

        if len(unique_ids) < 2:
            raise ValueError("A multi-policy comparison requires at least 2 distinct policies.")
        if len(unique_ids) > 4:
            raise ValueError("A multi-policy comparison supports a maximum of 4 policies.")

        store = authorized_policy_store if authorized_policy_store is not None else _dev_policy_store

        # 1. Authorize and load all requested policies
        loaded_policies: List[Tuple[str, PolicyExtractionResult]] = []
        for pid in unique_ids:
            policy = store.get(pid)
            if not policy:
                raise KeyError(f"Policy ID '{pid}' not found or unauthorized.")
            loaded_policies.append((pid, policy))

        # 2. Extract and cross-examine policy attributes
        comparison_cards: List[PolicyComparisonCard] = []
        for pid, policy in loaded_policies:
            card = self._evaluate_policy_attributes(pid, policy)
            comparison_cards.append(card)

        # 3. Deterministic Cost Simulation (if assumptions provided or default requested)
        cost_simulation = None
        if request.cost_assumptions:
            cost_simulation = self._simulate_costs(request.cost_assumptions, comparison_cards)

        # 4. Synthesize objective trade-offs
        tradeoffs = self._synthesize_tradeoffs(comparison_cards, cost_simulation)

        now = datetime.now(timezone.utc)
        comparison_id = f"cmp-{uuid.uuid4().hex[:10]}"

        return ComparisonRecord(
            id=comparison_id,
            user_id=user_id,
            title=request.title or "Multi-Policy Comparative Analysis",
            policy_ids=unique_ids,
            policies=comparison_cards,
            cost_simulation=cost_simulation,
            tradeoff_summary=tradeoffs,
            status="completed",
            created_at=now,
            updated_at=now,
        )

    def _evaluate_policy_attributes(
        self,
        policy_id: str,
        policy: PolicyExtractionResult,
    ) -> PolicyComparisonCard:
        """
        Evaluate and verify key insurance dimensions for a policy.
        Never converts missing values to zero. Uses explicit evidence status.
        """
        clauses = policy.clauses or []
        doc_hash = policy.document_hash
        policy_name = policy.document_name.rsplit(".", 1)[0].replace("_", " ").title()
        insurer_name = "Apex Health Plans" if "apex" in policy_name.lower() else "Insurer Schedule"

        attributes: Dict[str, PolicyAttributeEvidence] = {}

        # 1. Deductible (Individual)
        attributes["deductible_individual"] = self._extract_deductible(policy_id, clauses, doc_hash)

        # 2. Coinsurance Percentage
        attributes["coinsurance_percentage"] = self._extract_coinsurance(policy_id, clauses, doc_hash)

        # 3. Out-of-Pocket Maximum
        attributes["out_of_pocket_max"] = self._extract_oop_max(policy_id, clauses, doc_hash)

        # 4. Copayments (PCP, Specialist, Emergency)
        attributes["copay_pcp"] = self._extract_copay(policy_id, clauses, doc_hash, "pcp")
        attributes["copay_specialist"] = self._extract_copay(policy_id, clauses, doc_hash, "specialist")
        attributes["copay_er"] = self._extract_copay(policy_id, clauses, doc_hash, "er")

        # 5. Exclusions & Limitations
        attributes["exclusions"] = self._extract_exclusions(policy_id, clauses, doc_hash)

        # 6. Network Tier
        attributes["network_tier"] = self._extract_network_tier(policy_id, clauses, doc_hash)

        # 7. Prior Authorization
        attributes["prior_authorization"] = self._extract_prior_auth(policy_id, clauses, doc_hash)

        # 8. Waiting Period & Eligibility
        attributes["waiting_period"] = self._extract_waiting_period(policy_id, clauses, doc_hash)

        return PolicyComparisonCard(
            policy_id=policy_id,
            policy_name=policy_name,
            insurer_name=insurer_name,
            document_hash=doc_hash,
            attributes=attributes,
        )

    def _extract_deductible(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
    ) -> PolicyAttributeEvidence:
        """Extract individual deductible with conflict detection."""
        candidates = []
        for c in clauses:
            text = c.text
            for sentence in re.split(r"[.;\n]", text):
                s = sentence.strip()
                if not s or "deductible" not in s.lower():
                    continue
                # If sentence refers specifically to family and not individual, skip for individual
                if re.search(r"\bfamily\b", s, re.IGNORECASE) and not re.search(r"\bindividual\b", s, re.IGNORECASE):
                    continue

                matches = re.findall(
                    r"(?:individual|annual|calendar\s*year)?\s*deductible(?:\s+is|\s+of|:)?\s*\$([0-9,]+)",
                    s,
                    re.IGNORECASE,
                )
                if not matches:
                    matches = re.findall(r"\$([0-9,]+)\s*(?:individual|annual|calendar\s*year)?\s*deductible", s, re.IGNORECASE)
                for m in matches:
                    val = int(m.replace(",", ""))
                    candidates.append((val, c, f"deductible: ${val:,}"))

        if not candidates:
            return PolicyAttributeEvidence(
                attribute_name="deductible_individual",
                display_name="Individual Deductible",
                raw_value=None,
                numeric_value_cents=None,
                status=AttributeStatus.UNKNOWN,
                citations=[],
                notes="No explicit deductible amount documented in extracted policy clauses.",
            )

        unique_vals = set(val for val, _, _ in candidates)
        if len(unique_vals) > 1:
            # Conflicting values found
            citations = [
                VerifiedCitation(
                    clause_id=c.clause_id,
                    page_number=c.page_number,
                    exact_quote=c.text[:120],
                    policy_id=policy_id,
                    clause_heading=c.clause_heading,
                    verified=True,
                )
                for _, c, _ in candidates[:2]
            ]
            return PolicyAttributeEvidence(
                attribute_name="deductible_individual",
                display_name="Individual Deductible",
                raw_value=f"Conflicting (${min(unique_vals):,} vs ${max(unique_vals):,})",
                numeric_value_cents=None,
                status=AttributeStatus.CONFLICTING,
                citations=citations,
                notes=f"Conflicting deductible values documented across policy clauses: {', '.join(f'${v:,}' for v in unique_vals)}.",
            )

        val, clause, _ = candidates[0]
        cents = val * 100
        # Find exact verbatim substring in clause text
        quote = self._find_exact_quote(clause.text, str(val))
        cit = VerifiedCitation(
            clause_id=clause.clause_id,
            page_number=clause.page_number,
            exact_quote=quote,
            policy_id=policy_id,
            clause_heading=clause.clause_heading,
            verified=True,
        )
        return PolicyAttributeEvidence(
            attribute_name="deductible_individual",
            display_name="Individual Deductible",
            raw_value=f"${val:,}",
            numeric_value_cents=cents,
            status=AttributeStatus.VERIFIED,
            citations=[cit],
            notes=f"Verified individual calendar-year deductible of ${val:,}.",
        )

    def _extract_coinsurance(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
    ) -> PolicyAttributeEvidence:
        """Extract member coinsurance percentage."""
        candidates = []
        for c in clauses:
            text = c.text
            # Pattern: "member pays 20%" or "coinsurance of 20%" or "20% coinsurance"
            matches = re.findall(r"(?:member\s*(?:pays|responsibility|coinsurance)|coinsurance(?:\s+is|\s+of|:)?)\s*([0-9]{1,2})\s*%", text, re.IGNORECASE)
            if not matches:
                matches = re.findall(r"([0-9]{1,2})\s*%\s*(?:member\s*)?coinsurance", text, re.IGNORECASE)
            for m in matches:
                pct = float(m)
                candidates.append((pct, c))

        if not candidates:
            return PolicyAttributeEvidence(
                attribute_name="coinsurance_percentage",
                display_name="Member Coinsurance",
                raw_value=None,
                numeric_value_cents=None,
                status=AttributeStatus.UNKNOWN,
                citations=[],
                notes="Coinsurance percentage not explicitly defined in extracted policy text.",
            )

        unique_pcts = set(pct for pct, _ in candidates)
        if len(unique_pcts) > 1:
            citations = [
                VerifiedCitation(
                    clause_id=c.clause_id,
                    page_number=c.page_number,
                    exact_quote=c.text[:120],
                    policy_id=policy_id,
                    clause_heading=c.clause_heading,
                    verified=True,
                )
                for _, c in candidates[:2]
            ]
            return PolicyAttributeEvidence(
                attribute_name="coinsurance_percentage",
                display_name="Member Coinsurance",
                raw_value=f"Conflicting ({min(unique_pcts):.0f}% vs {max(unique_pcts):.0f}%)",
                numeric_value_cents=None,
                status=AttributeStatus.CONFLICTING,
                citations=citations,
                notes=f"Conflicting coinsurance rates detected: {', '.join(f'{p:.0f}%' for p in unique_pcts)}.",
            )

        pct, clause = candidates[0]
        quote = self._find_exact_quote(clause.text, f"{int(pct)}%")
        cit = VerifiedCitation(
            clause_id=clause.clause_id,
            page_number=clause.page_number,
            exact_quote=quote,
            policy_id=policy_id,
            clause_heading=clause.clause_heading,
            verified=True,
        )
        return PolicyAttributeEvidence(
            attribute_name="coinsurance_percentage",
            display_name="Member Coinsurance",
            raw_value=f"{pct:.0f}%",
            numeric_value_cents=int(pct * 100),
            status=AttributeStatus.VERIFIED,
            citations=[cit],
            notes=f"Member pays {pct:.0f}% after deductible is satisfied.",
        )

    def _extract_oop_max(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
    ) -> PolicyAttributeEvidence:
        """Extract out-of-pocket maximum."""
        candidates = []
        for c in clauses:
            text = c.text
            matches = re.findall(
                r"(?:out-of-pocket\s*(?:maximum|limit|cap)|oop\s*(?:max|limit|cap)|maximum\s*out-of-pocket(?:\s*(?:limit|cap))?)(?:\s+is|\s+of|:)?\s*\$([0-9,]+)",
                text,
                re.IGNORECASE,
            )
            if not matches:
                matches = re.findall(r"\$([0-9,]+)\s*(?:individual|annual)?\s*out-of-pocket\s*(?:maximum|limit|cap)", text, re.IGNORECASE)
            for m in matches:
                val = int(m.replace(",", ""))
                candidates.append((val, c))

        if not candidates:
            return PolicyAttributeEvidence(
                attribute_name="out_of_pocket_max",
                display_name="Out-of-Pocket Maximum",
                raw_value=None,
                numeric_value_cents=None,
                status=AttributeStatus.UNKNOWN,
                citations=[],
                notes="Out-of-pocket maximum cap not found in policy document.",
            )

        unique_vals = set(val for val, _ in candidates)
        if len(unique_vals) > 1:
            citations = [
                VerifiedCitation(
                    clause_id=c.clause_id,
                    page_number=c.page_number,
                    exact_quote=c.text[:120],
                    policy_id=policy_id,
                    clause_heading=c.clause_heading,
                    verified=True,
                )
                for _, c in candidates[:2]
            ]
            return PolicyAttributeEvidence(
                attribute_name="out_of_pocket_max",
                display_name="Out-of-Pocket Maximum",
                raw_value=f"Conflicting (${min(unique_vals):,} vs ${max(unique_vals):,})",
                numeric_value_cents=None,
                status=AttributeStatus.CONFLICTING,
                citations=citations,
                notes="Conflicting OOP maximums found across clauses.",
            )

        val, clause = candidates[0]
        quote = self._find_exact_quote(clause.text, str(val))
        cit = VerifiedCitation(
            clause_id=clause.clause_id,
            page_number=clause.page_number,
            exact_quote=quote,
            policy_id=policy_id,
            clause_heading=clause.clause_heading,
            verified=True,
        )
        return PolicyAttributeEvidence(
            attribute_name="out_of_pocket_max",
            display_name="Out-of-Pocket Maximum",
            raw_value=f"${val:,}",
            numeric_value_cents=val * 100,
            status=AttributeStatus.VERIFIED,
            citations=[cit],
            notes=f"Maximum member liability capped at ${val:,} per calendar year.",
        )

    def _extract_copay(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
        copay_type: str,
    ) -> PolicyAttributeEvidence:
        """Extract specific fixed copayment amounts."""
        labels = {
            "pcp": ("Primary Care Copay", ["pcp", "primary care", "office visit"]),
            "specialist": ("Specialist Visit Copay", ["specialist", "specialty care"]),
            "er": ("Emergency Room Copay", ["emergency room", "emergency department", "er copay"]),
        }
        display_name, terms = labels.get(copay_type, ("Copay", [copay_type]))

        for c in clauses:
            text = c.text
            if any(term in text.lower() for term in terms):
                matches = re.findall(r"(?:copay|copayment)(?:\s+is|\s+of|:)?\s*\$([0-9,]+)", text, re.IGNORECASE)
                if not matches:
                    matches = re.findall(r"\$([0-9,]+)\s*copay", text, re.IGNORECASE)
                if matches:
                    val = int(matches[0].replace(",", ""))
                    quote = self._find_exact_quote(c.text, str(val))
                    cit = VerifiedCitation(
                        clause_id=c.clause_id,
                        page_number=c.page_number,
                        exact_quote=quote,
                        policy_id=policy_id,
                        clause_heading=c.clause_heading,
                        verified=True,
                    )
                    return PolicyAttributeEvidence(
                        attribute_name=f"copay_{copay_type}",
                        display_name=display_name,
                        raw_value=f"${val}",
                        numeric_value_cents=val * 100,
                        status=AttributeStatus.VERIFIED,
                        citations=[cit],
                        notes=f"Fixed copayment of ${val} per visit.",
                    )

        return PolicyAttributeEvidence(
            attribute_name=f"copay_{copay_type}",
            display_name=display_name,
            raw_value=None,
            numeric_value_cents=None,
            status=AttributeStatus.UNKNOWN,
            citations=[],
            notes=f"{display_name} not explicitly stated in extracted policy clauses.",
        )

    def _extract_exclusions(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
    ) -> PolicyAttributeEvidence:
        """Extract explicit exclusions and non-covered services."""
        exclusion_citations = []
        found_terms = []

        for c in clauses:
            text = c.text.lower()
            if "exclusion" in text or "not covered" in text or "excluded services" in text:
                quote = c.text[:140].strip()
                cit = VerifiedCitation(
                    clause_id=c.clause_id,
                    page_number=c.page_number,
                    exact_quote=quote,
                    policy_id=policy_id,
                    clause_heading=c.clause_heading,
                    verified=True,
                )
                exclusion_citations.append(cit)
                if "cosmetic" in text:
                    found_terms.append("Cosmetic procedures")
                if "experimental" in text or "investigational" in text:
                    found_terms.append("Experimental / Investigational treatments")
                if "pre-existing" in text:
                    found_terms.append("Pre-existing conditions")

        if exclusion_citations:
            summary = ", ".join(list(dict.fromkeys(found_terms))) if found_terms else "Standard contract exclusions defined"
            return PolicyAttributeEvidence(
                attribute_name="exclusions",
                display_name="Exclusions & Limitations",
                raw_value=summary,
                numeric_value_cents=None,
                status=AttributeStatus.VERIFIED,
                citations=exclusion_citations[:3],
                notes=f"Identified {len(exclusion_citations)} exclusion clauses in policy record.",
            )

        return PolicyAttributeEvidence(
            attribute_name="exclusions",
            display_name="Exclusions & Limitations",
            raw_value="No explicit exclusion section detected",
            numeric_value_cents=None,
            status=AttributeStatus.UNKNOWN,
            citations=[],
            notes="No specific exclusion clauses were extracted from the document.",
        )

    def _extract_network_tier(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
    ) -> PolicyAttributeEvidence:
        """Extract network tier specifications."""
        for c in clauses:
            text = c.text
            if "in-network" in text.lower() or "preferred provider" in text.lower() or "ppo" in text.lower() or "hmo" in text.lower():
                quote = self._find_exact_quote(c.text, "network")
                cit = VerifiedCitation(
                    clause_id=c.clause_id,
                    page_number=c.page_number,
                    exact_quote=quote,
                    policy_id=policy_id,
                    clause_heading=c.clause_heading,
                    verified=True,
                )
                tier_type = "PPO (In & Out-of-Network)" if "out-of-network" in text.lower() else "Tiered Network"
                return PolicyAttributeEvidence(
                    attribute_name="network_tier",
                    display_name="Network Tier / Structure",
                    raw_value=tier_type,
                    numeric_value_cents=None,
                    status=AttributeStatus.VERIFIED,
                    citations=[cit],
                    notes="Network structure explicitly documented in policy.",
                )

        return PolicyAttributeEvidence(
            attribute_name="network_tier",
            display_name="Network Tier / Structure",
            raw_value=None,
            numeric_value_cents=None,
            status=AttributeStatus.UNKNOWN,
            citations=[],
            notes="Network tiering or provider directory terms not established in extracted text.",
        )

    def _extract_prior_auth(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
    ) -> PolicyAttributeEvidence:
        """Extract prior authorization requirements."""
        for c in clauses:
            text = c.text
            if "prior authorization" in text.lower() or "precertification" in text.lower() or "prior approval" in text.lower():
                quote = self._find_exact_quote(c.text, "prior")
                cit = VerifiedCitation(
                    clause_id=c.clause_id,
                    page_number=c.page_number,
                    exact_quote=quote,
                    policy_id=policy_id,
                    clause_heading=c.clause_heading,
                    verified=True,
                )
                return PolicyAttributeEvidence(
                    attribute_name="prior_authorization",
                    display_name="Prior Authorization",
                    raw_value="Required for Non-Emergency / Advanced Services",
                    numeric_value_cents=None,
                    status=AttributeStatus.VERIFIED,
                    citations=[cit],
                    notes="Prior authorization mandate documented in source clauses.",
                )

        return PolicyAttributeEvidence(
            attribute_name="prior_authorization",
            display_name="Prior Authorization",
            raw_value=None,
            numeric_value_cents=None,
            status=AttributeStatus.UNKNOWN,
            citations=[],
            notes="Prior authorization rules not located in extracted policy document.",
        )

    def _extract_waiting_period(
        self,
        policy_id: str,
        clauses: List[ExtractedClause],
        doc_hash: str,
    ) -> PolicyAttributeEvidence:
        """Extract waiting period or eligibility constraints."""
        for c in clauses:
            text = c.text
            if "waiting period" in text.lower() or "effective date" in text.lower():
                quote = self._find_exact_quote(c.text, "period")
                cit = VerifiedCitation(
                    clause_id=c.clause_id,
                    page_number=c.page_number,
                    exact_quote=quote,
                    policy_id=policy_id,
                    clause_heading=c.clause_heading,
                    verified=True,
                )
                return PolicyAttributeEvidence(
                    attribute_name="waiting_period",
                    display_name="Waiting Period / Eligibility",
                    raw_value="Documented in policy terms",
                    numeric_value_cents=None,
                    status=AttributeStatus.VERIFIED,
                    citations=[cit],
                    notes="Contract eligibility and waiting periods documented in clause.",
                )

        return PolicyAttributeEvidence(
            attribute_name="waiting_period",
            display_name="Waiting Period / Eligibility",
            raw_value="None Documented",
            numeric_value_cents=None,
            status=AttributeStatus.UNKNOWN,
            citations=[],
            notes="No waiting periods or specific eligibility constraints noted in extracted clauses.",
        )

    def _simulate_costs(
        self,
        assumptions: CostSimulationAssumption,
        cards: List[PolicyComparisonCard],
    ) -> ComparisonCostSimulation:
        """
        Execute deterministic cost calculations across policies under explicit assumptions.
        Distinguishes billed charges from allowed amounts.
        If allowed amount is unknown, marks calculations as illustrative / incomplete.
        """
        estimates: List[PolicyCostEstimate] = []
        billed_cents = assumptions.billed_charges_cents
        allowed_cents = assumptions.allowed_amount_cents or billed_cents
        is_known = assumptions.is_allowed_amount_known

        for card in cards:
            ded_attr = card.attributes.get("deductible_individual")
            coins_attr = card.attributes.get("coinsurance_percentage")
            oop_attr = card.attributes.get("out_of_pocket_max")

            is_complete = True
            caveats = []
            audit_steps = []

            if not is_known:
                is_complete = False
                caveats.append(
                    "Negotiated insurer allowed amount is unknown; calculation illustratively assumes billed charge ($"
                    f"{billed_cents / 100:,.2f}) equals allowed amount."
                )

            # Check if required policy parameters are verified
            if not ded_attr or ded_attr.status != AttributeStatus.VERIFIED or ded_attr.numeric_value_cents is None:
                is_complete = False
                caveats.append(f"Deductible is {ded_attr.status.value if ded_attr else 'missing'}; calculation is incomplete.")
                deductible_cents = 0
            else:
                deductible_cents = ded_attr.numeric_value_cents

            if not coins_attr or coins_attr.status != AttributeStatus.VERIFIED or coins_attr.numeric_value_cents is None:
                is_complete = False
                caveats.append(f"Coinsurance percentage is {coins_attr.status.value if coins_attr else 'missing'}; calculation is incomplete.")
                coins_pct = 20.0
            else:
                coins_pct = coins_attr.numeric_value_cents / 100.0

            if not oop_attr or oop_attr.status != AttributeStatus.VERIFIED or oop_attr.numeric_value_cents is None:
                is_complete = False
                caveats.append("Out-of-pocket maximum is unknown or unverified; no OOP cap applied.")
                oop_max_cents = 10000000  # High fallback cap for illustrative calculation
            else:
                oop_max_cents = oop_attr.numeric_value_cents

            # Execute deterministic rules engine
            remaining_ded = max(0, deductible_cents - assumptions.prior_deductible_paid_cents)
            remaining_oop = max(0, oop_max_cents - assumptions.prior_oop_paid_cents)

            calc_input = CostCalculationInput(
                eligible_expense_cents=allowed_cents,
                remaining_deductible_cents=remaining_ded,
                member_coinsurance_percentage=coins_pct,
                remaining_out_of_pocket_max_cents=remaining_oop,
            )

            result = InsuranceRulesEngine.calculate_cost_sharing(
                eligible_expense_cents=allowed_cents,
                remaining_deductible_cents=remaining_ded,
                member_coinsurance_percentage=coins_pct,
                remaining_out_of_pocket_max_cents=remaining_oop,
            )

            audit_steps.extend(result.calculation_steps)
            audit_steps.append(
                f"Billed Charge: {cents_to_dollars_str(billed_cents)} | Evaluated Allowed Amount: {cents_to_dollars_str(allowed_cents)}"
            )

            estimates.append(
                PolicyCostEstimate(
                    policy_id=card.policy_id,
                    policy_name=card.policy_name,
                    is_complete=is_complete,
                    member_responsibility_cents=result.member_total_cents,
                    insurer_responsibility_cents=result.insurer_total_cents,
                    deductible_portion_cents=result.deductible_paid_cents,
                    coinsurance_portion_cents=result.member_coinsurance_cents,
                    copay_portion_cents=0,
                    calculation_audit=audit_steps,
                    caveats_and_assumptions=caveats,
                )
            )

        analysis = self._generate_comparative_cost_analysis(estimates, cards, assumptions)

        return ComparisonCostSimulation(
            assumptions=assumptions,
            policy_estimates=estimates,
            comparative_analysis=analysis,
        )

    def _generate_comparative_cost_analysis(
        self,
        estimates: List[PolicyCostEstimate],
        cards: List[PolicyComparisonCard],
        assumptions: CostSimulationAssumption,
    ) -> List[str]:
        """Generate objective analysis explaining which assumptions materially affect results."""
        analysis = []
        if not assumptions.is_allowed_amount_known:
            analysis.append(
                "CRITICAL ASSUMPTION: The negotiated payer allowed amount is unknown. "
                "Actual patient responsibility will differ significantly once insurer in-network contracted rates are applied."
            )

        # Compare deductible vs coinsurance trade-offs
        if len(estimates) >= 2:
            sorted_by_cost = sorted(
                [e for e in estimates if e.member_responsibility_cents is not None],
                key=lambda x: x.member_responsibility_cents or 0,
            )
            if sorted_by_cost:
                lowest = sorted_by_cost[0]
                highest = sorted_by_cost[-1]
                diff = (highest.member_responsibility_cents or 0) - (lowest.member_responsibility_cents or 0)
                if diff > 0:
                    analysis.append(
                        f"Under the assumed expense of ${assumptions.billed_charges_cents / 100:,.2f}, {lowest.policy_name} "
                        f"yields an illustrative member responsibility of ${lowest.member_responsibility_cents / 100:,.2f}, "
                        f"which is ${diff / 100:,.2f} lower than {highest.policy_name}."
                    )

        analysis.append(
            "Trade-off note: Plans with lower deductibles protect against upfront cash outflows on initial visits, "
            "whereas plans with lower coinsurance percentages provide superior protection on catastrophic high-cost hospitalizations."
        )
        return analysis

    def _synthesize_tradeoffs(
        self,
        cards: List[PolicyComparisonCard],
        simulation: Optional[ComparisonCostSimulation],
    ) -> List[str]:
        """Synthesize factual, evidence-backed trade-offs across the compared policies."""
        tradeoffs = []

        # 1. Deductible comparison
        ded_info = []
        for c in cards:
            attr = c.attributes.get("deductible_individual")
            if attr and attr.status == AttributeStatus.VERIFIED and attr.numeric_value_cents is not None:
                ded_info.append((c.policy_name, attr.numeric_value_cents))

        if len(ded_info) >= 2:
            ded_info.sort(key=lambda x: x[1])
            lowest_name, lowest_val = ded_info[0]
            highest_name, highest_val = ded_info[-1]
            if lowest_val != highest_val:
                tradeoffs.append(
                    f"Deductible Structure: {lowest_name} offers the lowest individual deductible (${lowest_val / 100:,.2f}) "
                    f"compared to ${highest_val / 100:,.2f} for {highest_name}."
                )

        # 2. Coinsurance comparison
        coins_info = []
        for c in cards:
            attr = c.attributes.get("coinsurance_percentage")
            if attr and attr.status == AttributeStatus.VERIFIED and attr.numeric_value_cents is not None:
                coins_info.append((c.policy_name, attr.numeric_value_cents / 100.0))

        if len(coins_info) >= 2:
            coins_info.sort(key=lambda x: x[1])
            tradeoffs.append(
                f"Coinsurance Exposure: Plans range from {coins_info[0][1]:.0f}% ({coins_info[0][0]}) to {coins_info[-1][1]:.0f}% ({coins_info[-1][0]}) member cost-sharing."
            )

        # 3. Missing evidence highlights
        missing_attrs = []
        for c in cards:
            unknowns = [k for k, v in c.attributes.items() if v.status == AttributeStatus.UNKNOWN]
            if unknowns:
                missing_attrs.append(f"{c.policy_name} ({len(unknowns)} unverified dimensions)")

        if missing_attrs:
            tradeoffs.append(
                f"Evidence Completeness: Incomplete policy terms detected for: {', '.join(missing_attrs)}. "
                "Do not assume missing attributes are zero or covered."
            )

        return tradeoffs

    def _find_exact_quote(self, text: str, search_term: str) -> str:
        """Extract a clean, verbatim excerpt from clause text containing the term."""
        idx = text.lower().find(search_term.lower())
        if idx == -1:
            return text[:120].strip()
        start = max(0, idx - 40)
        end = min(len(text), idx + len(search_term) + 60)
        excerpt = text[start:end].strip()
        return excerpt


comparison_service = ComparisonService()
