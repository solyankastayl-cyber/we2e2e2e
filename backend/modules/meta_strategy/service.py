"""
Phase 9.27: Meta-Strategy Layer
================================

Надслой управления портфелем стратегий как портфелем альф.

Решает не "входить или не входить", а:
"какой стратегии сейчас доверять капитал, в каком объёме, в каком режиме и на каком активе"

Компоненты:
1. StrategyScoringEngine — расчёт meta-score по стратегиям
2. StrategyWeightAllocator — динамическое взвешивание
3. StrategyFamilyManager — управление семействами стратегий
4. CrowdingDetector — детекция overlap сигналов/трейдов
5. StrategyAdmissionEngine — финальный admission check
6. TierAllocator — Core/Tactical/Experimental split

Pipeline:
Market Regime → Strategy Lifecycle → Self-Healing Status → Meta-Strategy Scoring
→ Family Allocation → Crowding Control → Final Strategy Weight → Execution

API:
- GET  /api/meta-strategy/health
- GET  /api/meta-strategy/status
- GET  /api/meta-strategy/weights
- GET  /api/meta-strategy/families
- GET  /api/meta-strategy/crowding
- GET  /api/meta-strategy/admission
- POST /api/meta-strategy/recompute
- POST /api/meta-strategy/admit
"""

import time
import math
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Types & Enums
# ═══════════════════════════════════════════════════════════════

class StrategyTier(str, Enum):
    """Strategy tier classification"""
    CORE = "CORE"
    TACTICAL = "TACTICAL"
    EXPERIMENTAL = "EXPERIMENTAL"


class StrategyFamily(str, Enum):
    """Strategy family types"""
    BREAKOUT = "breakout_family"
    CONTINUATION = "continuation_family"
    REVERSAL = "reversal_family"
    PATTERN = "pattern_family"
    HARMONIC = "harmonic_family"
    MACRO = "macro_family"
    EXPERIMENTAL = "experimental_family"


class AdmissionStatus(str, Enum):
    """Strategy admission status"""
    ADMITTED = "ADMITTED"
    LIMITED = "LIMITED"
    BLOCKED = "BLOCKED"


class CrowdingLevel(str, Enum):
    """Crowding severity"""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MetaStrategyStatus(str, Enum):
    """Overall meta-strategy status"""
    ACTIVE = "ACTIVE"
    LIMITED = "LIMITED"
    BLOCKED = "BLOCKED"


# ═══════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class StrategyScore:
    """Individual strategy scoring components"""
    strategy_id: str
    
    # Core scores (0.0 - 1.0+)
    edge_health: float = 1.0
    regime_fit: float = 1.0
    recent_performance: float = 1.0
    confidence_integrity: float = 1.0
    portfolio_fit: float = 1.0
    
    # Modifiers
    lifecycle_modifier: float = 1.0
    self_healing_modifier: float = 1.0
    crowding_penalty: float = 0.0
    
    # Base weight from governance
    base_weight: float = 1.0
    
    # Calculated final weight
    final_weight: float = 0.0
    
    # Meta info
    family: str = ""
    tier: str = "TACTICAL"
    regime: str = ""
    asset: str = ""
    
    # Status
    status: str = "ACTIVE"
    status_reason: str = ""
    
    computed_at: int = 0


@dataclass
class FamilyBudget:
    """Family allocation budget"""
    family: str
    target_weight: float
    current_weight: float
    max_weight: float
    strategy_count: int
    active_strategies: int
    
    # Per-regime overrides
    regime_targets: Dict[str, float] = field(default_factory=dict)


@dataclass
class CrowdingPair:
    """Crowding between two strategies"""
    strategy_a: str
    strategy_b: str
    
    signal_overlap: float = 0.0
    trade_overlap: float = 0.0
    outcome_correlation: float = 0.0
    feature_overlap: float = 0.0
    
    total_overlap: float = 0.0
    penalty: float = 0.0
    level: str = "NONE"


@dataclass
class CrowdingCluster:
    """Cluster of crowded strategies"""
    cluster_id: str
    strategies: List[str]
    avg_overlap: float
    total_penalty: float
    level: str


@dataclass
class AdmissionDecision:
    """Strategy admission decision"""
    strategy_id: str
    signal_id: str
    
    admitted: bool
    status: str
    final_weight: float
    
    checks: Dict[str, bool] = field(default_factory=dict)
    reason: str = ""
    
    timestamp: int = 0


@dataclass
class TierAllocation:
    """Tier-based allocation"""
    tier: str
    budget: float
    current: float
    remaining: float
    strategy_count: int


@dataclass
class MetaStrategyState:
    """Full meta-strategy state"""
    # Overall status
    status: str = "ACTIVE"
    
    # Strategy weights
    strategy_scores: Dict[str, StrategyScore] = field(default_factory=dict)
    
    # Family allocations
    family_budgets: Dict[str, FamilyBudget] = field(default_factory=dict)
    
    # Tier allocations
    tier_allocations: Dict[str, TierAllocation] = field(default_factory=dict)
    
    # Crowding
    crowding_pairs: List[CrowdingPair] = field(default_factory=list)
    crowding_clusters: List[CrowdingCluster] = field(default_factory=list)
    
    # Recent admissions
    recent_admissions: List[AdmissionDecision] = field(default_factory=list)
    
    # Current regime
    current_regime: str = "RANGE"
    
    # Timestamps
    last_recompute: int = 0
    computed_at: int = 0


