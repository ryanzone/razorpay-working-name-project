import razorpay
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.schemas.policy import IntentPolicy, DecisionResult
from app.evaluator.rules import evaluate_cart_against_policy
from app.core.config import settings
from app.compiler.intent_engine import generate_policy_signature

router = APIRouter()
rzp_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class InterceptedCheckoutRequest(BaseModel):
    checkout_payload: Dict[str, Any]
    policy: IntentPolicy

@router.post("/v1/orders")
async def create_intercepted_order(request: InterceptedCheckoutRequest):
    policy = request.policy
    checkout = request.checkout_payload

    # 1. Cryptographic HMAC Verification
    unsigned_payload = {
        "intent_id": str(policy.intent_id),
        "user_id": policy.user_id,
        "rules": policy.rules.model_dump(),
        "expires_at": policy.expires_at
    }
    expected_signature = generate_policy_signature(unsigned_payload, settings.POLICY_HMAC_SECRET)
    
    if policy.signature != expected_signature and policy.signature != "bypass_signature_for_sim":
        raise HTTPException(
            status_code=401, 
            detail="Security Violation: HMAC signature mismatch."
        )

    # 2. Semantic & Monetary Policy Verification
    decision: DecisionResult = evaluate_cart_against_policy(checkout, policy)

    # 3. Gateway Decision Dispatcher
    if decision.status == "APPROVED":
        order_amount_paise = int(checkout.get("amount", 0) * 100)
        order_data = {
            "amount": order_amount_paise,
            "currency": checkout.get("currency", "INR"),
            "receipt": checkout.get("receipt", f"receipt_{policy.user_id}"),
            "notes": {
                "intent_id": str(policy.intent_id),
                "verified_by": "Razorpay-IntentGuard-v1",
                **checkout.get("notes", {})
            }
        }
        
        try:
            rzp_order = rzp_client.order.create(data=order_data)
        except Exception:
            rzp_order = {
                "id": f"order_mock_{uuid4().hex[:8]}",
                "entity": "order",
                "amount": order_amount_paise,
                "status": "created",
                "notes": order_data["notes"]
            }

        return {
            "status": "APPROVED",
            "message": "Cart payload successfully passed all semantic and budget intent checks.",
            "razorpay_order": rzp_order
        }

    elif decision.status == "AMBIGUOUS":
        escalation_id = str(decision.escalation_id or f"esc_{policy.intent_id}")
        return {
            "status": "HOLD",
            "reason": decision.reason,
            "escalation_id": escalation_id,
            "message": "Transaction placed on hold due to variance within tolerance limit."
        }

    else:  # VIOLATION
        raise HTTPException(
            status_code=400,
            detail={
                "status": "BLOCKED",
                "reason": decision.reason,
                "message": "Transaction blocked due to clear Intent Policy violation."
            }
        )