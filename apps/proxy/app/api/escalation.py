import razorpay
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from uuid import uuid4

from app.services.audit import record_audit_log, AuditLogEntry
from app.services.escalation_store import get_escalation, update_escalation_status
from app.core.config import settings

router = APIRouter()
rzp_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

class DecisionRequest(BaseModel):
    action: str = Field(..., description="'APPROVE' or 'REJECT'")

@router.post("/v1/escalations/{escalation_id}/decision")
@router.get("/v1/escalations/{escalation_id}/decision")
async def handle_escalation_decision(
    escalation_id: str,
    action: Optional[str] = Query(None, description="'APPROVE' or 'REJECT' via URL query"),
    body: Optional[DecisionRequest] = None
):
    selected_action = (action or (body.action if body else "")).upper()
    
    if selected_action not in ["APPROVE", "REJECT"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'APPROVE' or 'REJECT'.")

    record = get_escalation(escalation_id)
    if not record:
        raise HTTPException(status_code=404, detail="Escalation record not found or expired.")

    if record.status != "PENDING":
        return {
            "status": record.status,
            "message": f"Escalation has already been processed with decision: {record.status}"
        }

    checkout = record.checkout_payload
    policy = record.policy

    if selected_action == "APPROVE":
        order_amount_paise = int(checkout.get("amount", 0) * 100)

        order_data = {
            "amount": order_amount_paise,
            "currency": checkout.get("currency", "INR"),
            "receipt": checkout.get("receipt", f"receipt_{escalation_id}"),
            "notes": {
                "intent_id": str(policy.get("intent_id", "")),
                "escalation_id": escalation_id,
                "approved_by": "Human-in-the-Loop",
                "verified_by": "Razorpay-IntentGuard-v1"
            }
        }

        try:
            rzp_order = rzp_client.order.create(data=order_data)
            update_escalation_status(escalation_id, "APPROVED")

            # Record Approved Audit Log
            record_audit_log(AuditLogEntry(
                log_id=f"log_{uuid4().hex[:10]}",
                intent_id=str(policy.get("intent_id", "")),
                user_id=str(policy.get("user_id", checkout.get("user_id", "unknown"))),
                raw_prompt=str(policy.get("raw_prompt", "Escalated Transaction")),
                status="ESCALATED_APPROVED",
                reason=f"Human approved held transaction: {record.reason}",
                checkout_payload=checkout,
                policy_rules=policy.get("rules", {}),
                razorpay_order_id=str(rzp_order.get("id"))
            ))

            return {
                "status": "SUCCESS",
                "escalation_status": "APPROVED",
                "message": "Human approval recorded. Held transaction successfully resumed and executed on Razorpay.",
                "razorpay_order": rzp_order
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to execute Razorpay order: {str(e)}")

    else:  # REJECT
        update_escalation_status(escalation_id, "REJECTED")

        # Record Rejected Audit Log
        record_audit_log(AuditLogEntry(
            log_id=f"log_{uuid4().hex[:10]}",
            intent_id=str(policy.get("intent_id", "")),
            user_id=str(policy.get("user_id", checkout.get("user_id", "unknown"))),
            raw_prompt=str(policy.get("raw_prompt", "Escalated Transaction")),
            status="ESCALATED_REJECTED",
            reason=f"Human rejected held transaction: {record.reason}",
            checkout_payload=checkout,
            policy_rules=policy.get("rules", {})
        ))

        return {
            "status": "BLOCKED",
            "escalation_status": "REJECTED",
            "message": "Human decision recorded: Transaction rejected and permanently canceled."
        }