# ═══════════════════════════════════════════════════════════════
# Default Configuration
# ═══════════════════════════════════════════════════════════════

DEFAULT_META_STRATEGY_CONFIG = {
    # Tier budgets
    "tier_budgets": {
        "CORE": 0.60,
        "TACTICAL": 0.30,
        "EXPERIMENTAL": 0.10
    },
    
    # Family budgets (default)
    "family_budgets": {
        "breakout_family": {
            "default": 0.30,
            "TREND_UP": 0.35,
            "TREND_DOWN": 0.25,
            "RANGE": 0.10,
            "COMPRESSION": 0.20
        },
        "continuation_family": {
            "default": 0.25,
            "TREND_UP": 0.35,
            "TREND_DOWN": 0.30,
            "RANGE": 0.10
        },
        "reversal_family": {
            "default": 0.20,
            "RANGE": 0.35,
            "COMPRESSION": 0.25,
            "TREND_UP": 0.10,
            "TREND_DOWN": 0.10
        },
        "pattern_family": {
            "default": 0.15,
            "RANGE": 0.30,
            "COMPRESSION": 0.20
        },
        "harmonic_family": {
            "default": 0.05,
            "RANGE": 0.10
        },
        "macro_family": {
            "default": 0.05
        },
        "experimental_family": {
            "default": 0.10
        }
    },
    
    # Crowding thresholds
    "crowding": {
        "low_threshold": 0.20,
        "medium_threshold": 0.40,
        "high_threshold": 0.60,
        "critical_threshold": 0.80,
        "penalties": {
            "LOW": 0.05,
            "MEDIUM": 0.15,
            "HIGH": 0.30,
            "CRITICAL": 0.50
        }
    },
    
    # Admission thresholds
    "admission": {
        "min_health": 0.40,
        "min_regime_fit": 0.30,
        "min_final_weight": 0.10,
        "max_family_weight": 0.40,
        "max_strategy_weight": 0.20,
        "max_concurrent_per_family": 5
    },
    
    # Scoring weights
    "scoring_weights": {
        "edge_health": 1.0,
        "regime_fit": 1.0,
        "recent_performance": 0.8,
        "confidence_integrity": 0.7,
        "portfolio_fit": 0.9
    },
    
    # Weight bounds
    "weight_bounds": {
        "min": 0.0,
        "max": 1.5
    }
}


# ═══════════════════════════════════════════════════════════════
# Strategy Scoring Engine
# ═══════════════════════════════════════════════════════════════

