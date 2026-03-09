"""
Phase 8.0: Type definitions for Validation Guardrails
"""
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import time


class ViolationType(str, Enum):
    """Types of guardrail violations"""
    # Lookahead violations
    LOOKAHEAD_FUTURE_PRICE = "LOOKAHEAD_FUTURE_PRICE"
    LOOKAHEAD_FUTURE_INDICATOR = "LOOKAHEAD_FUTURE_INDICATOR"
    LOOKAHEAD_FUTURE_EVENT = "LOOKAHEAD_FUTURE_EVENT"
    LOOKAHEAD_SETTLEMENT_PRICE = "LOOKAHEAD_SETTLEMENT_PRICE"
    
    # Data snooping violations
    SNOOPING_MULTIPLE_TESTING = "SNOOPING_MULTIPLE_TESTING"
    SNOOPING_PARAMETER_OPTIMIZATION = "SNOOPING_PARAMETER_OPTIMIZATION"
    SNOOPING_CHERRY_PICKING = "SNOOPING_CHERRY_PICKING"
    SNOOPING_SURVIVORSHIP_BIAS = "SNOOPING_SURVIVORSHIP_BIAS"
    
    # Execution assumption violations
    EXECUTION_ZERO_SLIPPAGE = "EXECUTION_ZERO_SLIPPAGE"
    EXECUTION_UNLIMITED_LIQUIDITY = "EXECUTION_UNLIMITED_LIQUIDITY"
    EXECUTION_INSTANT_FILL = "EXECUTION_INSTANT_FILL"
    EXECUTION_NO_MARKET_IMPACT = "EXECUTION_NO_MARKET_IMPACT"
    EXECUTION_UNREALISTIC_FEES = "EXECUTION_UNREALISTIC_FEES"


class SeverityLevel(str, Enum):
    """Severity of violations"""
    CRITICAL = "CRITICAL"    # Must fix, invalidates results
    HIGH = "HIGH"            # Strongly recommended to fix
    MEDIUM = "MEDIUM"        # Should fix for production
    LOW = "LOW"              # Informational, minor impact
    INFO = "INFO"            # Suggestion only


@dataclass
class Violation:
    """A single guardrail violation"""
    type: ViolationType
    severity: SeverityLevel
    message: str
    location: Optional[str] = None  # File/function/line where violation occurs
    timestamp_affected: Optional[int] = None  # Time point where violation happened
    data_field: Optional[str] = None  # Field that caused violation
    details: Dict[str, Any] = field(default_factory=dict)
    suggestion: Optional[str] = None


@dataclass
class LookaheadCheckResult:
    """Result of lookahead bias detection"""
    passed: bool
    violations: List[Violation] = field(default_factory=list)
    fields_checked: List[str] = field(default_factory=list)
    timestamps_analyzed: int = 0
    future_data_detected: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class SnoopingCheckResult:
    """Result of data snooping detection"""
    passed: bool
    violations: List[Violation] = field(default_factory=list)
    hypothesis_count: int = 0
    adjusted_significance: float = 0.05  # After Bonferroni/BH correction
    effective_tests: int = 0
    multiple_testing_penalty: float = 0.0
    notes: List[str] = field(default_factory=list)


@dataclass
class ExecutionCheckResult:
    """Result of execution assumptions validation"""
    passed: bool
    violations: List[Violation] = field(default_factory=list)
    slippage_model: str = "none"
    liquidity_model: str = "unlimited"
    fill_model: str = "instant"
    fee_model: str = "none"
    realistic_score: float = 0.0  # 0-1, how realistic assumptions are
    notes: List[str] = field(default_factory=list)


@dataclass
class GuardrailsReport:
    """Complete guardrails validation report"""
    passed: bool
    overall_score: float  # 0-1, confidence in validation integrity
    lookahead_check: LookaheadCheckResult
    snooping_check: SnoopingCheckResult
    execution_check: ExecutionCheckResult
    total_violations: int = 0
    critical_violations: int = 0
    high_violations: int = 0
    recommendations: List[str] = field(default_factory=list)
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))


# Configuration thresholds
GUARDRAILS_CONFIG = {
    # Lookahead detection
    "lookahead": {
        "max_future_window": 0,  # No future data allowed by default
        "check_indicators": True,
        "check_prices": True,
        "check_events": True,
        "check_settlement": True,
    },
    
    # Data snooping protection
    "snooping": {
        "max_hypotheses_without_correction": 5,
        "significance_level": 0.05,
        "correction_method": "bonferroni",  # bonferroni, holm, benjamini-hochberg
        "min_out_of_sample_ratio": 0.3,  # 30% data for OOS testing
        "max_parameter_combinations": 100,
        "require_walk_forward": True,
    },
    
    # Execution realism
    "execution": {
        "min_slippage_bps": 5,  # 0.05% minimum slippage
        "max_slippage_bps": 50,  # 0.5% maximum reasonable slippage
        "default_slippage_bps": 10,  # 0.1% default
        "min_fill_delay_ms": 50,  # 50ms minimum fill delay
        "max_position_pct_adv": 5,  # Max 5% of average daily volume
        "min_fee_bps": 1,  # 0.01% minimum fees
        "max_fee_bps": 30,  # 0.3% maximum reasonable fees
        "default_fee_bps": 10,  # 0.1% default
        "market_impact_enabled": True,
    },
    
    # Overall thresholds
    "thresholds": {
        "pass_score": 0.7,  # 70% to pass overall
        "lookahead_weight": 0.4,  # Most important
        "snooping_weight": 0.35,
        "execution_weight": 0.25,
    }
}


# Fields that commonly cause lookahead bias
LOOKAHEAD_RISK_FIELDS = {
    "high_risk": [
        "close",  # Settlement price
        "high",   # Daily high
        "low",    # Daily low
        "volume", # End of period volume
        "vwap",   # Volume weighted average price
        "settlement_price",
        "final_price",
    ],
    "medium_risk": [
        "rsi",    # Indicators use close
        "macd",   # Uses close
        "ema",    # Uses close
        "sma",    # Uses close
        "atr",    # Uses high/low/close
        "bb_upper", "bb_lower",  # Bollinger bands
    ],
    "indicator_lag": {
        "rsi": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "ema_20": 20,
        "sma_50": 50,
        "atr": 14,
    }
}
