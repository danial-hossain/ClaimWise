"""Unit tests for Deterministic Insurance Rules Engine."""

import pytest
from app.services.rules_engine import (
    CalculationValidationError,
    cents_to_dollars_str,
    dollars_to_cents,
    rules_engine,
)


def test_dollars_to_cents_and_formatting():
    """Verify conversion of monetary values to exact integer cents."""
    assert dollars_to_cents(50) == 5000
    assert dollars_to_cents("150.25") == 15025
    assert dollars_to_cents(0) == 0
    assert dollars_to_cents(99.99) == 9999

    assert cents_to_dollars_str(5000) == "$50.00"
    assert cents_to_dollars_str(15025) == "$150.25"
    assert cents_to_dollars_str(0) == "$0.00"

    with pytest.raises(CalculationValidationError):
        dollars_to_cents(-10)


def test_expense_below_deductible():
    """Member pays 100% of expense when below remaining deductible balance."""
    # $300 eligible expense, $500 deductible, 20% coinsurance, $2000 OOP max
    result = rules_engine.calculate_cost_sharing(
        eligible_expense_cents=30000,
        remaining_deductible_cents=50000,
        member_coinsurance_percentage=20.0,
        remaining_out_of_pocket_max_cents=200000,
    )

    assert result.member_total_cents == 30000
    assert result.insurer_total_cents == 0
    assert result.deductible_paid_cents == 30000
    assert result.member_coinsurance_cents == 0
    assert result.new_remaining_deductible_cents == 20000
    assert result.new_remaining_out_of_pocket_max_cents == 170000
    assert result.deductible_met is False
    assert result.oop_max_reached is False


def test_expense_above_deductible():
    """Deductible is satisfied, remaining portion split by coinsurance percentage."""
    # $1,000 eligible expense, $500 deductible, 20% coinsurance, $3000 OOP max
    # Deductible: $500. Remaining: $500. 20% coinsurance: $100 member, $400 insurer.
    result = rules_engine.calculate_cost_sharing(
        eligible_expense_cents=100000,
        remaining_deductible_cents=50000,
        member_coinsurance_percentage=20.0,
        remaining_out_of_pocket_max_cents=300000,
    )

    assert result.deductible_paid_cents == 50000
    assert result.member_coinsurance_cents == 10000
    assert result.insurer_coinsurance_cents == 40000
    assert result.member_total_cents == 60000  # $600
    assert result.insurer_total_cents == 40000  # $400
    assert result.new_remaining_deductible_cents == 0
    assert result.deductible_met is True
    # OOP max credit: $500 deductible + $100 coinsurance = $600
    assert result.new_remaining_out_of_pocket_max_cents == 240000


def test_out_of_pocket_maximum_reached():
    """Member coinsurance capped when out-of-pocket maximum is reached."""
    # $5,000 expense, $500 deductible, 20% coinsurance, $800 remaining OOP max
    # Deductible: $500 (counts to OOP -> $300 OOP capacity left).
    # Post-deductible: $4,500. 20% coinsurance = $900. Capped at $300!
    # Member total = $500 + $300 = $800. Insurer total = $4,200.
    result = rules_engine.calculate_cost_sharing(
        eligible_expense_cents=500000,
        remaining_deductible_cents=50000,
        member_coinsurance_percentage=20.0,
        remaining_out_of_pocket_max_cents=80000,
    )

    assert result.deductible_paid_cents == 50000
    assert result.member_coinsurance_cents == 30000  # Capped at $300
    assert result.insurer_coinsurance_cents == 420000  # $4,200
    assert result.member_total_cents == 80000  # $800
    assert result.insurer_total_cents == 420000
    assert result.oop_max_reached is True
    assert result.new_remaining_out_of_pocket_max_cents == 0


def test_zero_eligible_expense():
    """Zero eligible expense results in zero charges."""
    result = rules_engine.calculate_cost_sharing(
        eligible_expense_cents=0,
        remaining_deductible_cents=50000,
        member_coinsurance_percentage=20.0,
        remaining_out_of_pocket_max_cents=200000,
    )

    assert result.member_total_cents == 0
    assert result.insurer_total_cents == 0
    assert result.deductible_paid_cents == 0
    assert result.member_coinsurance_cents == 0
    assert result.new_remaining_deductible_cents == 50000


