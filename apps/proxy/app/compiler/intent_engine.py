import hmac
import hashlib
import json
import time
from uuid import uuid4
from google import genai
from google.genai import types

from app.schemas.policy import IntentPolicy, IntentRules
from app.core.config import settings

# Initialize Gemini Client with API Key
client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Define system prompt for strict policy compilation
SYSTEM_INSTRUCTION = """
You are a financial policy engine for an agentic payment gateway.
Your task is to convert a user's natural language shopping instruction into a strict JSON policy schema.

Rules:
1. max_budget_inr: Extract the maximum spending limit in INR.
2. required_categories: Categories/items explicitly requested (e.g., 'laptop', 'shoes').
3. prohibited_categories: Categories explicitly forbidden (e.g., 'warranty', 'accessories', 'insurance').
4. prohibited_keywords: Specific negative keywords to block in line-item names (e.g., 'extended', '3-year', 'bag').
5. variance_tolerance_percent: Default to 5.0 unless user explicitly specifies budget flexibility.
"""

def generate_policy_signature(payload_dict: dict, secret: str) -> str:
    """Generates an HMAC SHA-256 signature over the policy rules for non-repudiation."""
    canonical_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
    return hmac.new(secret.encode('utf-8'), canonical_bytes, hashlib.sha256).hexdigest()

async def compile_user_intent(user_id: str, raw_prompt: str, ttl_seconds: int = 3600) -> IntentPolicy:
    """
    Compiles natural language prompt into a cryptographically signed IntentPolicy.
    """
    # Call Gemini 1.5 Flash with Pydantic Structured Output Enforcement
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=raw_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=IntentRules,
            temperature=0.0,
        ),
    )

    # Parse LLM response into Pydantic model
    parsed_rules: IntentRules = IntentRules.model_validate_json(response.text)

    intent_id = uuid4()
    expires_at = int(time.time()) + ttl_seconds

    # Construct base dictionary to compute signature
    unsigned_payload = {
        "intent_id": str(intent_id),
        "user_id": user_id,
        "rules": parsed_rules.model_dump(),
        "expires_at": expires_at
    }

    # Generate HMAC signature
    signature = generate_policy_signature(unsigned_payload, settings.POLICY_HMAC_SECRET)

    # Return full validated policy
    return IntentPolicy(
        intent_id=intent_id,
        user_id=user_id,
        raw_prompt=raw_prompt,
        rules=parsed_rules,
        expires_at=expires_at,
        signature=signature
    )

if __name__ == "__main__":
    import asyncio

    async def test_compiler():
        test_prompt = "Buy me a college laptop under ₹70,000, absolutely no warranty or accessories."
        print(f"\n[Input Prompt]: {test_prompt}")
        
        policy = await compile_user_intent(user_id="usr_test_99", raw_prompt=test_prompt)
        print("\n[Compiled & Signed Policy Envelope]:")
        print(json.dumps(policy.model_dump(), indent=2, default=str))

    asyncio.run(test_compiler())