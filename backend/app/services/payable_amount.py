"""Money arithmetic independent of language-model generated calculations."""
from decimal import Decimal, ROUND_HALF_UP
from app.schemas.coverage import PayableInputs


def calculate_payable(inputs: PayableInputs) -> tuple[str, str | None, list[str]]:
    required = ["claimed_amount", "limit", "excess"]
    if inputs.depreciation_method != "not_applicable":
        required.append("depreciation_rate")
    if inputs.depreciation_method == "annual":
        required.append("item_age")
    missing = [name for name in PayableInputs.model_fields if name in required and getattr(inputs, name) is None]
    if missing:
        return "needs more information: " + ", ".join(missing), None, missing
    if inputs.depreciation_method == "not_applicable":
        depreciation = Decimal(0)
    elif inputs.depreciation_method == "flat":
        depreciation = inputs.depreciation_rate
    else:
        depreciation = min(inputs.item_age * inputs.depreciation_rate, Decimal(1))
    depreciated = inputs.claimed_amount * (1 - depreciation)
    capped = min(depreciated, inputs.limit)
    payable = max(capped - inputs.excess, Decimal(0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    explanation = (f"Claimed {inputs.claimed_amount}; depreciation method {inputs.depreciation_method}; age {inputs.item_age} years; rate "
                   f"{inputs.depreciation_rate}: depreciated value {depreciated}; "
                   f"cap {inputs.limit}: {capped}; less excess {inputs.excess}; payable {payable}.")
    return str(payable), explanation, []
