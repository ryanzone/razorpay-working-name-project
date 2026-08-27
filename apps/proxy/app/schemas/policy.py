from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class IntentRules(BaseModel):
    max_budget_inr: float = Field(description="Maximum spending limit in INR")
    variance_tolerance_percent: float = Field(default=5.0, description="Tolerance percentage for budget overage before hold")
    required_categories: List[str] = Field(default_factory=list, description="Categories explicitly required")
    prohibited_categories: List[str] = Field(default_factory=list, description="Categories explicitly forbidden")
    prohibited_keywords: List[str] = Field(default_factory=list, description="Negative keywords to block in item titles")

class IntentPolicy(BaseModel):
    intent_id: UUID
    user_id: str
    raw_prompt: str
    rules: IntentRules
    expires_at: int
    signature: str

class DecisionResult(BaseModel):
    status: str  # "APPROVED", "AMBIGUOUS", or "VIOLATION"
    reason: Optional[str] = None
    escalation_id: Optional[str] = None