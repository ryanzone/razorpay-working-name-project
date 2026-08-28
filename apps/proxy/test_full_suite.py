import httpx
import asyncio
import json
from app.compiler.intent_engine import compile_user_intent

PROXY_URL = "http://127.0.0.1:8000/v1/orders"

async def test_clean_approval():
    print("\n==================================================")
    print("TEST 1: CLEAN APPROVED CART")
    print("==================================================")
    prompt = "Buy a gaming monitor under ₹30,000, no extended warranty."
    policy = await compile_user_intent(user_id="usr_test_01", raw_prompt=prompt)
    
    payload = {
        "checkout_payload": {
            "amount": 28500,
            "currency": "INR",
            "line_items": [{"name": "27-inch 144Hz Monitor", "category": "electronics", "price": 28500}]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(PROXY_URL, json=payload)
        print("Status Code:", res.status_code)
        print("Response:", json.dumps(res.json(), indent=2))
        assert res.status_code == 200
        assert res.json()["status"] == "APPROVED"

async def test_prohibited_violation():
    print("\n==================================================")
    print("TEST 2: PROHIBITED CATEGORY VIOLATION")
    print("==================================================")
    prompt = "Buy me a college laptop under ₹70,000, absolutely no warranty or accessories."
    policy = await compile_user_intent(user_id="usr_test_02", raw_prompt=prompt)
    
    payload = {
        "checkout_payload": {
            "amount": 74000,
            "currency": "INR",
            "line_items": [
                {"name": "Dell XPS 13 College Laptop", "category": "laptop", "price": 65000},
                {"name": "3-Year Extended Warranty", "category": "warranty", "price": 9000}
            ]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        res = await client.post(PROXY_URL, json=payload)
        print("Status Code:", res.status_code)
        print("Response:", json.dumps(res.json(), indent=2))
        assert res.status_code == 400
        assert res.json()["detail"]["status"] == "BLOCKED"

async def test_hitl_hold_and_approve():
    print("\n==================================================")
    print("TEST 3: AMBIGUOUS OVERAGE (HOLD -> APPROVE)")
    print("==================================================")
    prompt = "Buy me a college laptop under ₹70,000, no accessories."
    policy = await compile_user_intent(user_id="usr_test_03", raw_prompt=prompt)
    
    payload = {
        "checkout_payload": {
            "amount": 71400,
            "currency": "INR",
            "line_items": [{"name": "Dell XPS 13 Laptop (Upgraded CPU)", "category": "laptop", "price": 71400}]
        },
        "policy": policy.model_dump(mode="json")
    }

    async with httpx.AsyncClient() as client:
        # Step A: Trigger HOLD
        res = await client.post(PROXY_URL, json=payload)
        print("Hold Response Code:", res.status_code)
        res_json = res.json()
        print("Hold Response:", json.dumps(res_json, indent=2))
        assert res_json["status"] == "HOLD"
        
        escalation_id = res_json["escalation_id"]

        # Step B: Approve Escalation
        approve_url = f"http://127.0.0.1:8000/v1/escalations/{escalation_id}/decision?action=APPROVE"
        decision_res = await client.post(approve_url)
        print("\nDecision Response Code:", decision_res.status_code)
        print("Decision Response:", json.dumps(decision_res.json(), indent=2))
        assert decision_res.status_code == 200
        assert decision_res.json()["escalation_status"] == "APPROVED"

async def main():
    await test_clean_approval()
    await test_prohibited_violation()
    await test_hitl_hold_and_approve()
    print("\n✅ ALL END-TO-END SUITE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())