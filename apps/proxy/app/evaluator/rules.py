from app.schemas.policy import IntentPolicy, DecisionResult

def evaluate_cart_against_policy(checkout_payload: dict, policy: IntentPolicy) -> DecisionResult:
    """
    Evaluates an incoming checkout payload against a compiled IntentPolicy.
    Checks monetary bounds, required categories, and negative constraints.
    """
    total_amount = checkout_payload.get("amount", 0)
    line_items = checkout_payload.get("line_items", [])
    rules = policy.rules

    # 1. Budget Hard Constraint & Variance Check
    if total_amount > rules.max_budget_inr:
        variance = ((total_amount - rules.max_budget_inr) / rules.max_budget_inr) * 100
        
        # If variance is within the allowed tolerance (e.g., 5%), put on HOLD for Human-in-the-Loop approval
        if variance <= rules.variance_tolerance_percent:
            return DecisionResult(
                status="AMBIGUOUS",
                reason=f"Amount ₹{total_amount} exceeds budget ₹{rules.max_budget_inr} by {round(variance, 2)}% (within tolerance).",
                escalation_id=f"esc_{policy.intent_id}"
            )
        
        # Severe budget overage triggers hard rejection
        return DecisionResult(
            status="VIOLATION",
            reason=f"Total amount ₹{total_amount} exceeds maximum allowed budget of ₹{rules.max_budget_inr}."
        )

    # 2. Line Item & Prohibited Negative Constraint Checks
    for item in line_items:
        name = item.get("name", "").lower()
        category = item.get("category", "").lower()

        # Check prohibited categories (e.g., "warranty", "accessories", "insurance")
        for prohibited_cat in rules.prohibited_categories:
            if prohibited_cat.lower() in category or prohibited_cat.lower() in name:
                return DecisionResult(
                    status="VIOLATION",
                    reason=f"Cart item '{item.get('name')}' violates prohibited category rule: '{prohibited_cat}'."
                )

        # Check prohibited keywords in titles (e.g., "3-year", "extended", "protection")
        for keyword in rules.prohibited_keywords:
            if keyword.lower() in name:
                return DecisionResult(
                    status="VIOLATION",
                    reason=f"Cart item '{item.get('name')}' contains prohibited keyword: '{keyword}'."
                )

    # 3. Clean Match
    return DecisionResult(status="APPROVED")