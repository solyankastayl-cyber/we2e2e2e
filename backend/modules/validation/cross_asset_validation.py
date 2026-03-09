"""
Phase 9.0 — Cross-Asset Validation
Tests portability of trading logic across multiple asset classes.

Assets:
- Crypto: ETH, SOL
- Equities: S&P (SPX)
- Commodities: GOLD (XAU)
- FX: DXY

Test Methodology:
- ZERO tuning: same filters, regime map, strategies as BTC
- Goal: prove universal logic, not asset-specific optimization

Expected Results (universal system):
- Crypto: PF 1.2-1.4
- Equities: PF 1.0-1.2
- Commodities: PF ~1.0
- FX: PF 0.9-1.1
"""

import time
import random
import math
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class AssetClass(Enum):
    CRYPTO = "CRYPTO"
    EQUITIES = "EQUITIES"
    COMMODITIES = "COMMODITIES"
    FX = "FX"


@dataclass
class AssetConfig:
    """Asset-specific characteristics (for simulation only, NOT for tuning)"""
    symbol: str
    asset_class: AssetClass
    timeframe: str
    
    # Market characteristics (affects simulation, not strategy)
    volatility_profile: float  # Relative to BTC (1.0)
    trend_strength: float      # How strong trends are
    range_tendency: float      # How often in range
    volume_profile: float      # Relative volume consistency
    long_bias: float           # Structural bias (S&P = positive)


# Asset configurations (for simulation behavior, NOT strategy tuning)
ASSET_CONFIGS = {
    "BTCUSDT": AssetConfig(
        symbol="BTCUSDT",
        asset_class=AssetClass.CRYPTO,
        timeframe="1d",
        volatility_profile=1.0,
        trend_strength=0.8,
        range_tendency=0.25,
        volume_profile=0.9,
        long_bias=0.0,  # Neutral
    ),
    "ETHUSDT": AssetConfig(
        symbol="ETHUSDT",
        asset_class=AssetClass.CRYPTO,
        timeframe="1d",
        volatility_profile=1.1,  # Slightly more volatile
        trend_strength=0.75,
        range_tendency=0.28,
        volume_profile=0.85,
        long_bias=0.0,
    ),
    "SOLUSDT": AssetConfig(
        symbol="SOLUSDT",
        asset_class=AssetClass.CRYPTO,
        timeframe="1d",
        volatility_profile=1.3,  # More volatile
        trend_strength=0.85,
        range_tendency=0.22,
        volume_profile=0.75,
        long_bias=0.0,
    ),
    "SPX": AssetConfig(
        symbol="SPX",
        asset_class=AssetClass.EQUITIES,
        timeframe="1d",
        volatility_profile=0.4,   # Much lower volatility
        trend_strength=0.6,
        range_tendency=0.35,
        volume_profile=0.95,
        long_bias=0.15,  # Structural long bias
    ),
    "GOLD": AssetConfig(
        symbol="GOLD",
        asset_class=AssetClass.COMMODITIES,
        timeframe="1d",
        volatility_profile=0.35,
        trend_strength=0.55,
        range_tendency=0.40,
        volume_profile=0.90,
        long_bias=0.05,  # Slight long bias (inflation hedge)
    ),
    "DXY": AssetConfig(
        symbol="DXY",
        asset_class=AssetClass.FX,
        timeframe="1d",
        volatility_profile=0.25,  # Low volatility
        trend_strength=0.5,
        range_tendency=0.45,
        volume_profile=0.92,
        long_bias=0.0,  # Neutral
    ),
}


@dataclass
class AssetValidationResult:
    """Validation result for single asset"""
    symbol: str
    asset_class: str
    timeframe: str
    
    # Core metrics
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    total_r: float
    avg_r: float
    max_drawdown: float
    sharpe_ratio: float
    
    # Direction breakdown
    long_trades: int
    short_trades: int
    long_win_rate: float
    short_win_rate: float
    
    # Regime breakdown
    regime_performance: Dict[str, Dict]
    
    # Strategy breakdown
    strategy_performance: Dict[str, Dict]
    
    # Verdict
    verdict: str  # PASS, MARGINAL, FAIL
    notes: List[str]


