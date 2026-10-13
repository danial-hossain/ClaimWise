"""Deterministic Insurance Rules Engine for ClaimWise.

Pure Python mathematical engine for computing cost-sharing breakdowns,
deductibles, coinsurance splits, out-of-pocket maximums, and coverage limits.
All financial arithmetic is calculated in integer cents to prevent floating-point errors.

EDUCATIONAL DISCLAIMER:
These calculations are educational simulations and illustrative estimates only.
They do not constitute legal, medical, or financial determinations of actual insurer
payouts. Actual payment depends on policy terms, covered services, exclusions,
network status, pre-authorization, and insurer adjudication.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("claimwise.rules_engine")

EDUCATIONAL_DISCLAIMER = (
    "These are educational calculations, not legal determinations of actual insurer payouts. "
    "Actual reimbursement depends on exact policy wording, covered services, medical necessity, "
    "exclusions, network tier, pre-authorization, and formal insurer adjudication."
)


class CalculationValidationError(ValueError):
    """Raised when calculation inputs are negative, missing, or out of valid bounds."""
    def __init__(self, message: str, field_name: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.field_name = field_name


def dollars_to_cents(amount: Any) -> int:
    """
    Safely convert dollar amount (float, int, str, Decimal) to integer cents.
    
    Raises:
        CalculationValidationError if amount is None, non-numeric, or negative.
    """
    if amount is None:
        raise CalculationValidationError("Amount cannot be None.", field_name="amount")
    try:
        dec = Decimal(str(amount))
    except Exception as exc:
        raise CalculationValidationError(f"Invalid monetary value '{amount}': {exc}", field_name="amount")
    
    if dec < Decimal("0"):
        raise CalculationValidationError(f"Monetary amounts cannot be negative: '{amount}'", field_name="amount")
    
    return int((dec * Decimal("100")).quantize(Decimal("1")))


def cents_to_dollars_str(cents: int) -> str:
    """Format integer cents as formatted USD string, e.g. 15025 -> '$150.25'."""
    if cents < 0:
        return f"-${abs(cents) / 100:,.2f}"
    return f"${cents / 100:,.2f}"


class CostCalculationInput(BaseModel):
    """Input payload for deterministic cost calculation."""
    eligible_expense_cents: int = Field(..., description="Eligible covered expense in integer cents")
    remaining_deductible_cents: int = Field(..., description="Remaining deductible balance in cents")
    member_coinsurance_percentage: float = Field(
        ...,
        description="Member coinsurance share percentage (e.g. 20.0 for 20% member responsibility)",
    )
    remaining_out_of_pocket_max_cents: int = Field(
        ...,
        description="Remaining member out-of-pocket maximum in cents",
    )
    policy_coverage_limit_cents: Optional[int] = Field(
        default=None,
        description="Optional policy coverage or annual limit in cents",
    )
    deductible_counts_towards_oop: bool = Field(
        default=True,
        description="Whether deductible payments count toward out-of-pocket maximum (standard in ACA/US)",
    )

    model_config = ConfigDict(from_attributes=True)


class CostCalculationResult(BaseModel):
    """Detailed deterministic calculation breakdown."""
    eligible_expense_cents: int
    member_total_cents: int
    insurer_total_cents: int
    deductible_paid_cents: int
    member_coinsurance_cents: int
    insurer_coinsurance_cents: int
    uncovered_exceeding_limit_cents: int
    new_remaining_deductible_cents: int
    new_remaining_out_of_pocket_max_cents: int
    new_remaining_coverage_limit_cents: Optional[int] = None
    oop_max_reached: bool
    deductible_met: bool
    calculation_steps: List[str]
    disclaimer: str = EDUCATIONAL_DISCLAIMER
    display_summary: Dict[str, str]

    model_config = ConfigDict(from_attributes=True)


class InsuranceRulesEngine:
    """
    Deterministic mathematical engine for insurance cost-sharing.
    
    Calculations strictly follow this order:
    1. Validate non-negative numbers, valid percentage bounds (0-100%), and non-None values.
    2. Check Policy Limit: If eligible expense exceeds policy limit, the excess is 100% member responsibility.
    3. Apply Deductible: Member pays 100% of expense up to remaining deductible balance.
    4. OOP Maximum Headroom: Evaluate remaining OOP capacity after deductible contribution.
    5. Apply Coinsurance: Remaining post-deductible expense is split according to coinsurance %,
       capped by remaining OOP headroom. Once OOP max is satisfied, insurer pays 100%.
    6. Double-count prevention: Deductible and coinsurance strictly partition the eligible expense.
       Total member + insurer payout equals eligible expense.
    """

    @classmethod
    def validate_inputs(
        cls,
        eligible_expense_cents: Any,
        remaining_deductible_cents: Any,
        member_coinsurance_percentage: Any,
        remaining_out_of_pocket_max_cents: Any,
        policy_coverage_limit_cents: Optional[Any] = None,
    ) -> None:
        """
        Validate all calculation inputs.
        Missing values must not be silently treated as zero.
        Negative values are rejected.
        Percentages must be in [0.0, 100.0].
        """
        # Validate not None
        if eligible_expense_cents is None:
            raise CalculationValidationError(
                "eligible_expense_cents cannot be None. Missing values cannot be silently assumed as zero.",
                field_name="eligible_expense_cents",
            )
        if remaining_deductible_cents is None:
            raise CalculationValidationError(
                "remaining_deductible_cents cannot be None. Missing values cannot be assumed as zero.",
                field_name="remaining_deductible_cents",
            )
        if member_coinsurance_percentage is None:
            raise CalculationValidationError(
                "member_coinsurance_percentage cannot be None.",
                field_name="member_coinsurance_percentage",
            )
        if remaining_out_of_pocket_max_cents is None:
            raise CalculationValidationError(
                "remaining_out_of_pocket_max_cents cannot be None.",
                field_name="remaining_out_of_pocket_max_cents",
            )

        # Validate non-negative cents
        if not isinstance(eligible_expense_cents, int) or eligible_expense_cents < 0:
            raise CalculationValidationError(
                f"eligible_expense_cents must be a non-negative integer, got {eligible_expense_cents}",
                field_name="eligible_expense_cents",
            )
        if not isinstance(remaining_deductible_cents, int) or remaining_deductible_cents < 0:
            raise CalculationValidationError(
                f"remaining_deductible_cents must be a non-negative integer, got {remaining_deductible_cents}",
                field_name="remaining_deductible_cents",
            )
        if not isinstance(remaining_out_of_pocket_max_cents, int) or remaining_out_of_pocket_max_cents < 0:
            raise CalculationValidationError(
                f"remaining_out_of_pocket_max_cents must be a non-negative integer, got {remaining_out_of_pocket_max_cents}",
                field_name="remaining_out_of_pocket_max_cents",
            )

        # Validate coinsurance bounds
        if not isinstance(member_coinsurance_percentage, (int, float)):
            raise CalculationValidationError(
                f"member_coinsurance_percentage must be numeric, got {type(member_coinsurance_percentage)}",
                field_name="member_coinsurance_percentage",
            )
        if member_coinsurance_percentage < 0.0 or member_coinsurance_percentage > 100.0:
            raise CalculationValidationError(
                f"member_coinsurance_percentage must be between 0.0 and 100.0, got {member_coinsurance_percentage}",
                field_name="member_coinsurance_percentage",
            )

        # Validate optional policy coverage limit
        if policy_coverage_limit_cents is not None:
            if not isinstance(policy_coverage_limit_cents, int) or policy_coverage_limit_cents < 0:
                raise CalculationValidationError(
                    f"policy_coverage_limit_cents must be a non-negative integer, got {policy_coverage_limit_cents}",
                    field_name="policy_coverage_limit_cents",
                )

    @classmethod
    def calculate_cost_sharing(
        cls,
        eligible_expense_cents: int,
        remaining_deductible_cents: int,
        member_coinsurance_percentage: float,
        remaining_out_of_pocket_max_cents: int,
        policy_coverage_limit_cents: Optional[int] = None,
        deductible_counts_towards_oop: bool = True,
    ) -> CostCalculationResult:
        """
        Execute deterministic cost-sharing calculation in integer cents.
        """
        # Validate inputs strictly
        cls.validate_inputs(
            eligible_expense_cents=eligible_expense_cents,
            remaining_deductible_cents=remaining_deductible_cents,
            member_coinsurance_percentage=member_coinsurance_percentage,
            remaining_out_of_pocket_max_cents=remaining_out_of_pocket_max_cents,
            policy_coverage_limit_cents=policy_coverage_limit_cents,
        )

        steps: List[str] = []
        steps.append(f"Starting calculation for eligible expense of {cents_to_dollars_str(eligible_expense_cents)}.")

        # Handle zero expense edge case immediately
        if eligible_expense_cents == 0:
            steps.append("Eligible expense is $0.00. No deductible, coinsurance, or out-of-pocket charges applied.")
            return CostCalculationResult(
                eligible_expense_cents=0,
                member_total_cents=0,
                insurer_total_cents=0,
                deductible_paid_cents=0,
                member_coinsurance_cents=0,
                insurer_coinsurance_cents=0,
                uncovered_exceeding_limit_cents=0,
                new_remaining_deductible_cents=remaining_deductible_cents,
                new_remaining_out_of_pocket_max_cents=remaining_out_of_pocket_max_cents,
                new_remaining_coverage_limit_cents=policy_coverage_limit_cents,
                oop_max_reached=remaining_out_of_pocket_max_cents == 0,
                deductible_met=remaining_deductible_cents == 0,
                calculation_steps=steps,
                display_summary={
                    "eligible_expense": "$0.00",
                    "member_responsibility": "$0.00",
                    "insurer_responsibility": "$0.00",
                    "deductible_paid": "$0.00",
                    "coinsurance_paid": "$0.00",
                },
            )

        # Step 1: Policy Coverage Limit Interaction
        uncovered_exceeding_limit_cents = 0
        covered_expense_cents = eligible_expense_cents
        new_remaining_coverage_limit_cents = policy_coverage_limit_cents

        if policy_coverage_limit_cents is not None:
            if eligible_expense_cents > policy_coverage_limit_cents:
                covered_expense_cents = policy_coverage_limit_cents
                uncovered_exceeding_limit_cents = eligible_expense_cents - policy_coverage_limit_cents
                new_remaining_coverage_limit_cents = 0
                steps.append(
                    f"Expense exceeds policy limit of {cents_to_dollars_str(policy_coverage_limit_cents)}. "
                    f"Excess {cents_to_dollars_str(uncovered_exceeding_limit_cents)} is uncovered and member responsibility."
                )
            else:
                new_remaining_coverage_limit_cents = policy_coverage_limit_cents - eligible_expense_cents
                steps.append(
                    f"Expense is within policy limit. Remaining limit after claim: {cents_to_dollars_str(new_remaining_coverage_limit_cents)}."
                )

        # Step 2: Deductible Application
        deductible_paid_cents = min(covered_expense_cents, remaining_deductible_cents)
        post_deductible_expense_cents = covered_expense_cents - deductible_paid_cents
        new_remaining_deductible_cents = remaining_deductible_cents - deductible_paid_cents

        steps.append(
            f"Deductible applied: {cents_to_dollars_str(deductible_paid_cents)}. "
            f"Remaining deductible balance: {cents_to_dollars_str(new_remaining_deductible_cents)}."
        )

        # Step 3: Out-of-Pocket Maximum Headroom
        # Deductible counts toward OOP max in standard ACA/US policies
        if deductible_counts_towards_oop:
            deductible_oop_credit = min(deductible_paid_cents, remaining_out_of_pocket_max_cents)
            oop_headroom_for_coinsurance = remaining_out_of_pocket_max_cents - deductible_oop_credit
        else:
            deductible_oop_credit = 0
            oop_headroom_for_coinsurance = remaining_out_of_pocket_max_cents

        steps.append(
            f"Out-of-pocket maximum headroom available for coinsurance: {cents_to_dollars_str(oop_headroom_for_coinsurance)}."
        )

        # Step 4: Coinsurance Calculation
        member_coinsurance_cents = 0
        insurer_coinsurance_cents = 0

        if post_deductible_expense_cents > 0:
            if oop_headroom_for_coinsurance <= 0:
                # OOP max is fully reached; insurer pays 100% of remaining covered expense
                member_coinsurance_cents = 0
                insurer_coinsurance_cents = post_deductible_expense_cents
                steps.append(
                    f"Out-of-pocket maximum is met ($0 headroom). Insurer covers 100% of remaining "
                    f"{cents_to_dollars_str(post_deductible_expense_cents)}."
                )
            else:
                # Calculate member coinsurance in integer cents
                # round(amount * pct / 100)
                raw_member_coinsurance = int(
                    round(post_deductible_expense_cents * (member_coinsurance_percentage / 100.0))
                )
                # Cap member coinsurance by remaining OOP headroom
                member_coinsurance_cents = min(raw_member_coinsurance, oop_headroom_for_coinsurance)
                insurer_coinsurance_cents = post_deductible_expense_cents - member_coinsurance_cents

                steps.append(
                    f"Coinsurance calculated at {member_coinsurance_percentage}% member responsibility: "
                    f"Member pays {cents_to_dollars_str(member_coinsurance_cents)}, "
                    f"Insurer pays {cents_to_dollars_str(insurer_coinsurance_cents)}."
                )

        # Step 5: Final Aggregation and Verification
        # Total member responsibility
        member_total_cents = deductible_paid_cents + member_coinsurance_cents + uncovered_exceeding_limit_cents
        # Total insurer responsibility
        insurer_total_cents = covered_expense_cents - (deductible_paid_cents + member_coinsurance_cents)

        # Conservation of money check
        assert member_total_cents + insurer_total_cents == eligible_expense_cents, (
            f"Accounting discrepancy: member ({member_total_cents}) + insurer ({insurer_total_cents}) "
            f"!= total expense ({eligible_expense_cents})"
        )

        # Calculate new remaining OOP maximum
        total_oop_accrued = deductible_oop_credit + member_coinsurance_cents
        new_remaining_oop_cents = max(0, remaining_out_of_pocket_max_cents - total_oop_accrued)

        oop_max_reached = new_remaining_oop_cents == 0
        deductible_met = new_remaining_deductible_cents == 0

        steps.append(
            f"Total Member Responsibility: {cents_to_dollars_str(member_total_cents)}. "
            f"Total Insurer Responsibility: {cents_to_dollars_str(insurer_total_cents)}. "
            f"New OOP Maximum Remaining: {cents_to_dollars_str(new_remaining_oop_cents)}."
        )

        return CostCalculationResult(
            eligible_expense_cents=eligible_expense_cents,
            member_total_cents=member_total_cents,
            insurer_total_cents=insurer_total_cents,
            deductible_paid_cents=deductible_paid_cents,
            member_coinsurance_cents=member_coinsurance_cents,
            insurer_coinsurance_cents=insurer_coinsurance_cents,
            uncovered_exceeding_limit_cents=uncovered_exceeding_limit_cents,
            new_remaining_deductible_cents=new_remaining_deductible_cents,
            new_remaining_out_of_pocket_max_cents=new_remaining_oop_cents,
            new_remaining_coverage_limit_cents=new_remaining_coverage_limit_cents,
            oop_max_reached=oop_max_reached,
            deductible_met=deductible_met,
            calculation_steps=steps,
            display_summary={
                "eligible_expense": cents_to_dollars_str(eligible_expense_cents),
                "member_total": cents_to_dollars_str(member_total_cents),
                "insurer_total": cents_to_dollars_str(insurer_total_cents),
                "deductible_paid": cents_to_dollars_str(deductible_paid_cents),
                "coinsurance_paid": cents_to_dollars_str(member_coinsurance_cents),
                "new_remaining_deductible": cents_to_dollars_str(new_remaining_deductible_cents),
                "new_remaining_oop": cents_to_dollars_str(new_remaining_oop_cents),
            },
        )


rules_engine = InsuranceRulesEngine()
