import razorpay
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any

from app.schemas.policy import IntentPolicy, DecisionResult
from app.evaluator.rules import evaluate_cart_against_policy
from app.core.config import settings
from app.compiler.intent_engine import generate_policy_signature
from app.services.escalation_store import save_escalation, EscalationRecord
from app.services.notifier import notifier
from app.services.audit import record_audit_log, get_all_audit_logs, AuditLogEntry

router = APIRouter()
rzp_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class InterceptedCheckoutRequest(BaseModel):
    checkout_payload: Dict[str, Any]
    policy: IntentPolicy

@router.get("/v1/audit-trail")
async def fetch_audit_trail():
    """Returns all non-repudiable transaction interception logs."""
    return {"count": len(get_all_audit_logs()), "logs": get_all_audit_logs()}

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
    
    if policy.signature != expected_signature:
        raise HTTPException(status_code=401, detail="Security Violation: HMAC signature mismatch.")

    # 2. Policy Rule Evaluation
    decision: DecisionResult = evaluate_cart_against_policy(checkout, policy)
    log_id = f"log_{uuid4().hex[:10]}"

    # 3. Decision Routing
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
        rzp_order = rzp_client.order.create(data=order_data)

        # Audit Record
        record_audit_log(AuditLogEntry(
            log_id=log_id,
            intent_id=str(policy.intent_id),
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status="APPROVED",
            reason="Passed all intent checks.",
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump(),
            razorpay_order_id=rzp_order.get("id")
        ))

        return {
            "status": "APPROVED",
            "message": "Cart payload successfully passed all semantic and budget intent checks.",
            "razorpay_order": rzp_order
        }

    elif decision.status == "AMBIGUOUS":
        escalation_id = str(decision.escalation_id or f"esc_{policy.intent_id}")
        reason_msg = str(decision.reason or "Over budget within tolerance")

        # Save state to escalation store
        save_escalation(EscalationRecord(
            escalation_id=escalation_id,
            status="PENDING",
            reason=reason_msg,
            checkout_payload=checkout,
            policy=policy.model_dump(mode="json")
        ))

        # Send outbound notification
        await notifier.send_whatsapp_escalation(
            escalation_id=escalation_id,
            reason=reason_msg,
            checkout_payload=checkout
        )

        # Audit Record
        record_audit_log(AuditLogEntry(
            log_id=log_id,
            intent_id=str(policy.intent_id),
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status="HOLD",
            reason=reason_msg,
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump()
        ))

        return {
            "status": "HOLD",
            "reason": decision.reason,
            "escalation_id": escalation_id,
            "message": "Transaction placed on hold. Interactive approval notification dispatched."
        }

    else:  # VIOLATION
        reason_msg = str(decision.reason or "Policy violation detected")

        # Audit Record
        record_audit_log(AuditLogEntry(
            log_id=log_id,
            intent_id=str(policy.intent_id),
            user_id=policy.user_id,
            raw_prompt=policy.raw_prompt,
            status="BLOCKED",
            reason=reason_msg,
            checkout_payload=checkout,
            policy_rules=policy.rules.model_dump()
        ))

        raise HTTPException(
            status_code=400,
            detail={
                "status": "BLOCKED",
                "reason": decision.reason,
                "message": "Transaction blocked due to clear Intent Policy violation."
            }
        )