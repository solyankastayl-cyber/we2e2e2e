"""
Policy Engine
=============

Unified policy layer for governing the entire system.

Centralizes all rules:
- Strategy policies
- Tournament policies
- Research policies
- Risk policies

Includes schema validation for policy rules.
"""

import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class PolicyCategory(str, Enum):
    STRATEGY = "STRATEGY"
    TOURNAMENT = "TOURNAMENT"
    RESEARCH = "RESEARCH"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    GOVERNANCE = "GOVERNANCE"


# Schema definition for policy rule validation
# Each rule maps to: (type, min_value, max_value) or (type, allowed_values)
POLICY_SCHEMAS: Dict[str, Dict[str, tuple]] = {
    "STRATEGY_ADMISSION": {
        "min_trades": ("int", 1, 10000),
        "min_pf": ("float", 0.0, 100.0),
        "min_sharpe": ("float", -5.0, 10.0),
        "max_drawdown": ("float", 0.0, 1.0),
        "fragility_limit": ("enum", ["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
        "min_win_rate": ("float", 0.0, 1.0),
    },
    "TOURNAMENT_RULES": {
        "min_sharpe_to_enter": ("float", -5.0, 10.0),
        "min_sharpe_to_win": ("float", -5.0, 10.0),
        "max_crowding": ("float", 0.0, 1.0),
        "orthogonality_required": ("bool",),
        "min_rounds": ("int", 1, 100),
        "elimination_threshold": ("float", 0.0, 1.0),
    },
    "RESEARCH_LOOP": {
        "max_features_per_cycle": ("int", 1, 1000),
        "max_alphas_per_cycle": ("int", 1, 500),
        "max_mutations_per_cycle": ("int", 1, 5000),
        "cooldown_hours": ("float", 0.0, 168.0),
        "max_cycles_per_day": ("int", 1, 1000),
        "memory_check_required": ("bool",),
    },
    "RISK_LIMITS": {
        "max_portfolio_drawdown": ("float", 0.0, 1.0),
        "max_leverage": ("float", 0.0, 100.0),
        "max_single_strategy_weight": ("float", 0.0, 1.0),
        "max_family_concentration": ("float", 0.0, 1.0),
        "crisis_cash_ratio": ("float", 0.0, 1.0),
        "stress_exposure_limit": ("float", 0.0, 1.0),
    },
    "EXECUTION_LIMITS": {
        "max_slippage_bps": ("int", 0, 1000),
        "max_participation_pct": ("float", 0.0, 1.0),
        "max_order_size_pct": ("float", 0.0, 1.0),
        "reject_on_low_liquidity": ("bool",),
        "gap_protection_enabled": ("bool",),
    },
    "GOVERNANCE_RULES": {
        "auto_demotion_enabled": ("bool",),
        "demotion_drawdown_threshold": ("float", 0.0, 1.0),
        "promotion_min_days": ("int", 0, 365),
        "edge_decay_threshold": ("float", -1.0, 0.0),
        "fragility_auto_exclude": ("bool",),
    },
}


def validate_policy_rules(policy_id: str, rules: Dict[str, Any]) -> Dict:
    """
    Validate policy rules against schema.
    Returns validation result with any violations.
    """
    schema = POLICY_SCHEMAS.get(policy_id)
    if not schema:
        return {"valid": True, "violations": [], "warning": "No schema defined"}
    
    violations = []
    
    for rule_name, value in rules.items():
        if rule_name not in schema:
            violations.append({
                "rule": rule_name,
                "error": "unknown_rule",
                "message": f"Rule '{rule_name}' is not defined in schema for {policy_id}",
            })
            continue
        
        spec = schema[rule_name]
        rule_type = spec[0]
        
        if rule_type == "int":
            if not isinstance(value, (int, float)):
                violations.append({
                    "rule": rule_name,
                    "error": "type_error",
                    "expected": "integer",
                    "actual": type(value).__name__,
                })
            else:
                min_val, max_val = spec[1], spec[2]
                if value < min_val or value > max_val:
                    violations.append({
                        "rule": rule_name,
                        "error": "range_error",
                        "message": f"Value {value} out of range [{min_val}, {max_val}]",
                    })
        
        elif rule_type == "float":
            if not isinstance(value, (int, float)):
                violations.append({
                    "rule": rule_name,
                    "error": "type_error",
                    "expected": "number",
                    "actual": type(value).__name__,
                })
            else:
                min_val, max_val = spec[1], spec[2]
                if value < min_val or value > max_val:
                    violations.append({
                        "rule": rule_name,
                        "error": "range_error",
                        "message": f"Value {value} out of range [{min_val}, {max_val}]",
                    })
        
        elif rule_type == "bool":
            if not isinstance(value, bool):
                violations.append({
                    "rule": rule_name,
                    "error": "type_error",
                    "expected": "boolean",
                    "actual": type(value).__name__,
                })
        
        elif rule_type == "enum":
            allowed = spec[1]
            if str(value).upper() not in allowed:
                violations.append({
                    "rule": rule_name,
                    "error": "enum_error",
                    "message": f"Value '{value}' not in allowed: {allowed}",
                })
    
    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "rules_checked": len(rules),
    }


@dataclass
class Policy:
    """Single policy definition"""
    policy_id: str
    name: str
    category: PolicyCategory
    
    rules: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 0
    
    description: str = ""
    created_at: int = 0
    updated_at: int = 0


class PolicyEngine:
    """
    Central Policy Engine.
    
    Manages and enforces all system policies.
    """
    
    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self._init_default_policies()
    
    def _init_default_policies(self):
        """Initialize default policies"""
        now = int(time.time() * 1000)
        
        # Strategy Policy
        self.policies["STRATEGY_ADMISSION"] = Policy(
            policy_id="STRATEGY_ADMISSION",
            name="Strategy Admission Policy",
            category=PolicyCategory.STRATEGY,
            rules={
                "min_trades": 30,
                "min_pf": 1.1,
                "min_sharpe": 0.5,
                "max_drawdown": 0.25,
                "fragility_limit": "HIGH",
                "min_win_rate": 0.40
            },
            description="Rules for admitting strategies to production",
            created_at=now
        )
        
        # Tournament Policy
        self.policies["TOURNAMENT_RULES"] = Policy(
            policy_id="TOURNAMENT_RULES",
            name="Tournament Rules Policy",
            category=PolicyCategory.TOURNAMENT,
            rules={
                "min_sharpe_to_enter": 0.5,
                "min_sharpe_to_win": 0.8,
                "max_crowding": 0.70,
                "orthogonality_required": True,
                "min_rounds": 3,
                "elimination_threshold": 0.3
            },
            description="Rules for alpha tournament",
            created_at=now
        )
        
        # Research Policy
        self.policies["RESEARCH_LOOP"] = Policy(
            policy_id="RESEARCH_LOOP",
            name="Research Loop Policy",
            category=PolicyCategory.RESEARCH,
            rules={
                "max_features_per_cycle": 50,
                "max_alphas_per_cycle": 20,
                "max_mutations_per_cycle": 100,
                "cooldown_hours": 1,
                "max_cycles_per_day": 24,
                "memory_check_required": True
            },
            description="Rules for automated research",
            created_at=now
        )
        
        # Risk Policy
        self.policies["RISK_LIMITS"] = Policy(
            policy_id="RISK_LIMITS",
            name="Risk Limits Policy",
            category=PolicyCategory.RISK,
            rules={
                "max_portfolio_drawdown": 0.20,
                "max_leverage": 1.5,
                "max_single_strategy_weight": 0.15,
                "max_family_concentration": 0.40,
                "crisis_cash_ratio": 0.80,
                "stress_exposure_limit": 0.60
            },
            description="Global risk limits",
            created_at=now
        )
        
        # Execution Policy
        self.policies["EXECUTION_LIMITS"] = Policy(
            policy_id="EXECUTION_LIMITS",
            name="Execution Limits Policy",
            category=PolicyCategory.EXECUTION,
            rules={
                "max_slippage_bps": 50,
                "max_participation_pct": 0.01,
                "max_order_size_pct": 0.05,
                "reject_on_low_liquidity": True,
                "gap_protection_enabled": True
            },
            description="Execution quality limits",
            created_at=now
        )
        
        # Governance Policy
        self.policies["GOVERNANCE_RULES"] = Policy(
            policy_id="GOVERNANCE_RULES",
            name="Governance Rules Policy",
            category=PolicyCategory.GOVERNANCE,
            rules={
                "auto_demotion_enabled": True,
                "demotion_drawdown_threshold": 0.15,
                "promotion_min_days": 30,
                "edge_decay_threshold": -0.20,
                "fragility_auto_exclude": True
            },
            description="System governance rules",
            created_at=now
        )
    
    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get policy by ID"""
        return self.policies.get(policy_id)
    
    def list_policies(self, category: str = None) -> List[Dict]:
        """List all policies"""
        policies = list(self.policies.values())
        if category:
            try:
                cat = PolicyCategory(category)
                policies = [p for p in policies if p.category == cat]
            except ValueError:
                pass
        return [self._policy_to_dict(p) for p in policies]
    
    def update_policy(self, policy_id: str, rules: Dict) -> Optional[Dict]:
        """
        Update policy rules with schema validation.
        Returns tuple (policy, validation_result) or None.
        """
        policy = self.policies.get(policy_id)
        if not policy:
            return None
        
        # Validate rules against schema
        validation = validate_policy_rules(policy_id, rules)
        if not validation["valid"]:
            return {"error": "validation_failed", "validation": validation}
        
        policy.rules.update(rules)
        policy.updated_at = int(time.time() * 1000)
        return {"policy": self._policy_to_dict(policy), "validation": validation}
    
    def check_rule(self, policy_id: str, rule_name: str, value: Any) -> Dict:
        """Check if a value passes a policy rule"""
        policy = self.policies.get(policy_id)
        if not policy or rule_name not in policy.rules:
            return {"passed": False, "error": "Rule not found"}
        
        rule_value = policy.rules[rule_name]
        
        # Simple comparison
        if isinstance(rule_value, (int, float)):
            if "max" in rule_name:
                passed = value <= rule_value
            elif "min" in rule_name:
                passed = value >= rule_value
            else:
                passed = value == rule_value
        elif isinstance(rule_value, bool):
            passed = value == rule_value
        elif isinstance(rule_value, str):
            passed = str(value).upper() == rule_value.upper()
        else:
            passed = value == rule_value
        
        return {
            "policy_id": policy_id,
            "rule": rule_name,
            "rule_value": rule_value,
            "actual_value": value,
            "passed": passed
        }
    
    def validate_strategy(self, metrics: Dict) -> Dict:
        """Validate strategy against admission policy"""
        policy = self.policies.get("STRATEGY_ADMISSION")
        if not policy:
            return {"valid": True, "violations": []}
        
        violations = []
        for rule, threshold in policy.rules.items():
            if rule in metrics:
                check = self.check_rule("STRATEGY_ADMISSION", rule, metrics[rule])
                if not check["passed"]:
                    violations.append(check)
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "policy_id": "STRATEGY_ADMISSION"
        }
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phaseC",
            "status": "ok",
            "total_policies": len(self.policies),
            "by_category": {
                cat.value: len([p for p in self.policies.values() if p.category == cat])
                for cat in PolicyCategory
            },
            "timestamp": int(time.time() * 1000)
        }
    
    def _policy_to_dict(self, p: Policy) -> Dict:
        return {
            "policy_id": p.policy_id,
            "name": p.name,
            "category": p.category.value,
            "rules": p.rules,
            "enabled": p.enabled,
            "priority": p.priority,
            "description": p.description
        }


# Singleton
policy_engine = PolicyEngine()