def test_invalid_negative_amounts_rejected():
    """Negative monetary values must raise CalculationValidationError."""
    with pytest.raises(CalculationValidationError) as exc:
        rules_engine.calculate_cost_sharing(
            eligible_expense_cents=-5000,
            remaining_deductible_cents=50000,
            member_coinsurance_percentage=20.0,
            remaining_out_of_pocket_max_cents=200000,
        )
    assert exc.value.field_name == "eligible_expense_cents"


def test_missing_inputs_not_silently_zero():
    """None values must not be silently treated as zero."""
    with pytest.raises(CalculationValidationError) as exc:
        rules_engine.calculate_cost_sharing(
            eligible_expense_cents=10000,
            remaining_deductible_cents=None,  # type: ignore
            member_coinsurance_percentage=20.0,
            remaining_out_of_pocket_max_cents=200000,
        )
    assert exc.value.field_name == "remaining_deductible_cents"


def test_percentage_out_of_bounds():
    """Coinsurance percentage must be between 0.0 and 100.0."""
    with pytest.raises(CalculationValidationError):
        rules_engine.calculate_cost_sharing(
            eligible_expense_cents=10000,
            remaining_deductible_cents=5000,
            member_coinsurance_percentage=105.0,  # Invalid > 100%
            remaining_out_of_pocket_max_cents=20000,
        )

    with pytest.raises(CalculationValidationError):
        rules_engine.calculate_cost_sharing(
            eligible_expense_cents=10000,
            remaining_deductible_cents=5000,
            member_coinsurance_percentage=-5.0,  # Invalid < 0%
            remaining_out_of_pocket_max_cents=20000,
        )


def test_policy_coverage_limit_interactions():
    """Amounts exceeding policy limit are uncovered and 100% member responsibility."""
    # $15,000 expense, $10,000 policy limit, $500 deductible, 20% coinsurance, $3,000 OOP max
    # Excess above limit: $5,000 (member pays 100%).
    # Covered portion: $10,000.
    # Deductible on covered: $500. Remaining covered: $9,500.
    # Coinsurance 20% of $9,500 = $1,900.
    # OOP max credit = $500 + $1,900 = $2,400 (< $3,000 OOP max).
    # Member pays: $500 + $1,900 + $5,000 = $7,400.
    # Insurer pays: $7,600.
    # Total = $7,400 + $7,600 = $15,000.
    result = rules_engine.calculate_cost_sharing(
        eligible_expense_cents=1500000,
        remaining_deductible_cents=50000,
        member_coinsurance_percentage=20.0,
        remaining_out_of_pocket_max_cents=300000,
        policy_coverage_limit_cents=1000000,
    )

    assert result.uncovered_exceeding_limit_cents == 500000
    assert result.deductible_paid_cents == 50000
    assert result.member_coinsurance_cents == 190000
    assert result.insurer_coinsurance_cents == 760000
    assert result.member_total_cents == 740000
    assert result.insurer_total_cents == 760000
    assert result.member_total_cents + result.insurer_total_cents == 1500000
    assert result.new_remaining_coverage_limit_cents == 0


def test_conservation_of_money_and_no_double_counting():
    """Member total + Insurer total must strictly equal eligible expense in all cases."""
    cases = [
        (5000, 10000, 20.0, 50000),
        (25000, 10000, 15.0, 50000),
        (100000, 5000, 30.0, 15000),
        (500000, 25000, 10.0, 30000),
    ]
    for expense, deductible, coinsurance, oop in cases:
        res = rules_engine.calculate_cost_sharing(
            eligible_expense_cents=expense,
            remaining_deductible_cents=deductible,
            member_coinsurance_percentage=coinsurance,
            remaining_out_of_pocket_max_cents=oop,
        )
        assert res.member_total_cents + res.insurer_total_cents == expense
