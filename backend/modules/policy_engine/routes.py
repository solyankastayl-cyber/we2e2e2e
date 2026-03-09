"""
Policy Engine Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from .engine import policy_engine, validate_policy_rules


router = APIRouter(prefix="/api/policies", tags=["policy-engine"])


class UpdatePolicyRequest(BaseModel):
    rules: Dict[str, Any]


class CheckRuleRequest(BaseModel):
    rule_name: str
    value: Any


class ValidateStrategyRequest(BaseModel):
    metrics: Dict[str, Any]


class ValidateRulesRequest(BaseModel):
    policy_id: str
    rules: Dict[str, Any]


@router.get("/health")
async def health_check():
    return policy_engine.get_health()


@router.get("")
async def list_policies(category: Optional[str] = None):
    return {"policies": policy_engine.list_policies(category)}


@router.get("/{policy_id}")
async def get_policy(policy_id: str):
    policy = policy_engine.get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy_engine._policy_to_dict(policy)


@router.patch("/{policy_id}")
async def update_policy(policy_id: str, request: UpdatePolicyRequest):
    result = policy_engine.update_policy(policy_id, request.rules)
    if result is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    if "error" in result and result["error"] == "validation_failed":
        raise HTTPException(status_code=422, detail=result["validation"])
    return result


@router.post("/{policy_id}/check")
async def check_rule(policy_id: str, request: CheckRuleRequest):
    return policy_engine.check_rule(policy_id, request.rule_name, request.value)


@router.post("/validate/strategy")
async def validate_strategy(request: ValidateStrategyRequest):
    return policy_engine.validate_strategy(request.metrics)


@router.post("/validate/rules")
async def validate_rules(request: ValidateRulesRequest):
    """Validate policy rules against schema without applying them"""
    return validate_policy_rules(request.policy_id, request.rules)