class StrategyScoringEngine:
    """
    Calculates meta-score for each strategy.
    
    Inputs:
    - Edge health from EdgeDecayMonitor / Self-Healing
    - Regime fit from activation map
    - Recent performance (rolling PF)
    - Confidence integrity
    - Portfolio fit
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or DEFAULT_META_STRATEGY_CONFIG
    
    def score_strategy(
        self,
        strategy_id: str,
        strategy_data: Dict,
        regime: str = "RANGE",
        portfolio_state: Optional[Dict] = None
    ) -> StrategyScore:
        """Calculate complete score for a strategy"""
        
        # Extract components
        edge_health = self._calc_edge_health(strategy_data)
        regime_fit = self._calc_regime_fit(strategy_data, regime)
        recent_perf = self._calc_recent_performance(strategy_data)
        confidence = self._calc_confidence_integrity(strategy_data)
        portfolio_fit = self._calc_portfolio_fit(strategy_data, portfolio_state)
        
        # Get modifiers
        lifecycle_mod = self._get_lifecycle_modifier(strategy_data)
        healing_mod = self._get_self_healing_modifier(strategy_data)
        
        # Get base weight
        base_weight = strategy_data.get("base_weight", 1.0)
        
        # Calculate final weight (crowding applied later)
        final_weight = self._calc_final_weight(
            base_weight,
            edge_health,
            regime_fit,
            recent_perf,
            confidence,
            portfolio_fit,
            lifecycle_mod,
            healing_mod,
            crowding_penalty=0.0
        )
        
        return StrategyScore(
            strategy_id=strategy_id,
            edge_health=edge_health,
            regime_fit=regime_fit,
            recent_performance=recent_perf,
            confidence_integrity=confidence,
            portfolio_fit=portfolio_fit,
            lifecycle_modifier=lifecycle_mod,
            self_healing_modifier=healing_mod,
            crowding_penalty=0.0,
            base_weight=base_weight,
            final_weight=final_weight,
            family=strategy_data.get("family", "experimental_family"),
            tier=strategy_data.get("tier", "TACTICAL"),
            regime=regime,
            asset=strategy_data.get("asset", ""),
            status="ACTIVE" if final_weight > 0.1 else "LIMITED",
            computed_at=int(time.time() * 1000)
        )
    
    def _calc_edge_health(self, data: Dict) -> float:
        """
        Calculate edge health score.
        
        Sources: EdgeDecayMonitor, Self-Healing health
        """
        health_verdict = data.get("health_verdict", "HEALTHY")
        health_score = data.get("health_score", 0.8)
        
        # Map verdict to multiplier
        verdict_map = {
            "HEALTHY": 1.00,
            "WARNING": 0.80,
            "DEGRADED": 0.50,
            "CRITICAL": 0.20
        }
        
        base = verdict_map.get(health_verdict, 0.80)
        
        # Blend with actual score
        return (base + health_score) / 2
    
    def _calc_regime_fit(self, data: Dict, regime: str) -> float:
        """
        Calculate regime fit score.
        
        Source: activation map
        """
        activation_map = data.get("activation_map", {})
        activation = activation_map.get(regime, "LIMITED")
        
        fit_map = {
            "ON": 1.00,
            "LIMITED": 0.50,
            "WATCH": 0.20,
            "OFF": 0.00
        }
        
        return fit_map.get(activation, 0.50)
    
    def _calc_recent_performance(self, data: Dict) -> float:
        """
        Calculate recent performance multiplier.
        
        Based on rolling profit factor
        """
        rolling_pf = data.get("rolling_pf", 1.2)
        rolling_wr = data.get("rolling_wr", 0.55)
        
        # PF score
        if rolling_pf >= 1.4:
            pf_score = 1.10
        elif rolling_pf >= 1.1:
            pf_score = 1.00
        elif rolling_pf >= 0.9:
            pf_score = 0.80
        else:
            pf_score = 0.50
        
        # WR bonus
        wr_bonus = 0.0
        if rolling_wr >= 0.60:
            wr_bonus = 0.05
        elif rolling_wr >= 0.55:
            wr_bonus = 0.02
        
        return min(1.15, pf_score + wr_bonus)
    
    def _calc_confidence_integrity(self, data: Dict) -> float:
        """
        Calculate confidence calibration score.
        
        Good calibration = confidence matches actual hit rate
        """
        calibration_score = data.get("calibration_score", 0.8)
        brier_score = data.get("brier_score", 0.2)
        
        # Lower Brier is better
        brier_factor = 1.0 - min(0.4, brier_score)
        
        return (calibration_score + brier_factor) / 2
    
    def _calc_portfolio_fit(self, data: Dict, portfolio_state: Optional[Dict]) -> float:
        """
        Calculate portfolio fit score.
        
        Penalizes concentration and correlation
        """
        if not portfolio_state:
            return 1.0
        
        strategy_id = data.get("strategy_id", "")
        family = data.get("family", "")
        asset = data.get("asset", "")
        
        # Check family concentration
        family_exposure = portfolio_state.get("family_exposures", {}).get(family, 0)
        max_family = self.config["admission"]["max_family_weight"]
        
        if family_exposure >= max_family:
            return 0.50
        elif family_exposure >= max_family * 0.8:
            return 0.70
        elif family_exposure >= max_family * 0.5:
            return 0.85
        
        return 1.0
    
    def _get_lifecycle_modifier(self, data: Dict) -> float:
        """Get lifecycle-based modifier"""
        lifecycle = data.get("lifecycle", "APPROVED")
        
        lifecycle_map = {
            "APPROVED": 1.00,
            "LIMITED": 0.70,
            "WATCH": 0.50,
            "TESTING": 0.30,
            "CANDIDATE": 0.20,
            "DEGRADED": 0.30,
            "DISABLED": 0.00,
            "DEPRECATED": 0.00
        }
        
        return lifecycle_map.get(lifecycle, 0.50)
    
    def _get_self_healing_modifier(self, data: Dict) -> float:
        """Get self-healing status modifier"""
        healing_status = data.get("healing_status", "HEALTHY")
        healing_weight = data.get("healing_weight", 1.0)
        
        # If self-healing has adjusted weight, use it
        if healing_weight < 1.0:
            return healing_weight
        
        status_map = {
            "HEALTHY": 1.00,
            "RECOVERING": 0.80,
            "DEGRADED": 0.60,
            "CRITICAL": 0.30
        }
        
        return status_map.get(healing_status, 0.80)
    
    def _calc_final_weight(
        self,
        base: float,
        edge: float,
        regime: float,
        perf: float,
        conf: float,
        portfolio: float,
        lifecycle: float,
        healing: float,
        crowding_penalty: float
    ) -> float:
        """Calculate final strategy weight"""
        
        weight = (
            base
            * edge
            * regime
            * perf
            * conf
            * portfolio
            * lifecycle
            * healing
            * (1 - crowding_penalty)
        )
        
        # Clamp to bounds
        bounds = self.config["weight_bounds"]
        return max(bounds["min"], min(bounds["max"], weight))


# ═══════════════════════════════════════════════════════════════
# Crowding Detector
# ═══════════════════════════════════════════════════════════════

class CrowdingDetector:
    """
    Detects crowding between strategies.
    
    Metrics:
    - Signal overlap: how often strategies signal simultaneously
    - Trade overlap: trade direction/timing similarity
    - Outcome correlation: PnL curve correlation
    - Feature overlap: shared feature basis
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = (config or DEFAULT_META_STRATEGY_CONFIG).get("crowding", {})
    
    def detect_pairwise(
        self,
        strategy_a: str,
        strategy_b: str,
        data_a: Dict,
        data_b: Dict
    ) -> CrowdingPair:
        """Calculate crowding between two strategies"""
        
        signal_overlap = self._calc_signal_overlap(data_a, data_b)
        trade_overlap = self._calc_trade_overlap(data_a, data_b)
        outcome_corr = self._calc_outcome_correlation(data_a, data_b)
        feature_overlap = self._calc_feature_overlap(data_a, data_b)
        
        # Weighted total
        total = (
            signal_overlap * 0.30 +
            trade_overlap * 0.25 +
            outcome_corr * 0.25 +
            feature_overlap * 0.20
        )
        
        level = self._get_level(total)
        penalty = self._get_penalty(level)
        
        return CrowdingPair(
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            signal_overlap=signal_overlap,
            trade_overlap=trade_overlap,
            outcome_correlation=outcome_corr,
            feature_overlap=feature_overlap,
            total_overlap=total,
            penalty=penalty,
            level=level
        )
    
    def detect_all(self, strategies: Dict[str, Dict]) -> Tuple[List[CrowdingPair], List[CrowdingCluster]]:
        """Detect crowding across all strategies"""
        pairs = []
        strategy_ids = list(strategies.keys())
        
        # Pairwise comparison
        for i, sid_a in enumerate(strategy_ids):
            for sid_b in strategy_ids[i+1:]:
                pair = self.detect_pairwise(
                    sid_a, sid_b,
                    strategies[sid_a],
                    strategies[sid_b]
                )
                if pair.total_overlap > self.config.get("low_threshold", 0.2):
                    pairs.append(pair)
        
        # Cluster detection
        clusters = self._detect_clusters(pairs, strategy_ids)
        
        return pairs, clusters
    
    def get_strategy_penalty(self, strategy_id: str, pairs: List[CrowdingPair]) -> float:
        """Get total crowding penalty for a strategy"""
        total_penalty = 0.0
        
        for pair in pairs:
            if pair.strategy_a == strategy_id or pair.strategy_b == strategy_id:
                total_penalty += pair.penalty
        
        # Cap at max penalty
        return min(0.50, total_penalty)
    
    def _calc_signal_overlap(self, data_a: Dict, data_b: Dict) -> float:
        """Calculate signal timing overlap"""
        signals_a = set(data_a.get("signal_times", []))
        signals_b = set(data_b.get("signal_times", []))
        
        if not signals_a or not signals_b:
            # Use feature-based estimation
            features_a = set(data_a.get("features", []))
            features_b = set(data_b.get("features", []))
            
            if not features_a or not features_b:
                return 0.0
            
            return len(features_a & features_b) / len(features_a | features_b)
        
        intersection = len(signals_a & signals_b)
        union = len(signals_a | signals_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _calc_trade_overlap(self, data_a: Dict, data_b: Dict) -> float:
        """Calculate trade direction/timing overlap"""
        trades_a = data_a.get("trade_directions", [])
        trades_b = data_b.get("trade_directions", [])
        
        if not trades_a or not trades_b:
            # Estimate from family similarity
            family_a = data_a.get("family", "")
            family_b = data_b.get("family", "")
            
            return 0.30 if family_a == family_b else 0.0
        
        # Count directional matches
        min_len = min(len(trades_a), len(trades_b))
        matches = sum(1 for i in range(min_len) if trades_a[i] == trades_b[i])
        
        return matches / min_len if min_len > 0 else 0.0
    
    def _calc_outcome_correlation(self, data_a: Dict, data_b: Dict) -> float:
        """Calculate PnL curve correlation"""
        pnl_a = data_a.get("pnl_curve", [])
        pnl_b = data_b.get("pnl_curve", [])
        
        if len(pnl_a) < 10 or len(pnl_b) < 10:
            # Estimate from performance metrics
            pf_a = data_a.get("rolling_pf", 1.0)
            pf_b = data_b.get("rolling_pf", 1.0)
            wr_a = data_a.get("rolling_wr", 0.5)
            wr_b = data_b.get("rolling_wr", 0.5)
            
            pf_sim = 1 - abs(pf_a - pf_b) / max(pf_a, pf_b)
            wr_sim = 1 - abs(wr_a - wr_b)
            
            return (pf_sim + wr_sim) / 2 * 0.5  # Scaled down
        
        # Simple correlation
        min_len = min(len(pnl_a), len(pnl_b))
        pnl_a = pnl_a[:min_len]
        pnl_b = pnl_b[:min_len]
        
        mean_a = sum(pnl_a) / len(pnl_a)
        mean_b = sum(pnl_b) / len(pnl_b)
        
        cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(pnl_a, pnl_b))
        var_a = sum((a - mean_a) ** 2 for a in pnl_a)
        var_b = sum((b - mean_b) ** 2 for b in pnl_b)
        
        if var_a == 0 or var_b == 0:
            return 0.0
        
        corr = cov / (math.sqrt(var_a) * math.sqrt(var_b))
        return max(0, corr)  # Only positive correlation counts
    
    def _calc_feature_overlap(self, data_a: Dict, data_b: Dict) -> float:
        """Calculate feature basis overlap"""
        features_a = set(data_a.get("features", []))
        features_b = set(data_b.get("features", []))
        
        if not features_a or not features_b:
            return 0.0
        
        intersection = len(features_a & features_b)
        union = len(features_a | features_b)
        
        return intersection / union if union > 0 else 0.0
    
    def _get_level(self, overlap: float) -> str:
        """Get crowding level from overlap"""
        if overlap >= self.config.get("critical_threshold", 0.80):
            return "CRITICAL"
        elif overlap >= self.config.get("high_threshold", 0.60):
            return "HIGH"
        elif overlap >= self.config.get("medium_threshold", 0.40):
            return "MEDIUM"
        elif overlap >= self.config.get("low_threshold", 0.20):
            return "LOW"
        return "NONE"
    
    def _get_penalty(self, level: str) -> float:
        """Get penalty from level"""
        penalties = self.config.get("penalties", {})
        return penalties.get(level, 0.0)
    
    def _detect_clusters(
        self,
        pairs: List[CrowdingPair],
        strategy_ids: List[str]
    ) -> List[CrowdingCluster]:
        """Detect clusters of crowded strategies"""
        clusters = []
        
        # Build adjacency from high-overlap pairs
        adjacency: Dict[str, set] = {sid: set() for sid in strategy_ids}
        
        for pair in pairs:
            if pair.total_overlap >= self.config.get("medium_threshold", 0.40):
                adjacency[pair.strategy_a].add(pair.strategy_b)
                adjacency[pair.strategy_b].add(pair.strategy_a)
        
        # Find connected components (simple BFS)
        visited = set()
        
        for start in strategy_ids:
            if start in visited or not adjacency[start]:
                continue
            
            # BFS
            cluster_members = []
            queue = [start]
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster_members.append(current)
                
                for neighbor in adjacency[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            
            if len(cluster_members) >= 2:
                # Calculate cluster metrics
                cluster_pairs = [
                    p for p in pairs
                    if p.strategy_a in cluster_members and p.strategy_b in cluster_members
                ]
                
                avg_overlap = (
                    sum(p.total_overlap for p in cluster_pairs) / len(cluster_pairs)
                    if cluster_pairs else 0
                )
                total_penalty = sum(p.penalty for p in cluster_pairs)
                
                clusters.append(CrowdingCluster(
                    cluster_id=f"cluster_{hashlib.md5(''.join(sorted(cluster_members)).encode()).hexdigest()[:8]}",
                    strategies=cluster_members,
                    avg_overlap=avg_overlap,
                    total_penalty=total_penalty,
                    level=self._get_level(avg_overlap)
                ))
        
        return clusters


# ═══════════════════════════════════════════════════════════════
# Strategy Family Manager
# ═══════════════════════════════════════════════════════════════

class StrategyFamilyManager:
    """
    Manages family-based allocation budgets.
    
    Features:
    - Baseline family budgets
    - Regime-sensitive allocation
    - Dynamic rebalancing
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = (config or DEFAULT_META_STRATEGY_CONFIG).get("family_budgets", {})
    
    def get_family_budget(self, family: str, regime: str = "RANGE") -> float:
        """Get target budget for family in regime"""
        family_config = self.config.get(family, {"default": 0.10})
        
        # Try regime-specific first
        if regime in family_config:
            return family_config[regime]
        
        return family_config.get("default", 0.10)
    
    def compute_family_allocations(
        self,
        strategy_scores: Dict[str, StrategyScore],
        regime: str = "RANGE"
    ) -> Dict[str, FamilyBudget]:
        """Compute current family allocations"""
        
        allocations: Dict[str, FamilyBudget] = {}
        
        # Initialize all families
        for family in StrategyFamily:
            target = self.get_family_budget(family.value, regime)
            allocations[family.value] = FamilyBudget(
                family=family.value,
                target_weight=target,
                current_weight=0.0,
                max_weight=min(0.40, target * 1.2),
                strategy_count=0,
                active_strategies=0,
                regime_targets=self.config.get(family.value, {})
            )
        
        # Aggregate strategy weights
        for score in strategy_scores.values():
            family = score.family or "experimental_family"
            
            if family not in allocations:
                allocations[family] = FamilyBudget(
                    family=family,
                    target_weight=0.10,
                    current_weight=0.0,
                    max_weight=0.15,
                    strategy_count=0,
                    active_strategies=0
                )
            
            allocations[family].strategy_count += 1
            allocations[family].current_weight += score.final_weight
            
            if score.status == "ACTIVE":
                allocations[family].active_strategies += 1
        
        return allocations
    
    def get_family_fit_modifier(
        self,
        family: str,
        current_allocation: float,
        regime: str = "RANGE"
    ) -> float:
        """Get modifier based on family budget status"""
        target = self.get_family_budget(family, regime)
        max_weight = min(0.40, target * 1.2)
        
        if current_allocation >= max_weight:
            return 0.30  # Heavy penalty
        elif current_allocation >= target:
            return 0.70  # Moderate penalty
        elif current_allocation >= target * 0.7:
            return 0.90  # Slight penalty
        
        return 1.0  # No penalty, room for more


# ═══════════════════════════════════════════════════════════════
# Tier Allocator
# ═══════════════════════════════════════════════════════════════

class TierAllocator:
    """
    Manages Core / Tactical / Experimental allocation.
    
    Budgets:
    - CORE: 60% - always active
    - TACTICAL: 30% - regime-dependent
    - EXPERIMENTAL: 10% - limited live exposure
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = (config or DEFAULT_META_STRATEGY_CONFIG).get("tier_budgets", {})
    
    def compute_tier_allocations(
        self,
        strategy_scores: Dict[str, StrategyScore]
    ) -> Dict[str, TierAllocation]:
        """Compute current tier allocations"""
        
        allocations = {}
        
        for tier in StrategyTier:
            budget = self.config.get(tier.value, 0.30)
            allocations[tier.value] = TierAllocation(
                tier=tier.value,
                budget=budget,
                current=0.0,
                remaining=budget,
                strategy_count=0
            )
        
        for score in strategy_scores.values():
            tier = score.tier or "TACTICAL"
            
            if tier in allocations:
                allocations[tier].current += score.final_weight
                allocations[tier].remaining = allocations[tier].budget - allocations[tier].current
                allocations[tier].strategy_count += 1
        
        return allocations
    
    def get_tier_modifier(self, tier: str, current_allocation: float) -> float:
        """Get modifier based on tier budget status"""
        budget = self.config.get(tier, 0.30)
        
        if current_allocation >= budget:
            return 0.50  # Heavy penalty
        elif current_allocation >= budget * 0.8:
            return 0.80  # Moderate penalty
        
        return 1.0


# ═══════════════════════════════════════════════════════════════
# Strategy Admission Engine
# ═══════════════════════════════════════════════════════════════

class StrategyAdmissionEngine:
    """
    Final admission check before execution.
    
    Checks:
    - Lifecycle status
    - Regime fit
    - Health score
    - Family budget
    - Portfolio concentration
    - Crowding level
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = (config or DEFAULT_META_STRATEGY_CONFIG).get("admission", {})
        self._recent_decisions: List[AdmissionDecision] = []
    
    def check_admission(
        self,
        strategy_id: str,
        signal_id: str,
        score: StrategyScore,
        family_allocation: FamilyBudget,
        tier_allocation: TierAllocation,
        crowding_penalty: float
    ) -> AdmissionDecision:
        """Check if strategy signal should be admitted"""
        
        checks = {}
        reasons = []
        
        # 1. Lifecycle check
        checks["lifecycle_ok"] = score.lifecycle_modifier > 0
        if not checks["lifecycle_ok"]:
            reasons.append("Strategy lifecycle disabled")
        
        # 2. Health check
        min_health = self.config.get("min_health", 0.40)
        checks["health_ok"] = score.edge_health >= min_health
        if not checks["health_ok"]:
            reasons.append(f"Health {score.edge_health:.2f} < min {min_health}")
        
        # 3. Regime fit check
        min_regime = self.config.get("min_regime_fit", 0.30)
        checks["regime_ok"] = score.regime_fit >= min_regime
        if not checks["regime_ok"]:
            reasons.append(f"Regime fit {score.regime_fit:.2f} < min {min_regime}")
        
        # 4. Final weight check
        min_weight = self.config.get("min_final_weight", 0.10)
        checks["weight_ok"] = score.final_weight >= min_weight
        if not checks["weight_ok"]:
            reasons.append(f"Weight {score.final_weight:.2f} < min {min_weight}")
        
        # 5. Family budget check
        max_family = self.config.get("max_family_weight", 0.40)
        checks["family_ok"] = family_allocation.current_weight < max_family
        if not checks["family_ok"]:
            reasons.append(f"Family budget exceeded: {family_allocation.current_weight:.2f}")
        
        # 6. Strategy weight check
        max_strategy = self.config.get("max_strategy_weight", 0.20)
        checks["strategy_weight_ok"] = score.final_weight <= max_strategy
        if not checks["strategy_weight_ok"]:
            reasons.append(f"Strategy weight {score.final_weight:.2f} > max {max_strategy}")
        
        # 7. Tier budget check
        checks["tier_ok"] = tier_allocation.remaining > 0
        if not checks["tier_ok"]:
            reasons.append(f"Tier {tier_allocation.tier} budget exhausted")
        
        # 8. Crowding check
        max_crowding = 0.40
        checks["crowding_ok"] = crowding_penalty < max_crowding
        if not checks["crowding_ok"]:
            reasons.append(f"High crowding penalty: {crowding_penalty:.2f}")
        
        # 9. Max concurrent per family
        max_concurrent = self.config.get("max_concurrent_per_family", 5)
        checks["concurrent_ok"] = family_allocation.active_strategies < max_concurrent
        if not checks["concurrent_ok"]:
            reasons.append(f"Max concurrent in family: {family_allocation.active_strategies}")
        
        # Determine admission
        critical_checks = ["lifecycle_ok", "health_ok", "regime_ok"]
        important_checks = ["weight_ok", "family_ok", "tier_ok"]
        
        # Block if critical fails
        if not all(checks.get(c, False) for c in critical_checks):
            admitted = False
            status = "BLOCKED"
        # Limit if important fails
        elif not all(checks.get(c, False) for c in important_checks):
            admitted = True
            status = "LIMITED"
        else:
            admitted = True
            status = "ADMITTED"
        
        decision = AdmissionDecision(
            strategy_id=strategy_id,
            signal_id=signal_id,
            admitted=admitted,
            status=status,
            final_weight=score.final_weight if admitted else 0.0,
            checks=checks,
            reason="; ".join(reasons) if reasons else "All checks passed",
            timestamp=int(time.time() * 1000)
        )
        
        self._recent_decisions.append(decision)
        
        # Keep only last 100
        if len(self._recent_decisions) > 100:
            self._recent_decisions = self._recent_decisions[-100:]
        
        return decision
    
    def get_recent_decisions(self, limit: int = 50) -> List[AdmissionDecision]:
        """Get recent admission decisions"""
        return self._recent_decisions[-limit:]


# ═══════════════════════════════════════════════════════════════
# Meta-Strategy Service
# ═══════════════════════════════════════════════════════════════

class MetaStrategyService:
    """
    Main Meta-Strategy Service.
    
    Coordinates all components:
    - Scoring
    - Family allocation
    - Tier allocation
    - Crowding detection
    - Admission
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or DEFAULT_META_STRATEGY_CONFIG
        
        self.scoring_engine = StrategyScoringEngine(self.config)
        self.crowding_detector = CrowdingDetector(self.config)
        self.family_manager = StrategyFamilyManager(self.config)
        self.tier_allocator = TierAllocator(self.config)
        self.admission_engine = StrategyAdmissionEngine(self.config)
        
        self._state = MetaStrategyState()
        self._strategies_data: Dict[str, Dict] = {}
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.27",
            "status": "ok",
            "components": {
                "scoring_engine": "ok",
                "crowding_detector": "ok",
                "family_manager": "ok",
                "tier_allocator": "ok",
                "admission_engine": "ok"
            },
            "strategiesLoaded": len(self._strategies_data),
            "currentRegime": self._state.current_regime,
            "lastRecompute": self._state.last_recompute,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    def get_status(self) -> MetaStrategyState:
        """Get full meta-strategy state"""
        return self._state
    
    def load_strategies(self, strategies: Dict[str, Dict]):
        """Load strategy data for scoring"""
        self._strategies_data = strategies
    
    def recompute(
        self,
        regime: str = "RANGE",
        portfolio_state: Optional[Dict] = None
    ) -> Dict:
        """Recompute all strategy weights and allocations"""
        
        self._state.current_regime = regime
        
        # 1. Score all strategies
        scores: Dict[str, StrategyScore] = {}
        
        for sid, data in self._strategies_data.items():
            score = self.scoring_engine.score_strategy(
                sid, data, regime, portfolio_state
            )
            scores[sid] = score
        
        # 2. Detect crowding
        pairs, clusters = self.crowding_detector.detect_all(self._strategies_data)
        
        # 3. Apply crowding penalties
        for sid, score in scores.items():
            penalty = self.crowding_detector.get_strategy_penalty(sid, pairs)
            score.crowding_penalty = penalty
            
            # Recalculate final weight with penalty
            score.final_weight = self.scoring_engine._calc_final_weight(
                score.base_weight,
                score.edge_health,
                score.regime_fit,
                score.recent_performance,
                score.confidence_integrity,
                score.portfolio_fit,
                score.lifecycle_modifier,
                score.self_healing_modifier,
                penalty
            )
            
            # Update status
            if score.final_weight < 0.10:
                score.status = "BLOCKED"
                score.status_reason = "Weight too low"
            elif score.final_weight < 0.30:
                score.status = "LIMITED"
                score.status_reason = "Low weight"
            else:
                score.status = "ACTIVE"
        
        # 4. Compute allocations
        family_allocations = self.family_manager.compute_family_allocations(scores, regime)
        tier_allocations = self.tier_allocator.compute_tier_allocations(scores)
        
        # 5. Update state
        self._state.strategy_scores = scores
        self._state.family_budgets = family_allocations
        self._state.tier_allocations = tier_allocations
        self._state.crowding_pairs = pairs
        self._state.crowding_clusters = clusters
        self._state.last_recompute = int(time.time() * 1000)
        self._state.computed_at = int(time.time() * 1000)
        
        # Determine overall status
        active_count = sum(1 for s in scores.values() if s.status == "ACTIVE")
        if active_count == 0:
            self._state.status = "BLOCKED"
        elif active_count < len(scores) * 0.3:
            self._state.status = "LIMITED"
        else:
            self._state.status = "ACTIVE"
        
        return {
            "success": True,
            "regime": regime,
            "strategiesScored": len(scores),
            "activeStrategies": active_count,
            "crowdingPairs": len(pairs),
            "crowdingClusters": len(clusters),
            "overallStatus": self._state.status,
            "timestamp": self._state.computed_at
        }
    
    def admit_signal(
        self,
        strategy_id: str,
        signal_id: str
    ) -> AdmissionDecision:
        """Check admission for a strategy signal"""
        
        if strategy_id not in self._state.strategy_scores:
            return AdmissionDecision(
                strategy_id=strategy_id,
                signal_id=signal_id,
                admitted=False,
                status="BLOCKED",
                final_weight=0.0,
                reason="Strategy not found in meta-strategy state",
                timestamp=int(time.time() * 1000)
            )
        
        score = self._state.strategy_scores[strategy_id]
        family = score.family or "experimental_family"
        tier = score.tier or "TACTICAL"
        
        family_allocation = self._state.family_budgets.get(
            family,
            FamilyBudget(family=family, target_weight=0.1, current_weight=0, max_weight=0.15, strategy_count=0, active_strategies=0)
        )
        
        tier_allocation = self._state.tier_allocations.get(
            tier,
            TierAllocation(tier=tier, budget=0.3, current=0, remaining=0.3, strategy_count=0)
        )
        
        return self.admission_engine.check_admission(
            strategy_id,
            signal_id,
            score,
            family_allocation,
            tier_allocation,
            score.crowding_penalty
        )
    
    def get_weights(self) -> Dict[str, float]:
        """Get current strategy weights"""
        return {
            sid: score.final_weight
            for sid, score in self._state.strategy_scores.items()
        }
    
    def get_families(self) -> Dict[str, Dict]:
        """Get family allocation status"""
        return {
            family: {
                "targetWeight": budget.target_weight,
                "currentWeight": budget.current_weight,
                "maxWeight": budget.max_weight,
                "strategyCount": budget.strategy_count,
                "activeStrategies": budget.active_strategies,
                "remaining": budget.max_weight - budget.current_weight
            }
            for family, budget in self._state.family_budgets.items()
        }
    
    def get_tiers(self) -> Dict[str, Dict]:
        """Get tier allocation status"""
        return {
            tier: {
                "budget": alloc.budget,
                "current": alloc.current,
                "remaining": alloc.remaining,
                "strategyCount": alloc.strategy_count
            }
            for tier, alloc in self._state.tier_allocations.items()
        }
    
    def get_crowding(self) -> Dict:
        """Get crowding analysis"""
        return {
            "pairs": [
                {
                    "strategyA": p.strategy_a,
                    "strategyB": p.strategy_b,
                    "signalOverlap": p.signal_overlap,
                    "tradeOverlap": p.trade_overlap,
                    "outcomeCorrelation": p.outcome_correlation,
                    "featureOverlap": p.feature_overlap,
                    "totalOverlap": p.total_overlap,
                    "penalty": p.penalty,
                    "level": p.level
                }
                for p in self._state.crowding_pairs
            ],
            "clusters": [
                {
                    "clusterId": c.cluster_id,
                    "strategies": c.strategies,
                    "avgOverlap": c.avg_overlap,
                    "totalPenalty": c.total_penalty,
                    "level": c.level
                }
                for c in self._state.crowding_clusters
            ],
            "pairCount": len(self._state.crowding_pairs),
            "clusterCount": len(self._state.crowding_clusters)
        }
    
    def get_admissions(self, limit: int = 50) -> List[Dict]:
        """Get recent admission decisions"""
        decisions = self.admission_engine.get_recent_decisions(limit)
        return [
            {
                "strategyId": d.strategy_id,
                "signalId": d.signal_id,
                "admitted": d.admitted,
                "status": d.status,
                "finalWeight": d.final_weight,
                "checks": d.checks,
                "reason": d.reason,
                "timestamp": d.timestamp
            }
            for d in decisions
        ]


# ═══════════════════════════════════════════════════════════════
# Serialization Functions
# ═══════════════════════════════════════════════════════════════

def strategy_score_to_dict(score: StrategyScore) -> Dict:
    """Convert StrategyScore to dict"""
    return {
        "strategyId": score.strategy_id,
        "scores": {
            "edgeHealth": score.edge_health,
            "regimeFit": score.regime_fit,
            "recentPerformance": score.recent_performance,
            "confidenceIntegrity": score.confidence_integrity,
            "portfolioFit": score.portfolio_fit
        },
        "modifiers": {
            "lifecycle": score.lifecycle_modifier,
            "selfHealing": score.self_healing_modifier,
            "crowdingPenalty": score.crowding_penalty
        },
        "baseWeight": score.base_weight,
        "finalWeight": score.final_weight,
        "family": score.family,
        "tier": score.tier,
        "regime": score.regime,
        "asset": score.asset,
        "status": score.status,
        "statusReason": score.status_reason,
        "computedAt": score.computed_at
    }


def meta_state_to_dict(state: MetaStrategyState) -> Dict:
    """Convert MetaStrategyState to dict"""
    return {
        "status": state.status,
        "currentRegime": state.current_regime,
        "strategyCount": len(state.strategy_scores),
        "strategies": {
            sid: strategy_score_to_dict(score)
            for sid, score in state.strategy_scores.items()
        },
        "families": {
            family: {
                "targetWeight": budget.target_weight,
                "currentWeight": budget.current_weight,
                "maxWeight": budget.max_weight,
                "strategyCount": budget.strategy_count,
                "activeStrategies": budget.active_strategies
            }
            for family, budget in state.family_budgets.items()
        },
        "tiers": {
            tier: {
                "budget": alloc.budget,
                "current": alloc.current,
                "remaining": alloc.remaining,
                "strategyCount": alloc.strategy_count
            }
            for tier, alloc in state.tier_allocations.items()
        },
        "crowding": {
            "pairCount": len(state.crowding_pairs),
            "clusterCount": len(state.crowding_clusters)
        },
        "lastRecompute": state.last_recompute,
        "computedAt": state.computed_at
    }
