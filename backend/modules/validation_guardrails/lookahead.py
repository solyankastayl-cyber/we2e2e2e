"""
Phase 8.0: Lookahead Bias Detector
Detects use of future information in trading signals
"""
from typing import Dict, List, Optional, Any, Set
import time
from .types import (
    LookaheadCheckResult,
    Violation,
    ViolationType,
    SeverityLevel,
    GUARDRAILS_CONFIG,
    LOOKAHEAD_RISK_FIELDS
)


class LookaheadDetector:
    """
    Detects lookahead bias in trading strategies and backtests.
    
    Lookahead bias occurs when a strategy uses information that
    would not have been available at the time of the decision.
    
    Common sources:
    1. Using close price before bar closes
    2. Using daily high/low before day ends
    3. Using indicators before they're calculated
    4. Using future events (earnings, news)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or GUARDRAILS_CONFIG.get("lookahead", {})
        self.risk_fields = LOOKAHEAD_RISK_FIELDS
        
    def check(
        self, 
        signals: List[Dict[str, Any]],
        price_data: Optional[List[Dict[str, Any]]] = None,
        strategy_rules: Optional[Dict[str, Any]] = None
    ) -> LookaheadCheckResult:
        """
        Check for lookahead bias in a set of signals.
        
        Args:
            signals: List of trading signals with timestamps and data used
            price_data: Historical price data for cross-reference
            strategy_rules: Strategy rules to check for lookahead risks
            
        Returns:
            LookaheadCheckResult with violations
        """
        violations = []
        fields_checked = set()
        notes = []
        future_data_detected = False
        
        # 1. Check signal timestamps vs data timestamps
        if signals:
            ts_violations = self._check_timestamp_alignment(signals, price_data)
            violations.extend(ts_violations)
            if ts_violations:
                future_data_detected = True
        
        # 2. Check for high-risk field usage
        if strategy_rules:
            field_violations = self._check_field_usage(strategy_rules)
            violations.extend(field_violations)
            fields_checked.update(self._extract_fields(strategy_rules))
        
        # 3. Check indicator calculation timing
        if self.config.get("check_indicators", True):
            indicator_violations = self._check_indicator_timing(signals)
            violations.extend(indicator_violations)
        
        # 4. Check for settlement price usage
        if self.config.get("check_settlement", True):
            settlement_violations = self._check_settlement_usage(signals, price_data)
            violations.extend(settlement_violations)
            if settlement_violations:
                future_data_detected = True
        
        # Generate notes
        if not violations:
            notes.append("No lookahead bias detected")
        else:
            critical = len([v for v in violations if v.severity == SeverityLevel.CRITICAL])
            if critical > 0:
                notes.append(f"CRITICAL: {critical} lookahead violations invalidate backtest results")
            notes.append(f"Total violations: {len(violations)}")
        
        return LookaheadCheckResult(
            passed=len([v for v in violations if v.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]) == 0,
            violations=violations,
            fields_checked=list(fields_checked),
            timestamps_analyzed=len(signals) if signals else 0,
            future_data_detected=future_data_detected,
            notes=notes
        )
    
    def _check_timestamp_alignment(
        self, 
        signals: List[Dict[str, Any]],
        price_data: Optional[List[Dict[str, Any]]]
    ) -> List[Violation]:
        """Check if signals use data from future timestamps"""
        violations = []
        
        if not price_data:
            return violations
            
        # Build price timestamp index
        price_timestamps = {p.get("timestamp"): p for p in price_data if "timestamp" in p}
        
        for signal in signals:
            signal_ts = signal.get("timestamp")
            data_ts = signal.get("data_timestamp")
            
            if signal_ts and data_ts and data_ts > signal_ts:
                violations.append(Violation(
                    type=ViolationType.LOOKAHEAD_FUTURE_PRICE,
                    severity=SeverityLevel.CRITICAL,
                    message=f"Signal at {signal_ts} uses data from future timestamp {data_ts}",
                    timestamp_affected=signal_ts,
                    details={
                        "signal_timestamp": signal_ts,
                        "data_timestamp": data_ts,
                        "delta_ms": data_ts - signal_ts
                    },
                    suggestion="Ensure signals only use data available at decision time"
                ))
            
            # Check if signal uses close price before bar closes
            if signal.get("uses_close") and signal.get("bar_incomplete"):
                violations.append(Violation(
                    type=ViolationType.LOOKAHEAD_SETTLEMENT_PRICE,
                    severity=SeverityLevel.CRITICAL,
                    message="Signal uses close price before bar settlement",
                    timestamp_affected=signal_ts,
                    data_field="close",
                    suggestion="Use open price or previous bar's close for incomplete bars"
                ))
        
        return violations
    
    def _check_field_usage(
        self, 
        strategy_rules: Dict[str, Any]
    ) -> List[Violation]:
        """Check for use of high-risk fields that may cause lookahead"""
        violations = []
        
        required_fields = strategy_rules.get("required_fields", [])
        entry_fields = strategy_rules.get("entry_conditions", {}).get("fields", [])
        all_fields = set(required_fields + entry_fields)
        
        # Check high risk fields
        high_risk = set(self.risk_fields.get("high_risk", []))
        risky_used = all_fields & high_risk
        
        for field in risky_used:
            violations.append(Violation(
                type=ViolationType.LOOKAHEAD_FUTURE_PRICE,
                severity=SeverityLevel.MEDIUM,
                message=f"Strategy uses high-risk field '{field}' which may cause lookahead bias",
                data_field=field,
                details={"field": field, "risk_level": "high"},
                suggestion=f"Verify '{field}' is available at signal time, consider using lagged value"
            ))
        
        return violations
    
    def _check_indicator_timing(
        self, 
        signals: List[Dict[str, Any]]
    ) -> List[Violation]:
        """Check if indicators are used before they can be calculated"""
        violations = []
        indicator_lags = self.risk_fields.get("indicator_lag", {})
        
        for signal in signals:
            indicators_used = signal.get("indicators", {})
            bar_index = signal.get("bar_index", 0)
            
            for indicator, lag in indicator_lags.items():
                if indicator in indicators_used and bar_index < lag:
                    violations.append(Violation(
                        type=ViolationType.LOOKAHEAD_FUTURE_INDICATOR,
                        severity=SeverityLevel.HIGH,
                        message=f"Indicator '{indicator}' used at bar {bar_index} requires {lag} bars of history",
                        data_field=indicator,
                        timestamp_affected=signal.get("timestamp"),
                        details={
                            "indicator": indicator,
                            "required_bars": lag,
                            "current_bar": bar_index
                        },
                        suggestion=f"Wait until bar {lag} to use '{indicator}' or use alternative"
                    ))
        
        return violations
    
    def _check_settlement_usage(
        self, 
        signals: List[Dict[str, Any]],
        price_data: Optional[List[Dict[str, Any]]]
    ) -> List[Violation]:
        """Check for use of settlement prices before settlement time"""
        violations = []
        
        for signal in signals:
            # Check if signal uses same-bar close
            if signal.get("entry_price_type") == "close":
                violations.append(Violation(
                    type=ViolationType.LOOKAHEAD_SETTLEMENT_PRICE,
                    severity=SeverityLevel.HIGH,
                    message="Entry at close price assumes knowledge of settlement before it occurs",
                    timestamp_affected=signal.get("timestamp"),
                    details={
                        "entry_type": "close",
                        "signal_bar": signal.get("bar_index")
                    },
                    suggestion="Use next bar open or limit order at estimated price"
                ))
            
            # Check for daily high/low usage intraday
            if signal.get("timeframe") in ["1m", "5m", "15m", "30m", "1h"]:
                if signal.get("uses_daily_high") or signal.get("uses_daily_low"):
                    violations.append(Violation(
                        type=ViolationType.LOOKAHEAD_FUTURE_PRICE,
                        severity=SeverityLevel.HIGH,
                        message="Intraday signal uses daily high/low before day ends",
                        timestamp_affected=signal.get("timestamp"),
                        suggestion="Use running high/low up to current time only"
                    ))
        
        return violations
    
    def _extract_fields(self, strategy_rules: Dict[str, Any]) -> Set[str]:
        """Extract all fields used in strategy rules"""
        fields = set()
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in ["field", "data_field", "indicator"]:
                        fields.add(v)
                    extract_recursive(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
        
        extract_recursive(strategy_rules)
        return fields
    
    def quick_check(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Quick lookahead check for a strategy without detailed analysis.
        Returns risk assessment.
        """
        rules = strategy.get("rules", {})
        required = rules.get("required", [])
        
        high_risk = self.risk_fields.get("high_risk", [])
        medium_risk = self.risk_fields.get("medium_risk", [])
        
        high_risk_count = len(set(required) & set(high_risk))
        medium_risk_count = len(set(required) & set(medium_risk))
        
        risk_score = (high_risk_count * 0.3 + medium_risk_count * 0.1)
        risk_level = "LOW"
        if risk_score > 0.5:
            risk_level = "HIGH"
        elif risk_score > 0.2:
            risk_level = "MEDIUM"
        
        return {
            "risk_level": risk_level,
            "risk_score": round(risk_score, 3),
            "high_risk_fields": high_risk_count,
            "medium_risk_fields": medium_risk_count,
            "recommendation": "Review data timestamps" if risk_score > 0.2 else "Low lookahead risk"
        }
