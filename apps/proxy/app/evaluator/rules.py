from app.schemas.policy import IntentPolicy, DecisionResult

def evaluate_cart_against_policy(checkout_payload: dict, policy: IntentPolicy) -> DecisionResult:
    """
    Evaluates an incoming checkout payload dynamically against a compiled IntentPolicy.
    Uses rules extracted directly from the user's natural language input.
    """
    total_amount = checkout_payload.get("amount", 0)
    line_items = checkout_payload.get("line_items", [])
    rules = policy.rules

    # 1. Dynamic Budget & Variance Check
    if total_amount > rules.max_budget_inr:
        variance = ((total_amount - rules.max_budget_inr) / rules.max_budget_inr) * 100
        
        # Evaluates variance against the dynamically extracted percentage
        if variance <= rules.variance_tolerance_percent:
            return DecisionResult(
                status="AMBIGUOUS",
                reason=(
                    f"Cart total ₹{total_amount:,.2f} exceeds dynamic budget ₹{rules.max_budget_inr:,.2f} "
                    f"by {round(variance, 2)}% (within user's allowed {rules.variance_tolerance_percent}% tolerance)."
                ),
                escalation_id=f"esc_{policy.intent_id}"
            )
        
        return DecisionResult(
            status="VIOLATION",
            reason=f"Cart total ₹{total_amount:,.2f} exceeds user spending limit of ₹{rules.max_budget_inr:,.2f}."
        )

    # 2. Dynamic Line Item & Negative Constraint Checks
    for item in line_items:
        name = item.get("name", "").lower()
        category = item.get("category", "").lower()

        # Check prohibited categories dynamically extracted by LLM compiler
        for prohibited_cat in rules.prohibited_categories:
            if prohibited_cat.lower() in category or prohibited_cat.lower() in name:
                return DecisionResult(
                    status="VIOLATION",
                    reason=f"Cart item '{item.get('name')}' violates prohibited category rule: '{prohibited_cat}'."
                )

        # Check prohibited keywords dynamically extracted by LLM compiler
        for keyword in rules.prohibited_keywords:
            if keyword.lower() in name:
                return DecisionResult(
                    status="VIOLATION",
                    reason=f"Cart item '{item.get('name')}' contains prohibited keyword: '{keyword}'."
                )

    # 3. Clean Match
    return DecisionResult(status="APPROVED")