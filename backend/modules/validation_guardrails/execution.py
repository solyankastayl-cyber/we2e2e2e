"""
Phase 8.0: Execution Assumptions Validator
Ensures realistic execution assumptions in backtests
"""
from typing import Dict, List, Optional, Any
from .types import (
    ExecutionCheckResult,
    Violation,
    ViolationType,
    SeverityLevel,
    GUARDRAILS_CONFIG
)


class ExecutionValidator:
    """
    Validates execution assumptions in backtests.
    
    Common unrealistic assumptions:
    1. Zero slippage (instant fills at exact price)
    2. Unlimited liquidity (can fill any size instantly)
    3. No market impact (large orders don't move price)
    4. Zero or unrealistic fees
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or GUARDRAILS_CONFIG.get("execution", {})
        
    def check(
        self,
        backtest_config: Dict[str, Any],
        trades: Optional[List[Dict[str, Any]]] = None,
        market_data: Optional[Dict[str, Any]] = None
    ) -> ExecutionCheckResult:
        """
        Check execution assumptions for realism.
        
        Args:
            backtest_config: Backtest configuration with execution params
            trades: List of executed trades to analyze
            market_data: Market data with liquidity info
            
        Returns:
            ExecutionCheckResult with violations
        """
        violations = []
        notes = []
        
        # Extract models from config
        slippage_model = backtest_config.get("slippage_model", "none")
        liquidity_model = backtest_config.get("liquidity_model", "unlimited")
        fill_model = backtest_config.get("fill_model", "instant")
        fee_model = backtest_config.get("fee_model", "none")
        
        # 1. Check slippage
        slippage_violations = self._check_slippage(backtest_config)
        violations.extend(slippage_violations)
        
        # 2. Check liquidity assumptions
        liquidity_violations = self._check_liquidity(backtest_config, trades, market_data)
        violations.extend(liquidity_violations)
        
        # 3. Check fill assumptions
        fill_violations = self._check_fills(backtest_config, trades)
        violations.extend(fill_violations)
        
        # 4. Check fee model
        fee_violations = self._check_fees(backtest_config)
        violations.extend(fee_violations)
        
        # 5. Check market impact
        if self.config.get("market_impact_enabled", True):
            impact_violations = self._check_market_impact(backtest_config, trades)
            violations.extend(impact_violations)
        
        # Calculate realism score
        realistic_score = self._calculate_realism_score(
            slippage_model, liquidity_model, fill_model, fee_model, violations
        )
        
        # Generate notes
        if realistic_score >= 0.8:
            notes.append("Execution assumptions are realistic")
        elif realistic_score >= 0.5:
            notes.append("Execution assumptions have some gaps - review suggested")
        else:
            notes.append("Execution assumptions are unrealistic - results may be inflated")
        
        return ExecutionCheckResult(
            passed=len([v for v in violations if v.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]) == 0,
            violations=violations,
            slippage_model=slippage_model,
            liquidity_model=liquidity_model,
            fill_model=fill_model,
            fee_model=fee_model,
            realistic_score=realistic_score,
            notes=notes
        )
    
    def _check_slippage(self, config: Dict[str, Any]) -> List[Violation]:
        """Check slippage model"""
        violations = []
        
        slippage_bps = config.get("slippage_bps", 0)
        slippage_model = config.get("slippage_model", "none")
        
        min_slippage = self.config.get("min_slippage_bps", 5)
        max_slippage = self.config.get("max_slippage_bps", 50)
        
        if slippage_model == "none" or slippage_bps == 0:
            violations.append(Violation(
                type=ViolationType.EXECUTION_ZERO_SLIPPAGE,
                severity=SeverityLevel.HIGH,
                message="Zero slippage assumption is unrealistic",
                details={
                    "current_slippage_bps": slippage_bps,
                    "recommended_min_bps": min_slippage
                },
                suggestion=f"Add at least {min_slippage} bps slippage for realistic results"
            ))
        elif slippage_bps < min_slippage:
            violations.append(Violation(
                type=ViolationType.EXECUTION_ZERO_SLIPPAGE,
                severity=SeverityLevel.MEDIUM,
                message=f"Slippage of {slippage_bps} bps may be too optimistic",
                details={
                    "current_slippage_bps": slippage_bps,
                    "recommended_min_bps": min_slippage
                },
                suggestion=f"Consider increasing slippage to at least {min_slippage} bps"
            ))
        
        return violations
    
    def _check_liquidity(
        self, 
        config: Dict[str, Any],
        trades: Optional[List[Dict[str, Any]]],
        market_data: Optional[Dict[str, Any]]
    ) -> List[Violation]:
        """Check liquidity assumptions"""
        violations = []
        
        liquidity_model = config.get("liquidity_model", "unlimited")
        
        if liquidity_model == "unlimited":
            violations.append(Violation(
                type=ViolationType.EXECUTION_UNLIMITED_LIQUIDITY,
                severity=SeverityLevel.MEDIUM,
                message="Unlimited liquidity assumption may not hold for large positions",
                details={"current_model": liquidity_model},
                suggestion="Model liquidity based on average daily volume"
            ))
        
        # Check trade sizes vs market capacity
        if trades and market_data:
            adv = market_data.get("average_daily_volume", 0)
            max_pct_adv = self.config.get("max_position_pct_adv", 5)
            
            for trade in trades:
                trade_size = trade.get("size", 0)
                if adv > 0:
                    pct_adv = (trade_size / adv) * 100
                    if pct_adv > max_pct_adv:
                        violations.append(Violation(
                            type=ViolationType.EXECUTION_UNLIMITED_LIQUIDITY,
                            severity=SeverityLevel.HIGH,
                            message=f"Trade size {pct_adv:.1f}% of ADV exceeds safe limit of {max_pct_adv}%",
                            details={
                                "trade_size": trade_size,
                                "adv": adv,
                                "pct_adv": round(pct_adv, 2),
                                "limit": max_pct_adv
                            },
                            suggestion="Reduce position size or model partial fills"
                        ))
                        break  # Only report first violation
        
        return violations
    
    def _check_fills(
        self, 
        config: Dict[str, Any],
        trades: Optional[List[Dict[str, Any]]]
    ) -> List[Violation]:
        """Check fill assumptions"""
        violations = []
        
        fill_model = config.get("fill_model", "instant")
        fill_delay_ms = config.get("fill_delay_ms", 0)
        min_delay = self.config.get("min_fill_delay_ms", 50)
        
        if fill_model == "instant" or fill_delay_ms < min_delay:
            violations.append(Violation(
                type=ViolationType.EXECUTION_INSTANT_FILL,
                severity=SeverityLevel.MEDIUM,
                message="Instant fill assumption ignores execution latency",
                details={
                    "current_delay_ms": fill_delay_ms,
                    "recommended_min_ms": min_delay
                },
                suggestion=f"Add at least {min_delay}ms fill delay to account for execution latency"
            ))
        
        # Check fill rate assumptions
        fill_rate = config.get("fill_rate", 1.0)
        if fill_rate == 1.0:
            violations.append(Violation(
                type=ViolationType.EXECUTION_INSTANT_FILL,
                severity=SeverityLevel.LOW,
                message="100% fill rate assumes all limit orders are filled",
                details={"fill_rate": fill_rate},
                suggestion="Consider 80-95% fill rate for limit orders"
            ))
        
        return violations
    
    def _check_fees(self, config: Dict[str, Any]) -> List[Violation]:
        """Check fee model"""
        violations = []
        
        fee_model = config.get("fee_model", "none")
        fee_bps = config.get("fee_bps", 0)
        
        min_fee = self.config.get("min_fee_bps", 1)
        max_fee = self.config.get("max_fee_bps", 30)
        
        if fee_model == "none" or fee_bps == 0:
            violations.append(Violation(
                type=ViolationType.EXECUTION_UNREALISTIC_FEES,
                severity=SeverityLevel.HIGH,
                message="Zero fees assumption inflates profitability",
                details={
                    "current_fee_bps": fee_bps,
                    "recommended_min_bps": min_fee
                },
                suggestion=f"Add at least {min_fee} bps fees (typical range: {min_fee}-{max_fee} bps)"
            ))
        elif fee_bps < min_fee:
            violations.append(Violation(
                type=ViolationType.EXECUTION_UNREALISTIC_FEES,
                severity=SeverityLevel.LOW,
                message=f"Fee of {fee_bps} bps is below typical minimum",
                details={
                    "current_fee_bps": fee_bps,
                    "typical_range": f"{min_fee}-{max_fee} bps"
                },
                suggestion="Verify fee structure matches actual trading costs"
            ))
        
        return violations
    
    def _check_market_impact(
        self, 
        config: Dict[str, Any],
        trades: Optional[List[Dict[str, Any]]]
    ) -> List[Violation]:
        """Check market impact modeling"""
        violations = []
        
        impact_model = config.get("market_impact_model", "none")
        
        if impact_model == "none":
            violations.append(Violation(
                type=ViolationType.EXECUTION_NO_MARKET_IMPACT,
                severity=SeverityLevel.MEDIUM,
                message="No market impact model - large orders may move price adversely",
                details={"current_model": impact_model},
                suggestion="Add square-root or linear market impact model"
            ))
        
        return violations
    
    def _calculate_realism_score(
        self,
        slippage_model: str,
        liquidity_model: str,
        fill_model: str,
        fee_model: str,
        violations: List[Violation]
    ) -> float:
        """Calculate overall realism score"""
        score = 1.0
        
        # Penalty for violations by severity
        for v in violations:
            if v.severity == SeverityLevel.CRITICAL:
                score -= 0.25
            elif v.severity == SeverityLevel.HIGH:
                score -= 0.15
            elif v.severity == SeverityLevel.MEDIUM:
                score -= 0.08
            elif v.severity == SeverityLevel.LOW:
                score -= 0.03
        
        # Bonus for realistic models
        if slippage_model not in ["none", ""]:
            score += 0.05
        if liquidity_model not in ["unlimited", ""]:
            score += 0.05
        if fee_model not in ["none", ""]:
            score += 0.05
        
        return max(0.0, min(1.0, round(score, 4)))
    
    def get_recommended_config(
        self, 
        asset_type: str = "crypto",
        strategy_type: str = "trend"
    ) -> Dict[str, Any]:
        """
        Get recommended execution configuration for asset/strategy type.
        """
        configs = {
            "crypto": {
                "slippage_bps": 15,
                "fee_bps": 10,
                "fill_delay_ms": 100,
                "fill_rate": 0.95,
                "market_impact_model": "square_root",
                "liquidity_model": "adv_based"
            },
            "equity": {
                "slippage_bps": 5,
                "fee_bps": 1,
                "fill_delay_ms": 50,
                "fill_rate": 0.90,
                "market_impact_model": "linear",
                "liquidity_model": "adv_based"
            },
            "forex": {
                "slippage_bps": 3,
                "fee_bps": 2,
                "fill_delay_ms": 30,
                "fill_rate": 0.98,
                "market_impact_model": "none",
                "liquidity_model": "unlimited"
            }
        }
        
        base_config = configs.get(asset_type, configs["crypto"])
        
        # Adjust for strategy type
        if strategy_type == "hft":
            base_config["fill_delay_ms"] = max(10, base_config["fill_delay_ms"] // 2)
        elif strategy_type == "swing":
            base_config["slippage_bps"] = min(50, base_config["slippage_bps"] * 2)
        
        return base_config
    
    def estimate_cost_drag(
        self,
        trades_per_year: int,
        avg_trade_size: float,
        fee_bps: float,
        slippage_bps: float
    ) -> Dict[str, Any]:
        """
        Estimate the performance drag from execution costs.
        """
        # Total cost per trade in bps
        cost_per_trade_bps = fee_bps + slippage_bps
        
        # Annual cost (assumes round-trip)
        annual_cost_bps = trades_per_year * cost_per_trade_bps * 2
        annual_cost_pct = annual_cost_bps / 100
        
        return {
            "cost_per_trade_bps": round(cost_per_trade_bps, 2),
            "annual_cost_bps": round(annual_cost_bps, 2),
            "annual_cost_pct": round(annual_cost_pct, 2),
            "trades_per_year": trades_per_year,
            "breakeven_edge_pct": round(annual_cost_pct, 2),
            "recommendation": f"Strategy needs >{annual_cost_pct:.1f}% annual edge to be profitable after costs"
        }