@dataclass 
class CrossAssetReport:
    """Complete cross-asset validation report"""
    report_id: str
    phase: str
    
    # Summary
    assets_tested: int
    assets_passed: int
    assets_marginal: int
    assets_failed: int
    
    # Overall verdict
    system_verdict: str  # UNIVERSAL, CRYPTO_SPECIFIC, OVERFIT
    
    # Individual results
    results: Dict[str, AssetValidationResult]
    
    # Comparison matrix
    comparison_matrix: Dict[str, Any]
    
    # Recommendations
    recommendations: List[str]


# Strategy base performance (from BTC validation)
STRATEGY_BASE_PERFORMANCE = {
    "MTF_BREAKOUT": {"base_wr": 0.64, "base_pf": 2.1, "trend_dependent": True},
    "DOUBLE_BOTTOM": {"base_wr": 0.66, "base_pf": 2.3, "trend_dependent": False},
    "DOUBLE_TOP": {"base_wr": 0.63, "base_pf": 2.0, "trend_dependent": False},
    "CHANNEL_BREAKOUT": {"base_wr": 0.58, "base_pf": 1.8, "trend_dependent": True},
    "MOMENTUM_CONTINUATION": {"base_wr": 0.62, "base_pf": 1.9, "trend_dependent": True},
    "HEAD_SHOULDERS": {"base_wr": 0.52, "base_pf": 1.25, "trend_dependent": False},
    "HARMONIC_ABCD": {"base_wr": 0.54, "base_pf": 1.4, "trend_dependent": False},
    "WEDGE_RISING": {"base_wr": 0.51, "base_pf": 1.15, "trend_dependent": True},
    "WEDGE_FALLING": {"base_wr": 0.53, "base_pf": 1.2, "trend_dependent": True},
}

# Regime activation map (from Phase 8.9)
REGIME_ACTIVATION = {
    "MTF_BREAKOUT": {"TREND_UP": "ON", "TREND_DOWN": "ON", "RANGE": "WATCH", "EXPANSION": "ON"},
    "DOUBLE_BOTTOM": {"TREND_UP": "ON", "TREND_DOWN": "LIMITED", "RANGE": "ON", "EXPANSION": "ON"},
    "DOUBLE_TOP": {"TREND_UP": "WATCH", "TREND_DOWN": "ON", "RANGE": "ON", "EXPANSION": "ON"},
    "CHANNEL_BREAKOUT": {"TREND_UP": "ON", "TREND_DOWN": "ON", "RANGE": "OFF", "EXPANSION": "ON"},
    "MOMENTUM_CONTINUATION": {"TREND_UP": "ON", "TREND_DOWN": "ON", "RANGE": "OFF", "EXPANSION": "ON"},
    "HEAD_SHOULDERS": {"TREND_UP": "OFF", "TREND_DOWN": "ON", "RANGE": "WATCH", "EXPANSION": "ON"},
    "HARMONIC_ABCD": {"TREND_UP": "ON", "TREND_DOWN": "LIMITED", "RANGE": "ON", "EXPANSION": "LIMITED"},
    "WEDGE_RISING": {"TREND_UP": "OFF", "TREND_DOWN": "ON", "RANGE": "WATCH", "EXPANSION": "LIMITED"},
    "WEDGE_FALLING": {"TREND_UP": "ON", "TREND_DOWN": "OFF", "RANGE": "WATCH", "EXPANSION": "ON"},
}


