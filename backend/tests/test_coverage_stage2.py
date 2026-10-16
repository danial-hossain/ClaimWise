"""Synthetic recordings exercise Stage-2 validation, scope and arithmetic contracts."""
import copy
import importlib.util
import json
from pathlib import Path
import pytest
from app.schemas.coverage import PayableInputs
from app.services.payable_amount import calculate_payable

script = Path(__file__).resolve().parents[1] / "scripts/coverage_event_evaluation.py"
spec = importlib.util.spec_from_file_location("coverage_event_evaluation", script)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)
FIXTURES = json.loads(evaluation.FIXTURES.read_text())


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f["id"])
def test_stage2_synthetic_recordings(fixture):
    event = evaluation.evaluate_event(fixture)
    assert event["error_stage"] is None, event
    if fixture.get("table_detector_miss"):
        assert event["details"]["detected_tables"] == 0


def test_model_cannot_override_code_arithmetic():
    fixture = copy.deepcopy(next(f for f in FIXTURES if f["id"] == "limit-and-depreciation"))
    fixture["model_output"].update(payable_amount="99999999", calculation="Pay everything")
    event = evaluation.evaluate_event(fixture)
    assert event["metrics"]["amount_accuracy"] == 1


def test_missing_inputs_are_named_without_assumed_zero():
    amount, calculation, missing = calculate_payable(PayableInputs(claimed_amount=100))
    assert amount == "needs more information: item_age, limit, depreciation_rate, excess"
    assert missing == ["item_age", "limit", "depreciation_rate", "excess"]
    assert calculation is None


@pytest.mark.parametrize("inputs", [
    {"claimed_amount": "NaN"}, {"limit": -1}, {"depreciation_rate": 2}, {"excess": "Infinity"},
])
def test_invalid_money_inputs_are_rejected(inputs):
    with pytest.raises(ValueError):
        PayableInputs(**inputs)


def test_depreciation_and_excess_cannot_make_negative_payment():
    amount, _, missing = calculate_payable(PayableInputs(claimed_amount=100, item_age=20,
        limit=90, depreciation_rate="0.1", excess=50))
    assert amount == "0.00" and not missing


@pytest.mark.parametrize("metric,stage", [
    ("extraction_accuracy", "extraction"), ("retrieval_recall", "selection"),
    ("selection_recall", "selection"), ("status_accuracy", "answering"),
    ("amount_accuracy", "answering"), ("citation_accuracy", "answering"),
])
def test_error_stage_is_derived_from_metrics(metric, stage):
    metrics = dict.fromkeys(["extraction_accuracy", "retrieval_recall", "selection_recall",
                            "status_accuracy", "amount_accuracy", "citation_accuracy"], 1.0)
    metrics[metric] = 0.0
    assert evaluation.error_stage(metrics) == stage


def test_event_evaluation_marks_wrong_recorded_status_as_answering():
    fixture = copy.deepcopy(FIXTURES[0])
    fixture["model_output"]["verdict"] = "covered"
    event = evaluation.evaluate_event(fixture)
    assert event["error_stage"] == "answering"
    assert event["metrics"]["status_accuracy"] == 0


def test_answering_exception_is_not_misattributed_to_selection(monkeypatch):
    monkeypatch.setattr(evaluation.CoverageGapService, "_analyze_with_gemini",
                        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad response")))
    event = evaluation.evaluate_event(FIXTURES[0])
    assert event["metrics"]["selection_recall"] == 1
    assert event["error_stage"] == "answering"