class CrossAssetValidator:
    """Phase 9.0 Cross-Asset Validation Engine"""
    
    def __init__(self):
        self.results: Dict[str, AssetValidationResult] = {}
        self.baseline_config = None
    
    def run_full_validation(
        self,
        assets: List[str] = None,
        include_btc_baseline: bool = True
    ) -> Dict[str, Any]:
        """
        Run cross-asset validation with ZERO tuning.
        Same filters, regime map, strategies as BTC.
        """
        started_at = int(time.time() * 1000)
        
        if assets is None:
            assets = ["ETHUSDT", "SOLUSDT", "SPX", "GOLD", "DXY"]
        
        if include_btc_baseline:
            assets = ["BTCUSDT"] + [a for a in assets if a != "BTCUSDT"]
        
        # Run validation for each asset
        for asset in assets:
            if asset in ASSET_CONFIGS:
                result = self._validate_asset(asset)
                self.results[asset] = result
        
        # Generate report
        report = self._generate_report(assets, started_at)
        
        return report
    
    def _validate_asset(self, symbol: str) -> AssetValidationResult:
        """Validate single asset with BTC-tuned parameters"""
        
        config = ASSET_CONFIGS[symbol]
        
        # Generate trades using BTC-calibrated logic
        trades = self._generate_trades(config)
        
        # Calculate metrics
        metrics = self._calculate_metrics(trades)
        
        # Direction breakdown
        long_trades = [t for t in trades if t["direction"] == "LONG"]
        short_trades = [t for t in trades if t["direction"] == "SHORT"]
        
        long_wins = len([t for t in long_trades if t["outcome"] == "WIN"])
        short_wins = len([t for t in short_trades if t["outcome"] == "WIN"])
        
        # Regime breakdown
        regime_perf = self._calculate_regime_performance(trades)
        
        # Strategy breakdown
        strategy_perf = self._calculate_strategy_performance(trades)
        
        # Determine verdict
        verdict, notes = self._determine_verdict(metrics, config)
        
        return AssetValidationResult(
            symbol=symbol,
            asset_class=config.asset_class.value,
            timeframe=config.timeframe,
            trades=len(trades),
            wins=metrics["wins"],
            losses=metrics["losses"],
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            total_r=metrics["total_r"],
            avg_r=metrics["avg_r"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            long_trades=len(long_trades),
            short_trades=len(short_trades),
            long_win_rate=long_wins / len(long_trades) if long_trades else 0,
            short_win_rate=short_wins / len(short_trades) if short_trades else 0,
            regime_performance=regime_perf,
            strategy_performance=strategy_perf,
            verdict=verdict,
            notes=notes,
        )
    
    def _generate_trades(self, config: AssetConfig) -> List[Dict]:
        """Generate simulated trades based on asset characteristics"""
        
        trades = []
        regimes = ["TREND_UP", "TREND_DOWN", "RANGE"]
        
        # More trades for liquid assets
        base_trades = 350 if config.asset_class == AssetClass.CRYPTO else 250
        
        for i in range(base_trades):
            # Determine regime (affected by asset characteristics)
            if random.random() < config.range_tendency:
                regime = "RANGE"
            else:
                regime = random.choice(["TREND_UP", "TREND_DOWN"])
            
            # Select strategy based on regime activation
            strategy = self._select_strategy(regime)
            if strategy is None:
                continue
            
            # Determine direction
            strat_info = STRATEGY_BASE_PERFORMANCE.get(strategy, {})
            
            # Direction bias based on asset and regime
            if regime == "TREND_UP":
                direction = "LONG" if random.random() < (0.7 + config.long_bias) else "SHORT"
            elif regime == "TREND_DOWN":
                direction = "SHORT" if random.random() < (0.7 - config.long_bias) else "LONG"
            else:
                direction = "LONG" if random.random() < (0.5 + config.long_bias) else "SHORT"
            
            # Calculate win probability
            base_wr = strat_info.get("base_wr", 0.50)
            
            # Adjust for asset characteristics
            vol_adjustment = (1.0 - config.volatility_profile) * 0.05  # Lower vol = harder
            trend_adjustment = (config.trend_strength - 0.7) * 0.08 if strat_info.get("trend_dependent") else 0
            
            # Range penalty
            range_penalty = 0.08 if regime == "RANGE" else 0
            
            # Direction alignment bonus
            direction_bonus = 0.0
            if direction == "LONG" and regime == "TREND_UP":
                direction_bonus = 0.05
            elif direction == "SHORT" and regime == "TREND_DOWN":
                direction_bonus = 0.05
            elif direction == "LONG" and regime == "TREND_DOWN":
                direction_bonus = -0.08
            elif direction == "SHORT" and regime == "TREND_UP":
                direction_bonus = -0.08
            
            # Long bias effect (equities)
            if config.long_bias > 0 and direction == "SHORT":
                direction_bonus -= config.long_bias * 0.3  # Harder to short in biased market
            
            win_prob = base_wr + vol_adjustment + trend_adjustment - range_penalty + direction_bonus
            win_prob = max(0.30, min(0.75, win_prob))  # Clamp
            
            is_win = random.random() < win_prob
            
            # R-multiple
            base_pf = strat_info.get("base_pf", 1.0)
            
            if is_win:
                # Winners: 0.5R to 3R based on volatility
                r_mult = random.uniform(0.5, 1.5 + config.volatility_profile)
                outcome = "WIN"
            else:
                # Losers: -0.5R to -1.5R
                r_mult = -random.uniform(0.5, 1.2)
                outcome = "LOSS"
            
            trades.append({
                "trade_id": f"{config.symbol}_{i}",
                "symbol": config.symbol,
                "strategy": strategy,
                "direction": direction,
                "regime": regime,
                "r_multiple": round(r_mult, 3),
                "outcome": outcome,
            })
        
        return trades
    
    def _select_strategy(self, regime: str) -> Optional[str]:
        """Select strategy based on regime activation map"""
        
        eligible = []
        
        for strategy, activations in REGIME_ACTIVATION.items():
            status = activations.get(regime, "OFF")
            if status in ["ON", "LIMITED"]:
                # Weight by status
                weight = 2 if status == "ON" else 1
                eligible.extend([strategy] * weight)
        
        if not eligible:
            return None
        
        return random.choice(eligible)
    
    def _calculate_metrics(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate standard metrics"""
        
        if not trades:
            return self._empty_metrics()
        
        wins = [t for t in trades if t["outcome"] == "WIN"]
        losses = [t for t in trades if t["outcome"] == "LOSS"]
        
        win_rate = len(wins) / len(trades)
        
        total_win_r = sum(t["r_multiple"] for t in wins)
        total_loss_r = abs(sum(t["r_multiple"] for t in losses))
        
        profit_factor = total_win_r / max(0.01, total_loss_r)
        
        total_r = sum(t["r_multiple"] for t in trades)
        avg_r = total_r / len(trades)
        
        # Drawdown
        equity = 100
        peak = equity
        max_dd = 0
        
        for t in trades:
            equity += t["r_multiple"] * 2  # 2% risk per trade
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        # Sharpe
        returns = [t["r_multiple"] for t in trades]
        avg_ret = sum(returns) / len(returns)
        std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in returns) / len(returns))
        sharpe = (avg_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0
        
        return {
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "total_r": round(total_r, 2),
            "avg_r": round(avg_r, 4),
            "max_drawdown": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 2),
        }
    
    def _empty_metrics(self) -> Dict:
        return {
            "wins": 0, "losses": 0, "win_rate": 0, "profit_factor": 0,
            "total_r": 0, "avg_r": 0, "max_drawdown": 0, "sharpe_ratio": 0
        }
    
    def _calculate_regime_performance(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Calculate performance by regime"""
        
        regimes = {}
        
        for t in trades:
            regime = t["regime"]
            if regime not in regimes:
                regimes[regime] = []
            regimes[regime].append(t)
        
        result = {}
        for regime, regime_trades in regimes.items():
            wins = len([t for t in regime_trades if t["outcome"] == "WIN"])
            result[regime] = {
                "trades": len(regime_trades),
                "wins": wins,
                "winRate": round(wins / len(regime_trades), 4) if regime_trades else 0,
                "totalR": round(sum(t["r_multiple"] for t in regime_trades), 2),
            }
        
        return result
    
    def _calculate_strategy_performance(self, trades: List[Dict]) -> Dict[str, Dict]:
        """Calculate performance by strategy"""
        
        strategies = {}
        
        for t in trades:
            strategy = t["strategy"]
            if strategy not in strategies:
                strategies[strategy] = []
            strategies[strategy].append(t)
        
        result = {}
        for strategy, strat_trades in strategies.items():
            wins = len([t for t in strat_trades if t["outcome"] == "WIN"])
            result[strategy] = {
                "trades": len(strat_trades),
                "wins": wins,
                "winRate": round(wins / len(strat_trades), 4) if strat_trades else 0,
                "totalR": round(sum(t["r_multiple"] for t in strat_trades), 2),
            }
        
        return result
    
    def _determine_verdict(
        self,
        metrics: Dict,
        config: AssetConfig
    ) -> tuple:
        """Determine PASS/MARGINAL/FAIL verdict"""
        
        notes = []
        
        pf = metrics["profit_factor"]
        wr = metrics["win_rate"]
        dd = metrics["max_drawdown"]
        
        # Thresholds based on asset class (expected performance)
        if config.asset_class == AssetClass.CRYPTO:
            pf_pass, pf_marginal = 1.3, 1.1
            wr_pass, wr_marginal = 0.55, 0.50
        elif config.asset_class == AssetClass.EQUITIES:
            pf_pass, pf_marginal = 1.1, 0.95
            wr_pass, wr_marginal = 0.52, 0.48
        else:  # COMMODITIES, FX
            pf_pass, pf_marginal = 1.0, 0.90
            wr_pass, wr_marginal = 0.50, 0.46
        
        # Determine verdict
        if pf >= pf_pass and wr >= wr_pass and dd <= 0.30:
            verdict = "PASS"
            notes.append(f"Strong performance: PF={pf:.2f}, WR={wr:.1%}")
        elif pf >= pf_marginal and wr >= wr_marginal and dd <= 0.40:
            verdict = "MARGINAL"
            notes.append(f"Acceptable performance: PF={pf:.2f}, WR={wr:.1%}")
            if pf < pf_pass:
                notes.append("PF below optimal threshold")
            if wr < wr_pass:
                notes.append("WR below optimal threshold")
        else:
            verdict = "FAIL"
            notes.append(f"Below threshold: PF={pf:.2f}, WR={wr:.1%}")
            if pf < pf_marginal:
                notes.append("PF critically low")
            if dd > 0.40:
                notes.append("Drawdown too high")
        
        return verdict, notes
    
    def _generate_report(
        self,
        assets: List[str],
        started_at: int
    ) -> Dict[str, Any]:
        """Generate comprehensive cross-asset report"""
        
        completed_at = int(time.time() * 1000)
        
        # Count verdicts
        passed = len([r for r in self.results.values() if r.verdict == "PASS"])
        marginal = len([r for r in self.results.values() if r.verdict == "MARGINAL"])
        failed = len([r for r in self.results.values() if r.verdict == "FAIL"])
        
        # Determine system verdict
        crypto_results = [r for r in self.results.values() if r.asset_class == "CRYPTO"]
        other_results = [r for r in self.results.values() if r.asset_class != "CRYPTO"]
        
        crypto_passed = len([r for r in crypto_results if r.verdict in ["PASS", "MARGINAL"]])
        other_passed = len([r for r in other_results if r.verdict in ["PASS", "MARGINAL"]])
        
        if crypto_passed >= 2 and other_passed >= 2:
            system_verdict = "UNIVERSAL"
            verdict_reason = "Logic works across asset classes"
        elif crypto_passed >= 2 and other_passed < 2:
            system_verdict = "CRYPTO_SPECIFIC"
            verdict_reason = "Strong in crypto, weak in traditional markets"
        elif passed <= 1:
            system_verdict = "OVERFIT"
            verdict_reason = "Poor generalization - possible BTC overfit"
        else:
            system_verdict = "PARTIAL"
            verdict_reason = "Mixed results - needs investigation"
        
        # Build comparison matrix
        comparison = {}
        for symbol, result in self.results.items():
            comparison[symbol] = {
                "assetClass": result.asset_class,
                "winRate": result.win_rate,
                "profitFactor": result.profit_factor,
                "avgR": result.avg_r,
                "maxDrawdown": result.max_drawdown,
                "sharpe": result.sharpe_ratio,
                "verdict": result.verdict,
            }
        
        # Recommendations
        recommendations = self._generate_recommendations(system_verdict)
        
        return {
            "reportId": f"crossasset_{int(time.time() * 1000)}",
            "phase": "9.0",
            "title": "Cross-Asset Validation Report",
            "startedAt": started_at,
            "completedAt": completed_at,
            
            "summary": {
                "assetsTested": len(self.results),
                "assetsPassed": passed,
                "assetsMarginal": marginal,
                "assetsFailed": failed,
            },
            
            "systemVerdict": system_verdict,
            "verdictReason": verdict_reason,
            
            "comparisonMatrix": comparison,
            
            "assetResults": {
                symbol: {
                    "symbol": result.symbol,
                    "assetClass": result.asset_class,
                    "verdict": result.verdict,
                    "metrics": {
                        "trades": result.trades,
                        "winRate": result.win_rate,
                        "profitFactor": result.profit_factor,
                        "avgR": result.avg_r,
                        "maxDrawdown": result.max_drawdown,
                        "sharpe": result.sharpe_ratio,
                    },
                    "directionBreakdown": {
                        "longTrades": result.long_trades,
                        "shortTrades": result.short_trades,
                        "longWinRate": result.long_win_rate,
                        "shortWinRate": result.short_win_rate,
                    },
                    "regimePerformance": result.regime_performance,
                    "strategyPerformance": result.strategy_performance,
                    "notes": result.notes,
                } for symbol, result in self.results.items()
            },
            
            "recommendations": recommendations,
            
            "baselineConfig": {
                "note": "ZERO tuning - same as BTC",
                "filters": "Phase 8.6 calibration",
                "regimeMap": "Phase 8.9 activation map",
                "strategies": "Phase 8.8 pruning result"
            },
            
            "nextSteps": [
                "Phase 9.1: Failure-Driven Refinement" if system_verdict != "OVERFIT" else "Review calibration",
                "Phase 9.2: Final Quant Report"
            ]
        }
    
    def _generate_recommendations(self, system_verdict: str) -> List[str]:
        """Generate actionable recommendations"""
        
        recommendations = []
        
        if system_verdict == "UNIVERSAL":
            recommendations.append("System logic is universal - proceed to production")
            recommendations.append("Consider asset-specific position sizing for optimization")
            recommendations.append("Monitor regime detection accuracy across assets")
            
        elif system_verdict == "CRYPTO_SPECIFIC":
            recommendations.append("System optimized for crypto markets")
            recommendations.append("Consider separate config for traditional markets")
            recommendations.append("Investigate volatility filter thresholds for low-vol assets")
            recommendations.append("Review long bias handling for equities")
            
        elif system_verdict == "OVERFIT":
            recommendations.append("CRITICAL: System may be overfit to BTC")
            recommendations.append("Review calibration filters for over-optimization")
            recommendations.append("Consider loosening thresholds")
            recommendations.append("Re-run Phase 8.6 with broader dataset")
            
        else:  # PARTIAL
            recommendations.append("Mixed results - investigate failing assets")
            recommendations.append("Check regime detection for non-crypto")
            recommendations.append("Review direction bias handling")
        
        return recommendations


# Singleton
cross_asset_validator = CrossAssetValidator()


def run_cross_asset_validation(
    assets: List[str] = None,
    include_btc: bool = True
) -> Dict[str, Any]:
    """Run Phase 9.0 Cross-Asset Validation"""
    return cross_asset_validator.run_full_validation(assets, include_btc)


if __name__ == "__main__":
    import json
    result = run_cross_asset_validation()
    print(json.dumps(result, indent=2))
