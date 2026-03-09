"""
Edge Research Lab Engine
========================

Phase A - Core engine for edge research and analysis.

Analyzes where edge really exists:
- By strategy/asset/regime combinations
- By decade (temporal stability)
- By regime (conditional edge)
- By asset class (transferability)
- By family (robustness)
"""

import time
import uuid
import math
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

from .types import (
    EdgeStrength, RegimeType, AssetClass, StrategyFamily,
    EdgeMapEntry, DecadeAnalysis, RegimeEdge, CrossAssetEdge,
    FamilyRobustness, EdgeDecay, FragilityAnalysis, EdgeReport
)


class EdgeResearchEngine:
    """
    Edge Research Lab Engine.
    
    Comprehensive analysis of where edge exists and where it doesn't.
    """
    
    def __init__(self):
        # Storage
        self.edge_map: Dict[str, EdgeMapEntry] = {}
        self.decade_analyses: Dict[str, DecadeAnalysis] = {}
        self.regime_edges: Dict[str, RegimeEdge] = {}
        self.cross_asset_edges: Dict[str, CrossAssetEdge] = {}
        self.family_robustness: Dict[str, FamilyRobustness] = {}
        self.edge_decays: Dict[str, EdgeDecay] = {}
        self.fragility_analyses: Dict[str, FragilityAnalysis] = {}
        self.reports: Dict[str, EdgeReport] = {}
        
        # Mock data for demonstration
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize with realistic mock data"""
        
        strategies = [
            ("breakout_spx_v1", "SPX", StrategyFamily.BREAKOUT),
            ("breakout_btc_v1", "BTC", StrategyFamily.BREAKOUT),
            ("trend_spx_v1", "SPX", StrategyFamily.TREND),
            ("trend_btc_v1", "BTC", StrategyFamily.TREND),
            ("momentum_spx_v1", "SPX", StrategyFamily.MOMENTUM),
            ("momentum_btc_v1", "BTC", StrategyFamily.MOMENTUM),
            ("reversal_spx_v1", "SPX", StrategyFamily.MEAN_REVERSION),
            ("reversal_btc_v1", "BTC", StrategyFamily.MEAN_REVERSION),
        ]
        
        regimes = list(RegimeType)
        
        # Generate edge map entries
        for strat, asset, family in strategies:
            asset_class = AssetClass.CRYPTO if asset == "BTC" else AssetClass.EQUITY
            
            for regime in regimes:
                key = f"{strat}_{asset}_{regime.value}"
                
                # Simulate realistic performance variations
                base_pf = self._get_family_base_pf(family)
                regime_mod = self._get_regime_modifier(family, regime)
                asset_mod = self._get_asset_modifier(family, asset_class)
                
                pf = base_pf * regime_mod * asset_mod
                sharpe = (pf - 1) * 2 + 0.3  # Rough Sharpe approximation
                win_rate = 0.45 + (pf - 1) * 0.15
                
                self.edge_map[key] = EdgeMapEntry(
                    strategy=strat,
                    asset=asset,
                    asset_class=asset_class,
                    regime=regime,
                    trades=50 + int(pf * 30),
                    pf=round(pf, 3),
                    sharpe=round(max(0, sharpe), 3),
                    win_rate=round(min(0.65, max(0.35, win_rate)), 3),
                    edge_strength=self._classify_edge(pf, sharpe),
                    sample_size_score=0.7,
                    consistency_score=0.6
                )
        
        # Generate decade analyses
        decades = ["1990s", "2000s", "2010s", "2020s"]
        for strat, _, family in strategies:
            prev_pf = 1.0
            for decade in decades:
                key = f"{strat}_{decade}"
                # Simulate edge decay over time
                decay = 0.95 ** decades.index(decade)
                pf = self._get_family_base_pf(family) * decay
                sharpe = (pf - 1) * 2 + 0.3
                
                self.decade_analyses[key] = DecadeAnalysis(
                    strategy=strat,
                    family=family,
                    decade=decade,
                    start_year=1990 + decades.index(decade) * 10,
                    end_year=1999 + decades.index(decade) * 10,
                    trades=100 + int(pf * 50),
                    pf=round(pf, 3),
                    sharpe=round(max(0, sharpe), 3),
                    win_rate=round(0.45 + (pf - 1) * 0.15, 3),
                    vs_previous_decade_pf=round(pf / prev_pf - 1, 3) if prev_pf > 0 else 0,
                    edge_strength=self._classify_edge(pf, sharpe)
                )
                prev_pf = pf
        
        # Generate regime edges
        for strat, _, family in strategies:
            regime_pfs = {}
            regime_sharpes = {}
            
            for regime in RegimeType:
                mod = self._get_regime_modifier(family, regime)
                pf = self._get_family_base_pf(family) * mod
                regime_pfs[regime] = pf
                regime_sharpes[regime] = (pf - 1) * 2 + 0.3
            
            best = max(regime_pfs, key=regime_pfs.get)
            worst = min(regime_pfs, key=regime_pfs.get)
            
            self.regime_edges[strat] = RegimeEdge(
                strategy=strat,
                family=family,
                trend_up_pf=round(regime_pfs.get(RegimeType.TREND_UP, 1.0), 3),
                trend_up_sharpe=round(regime_sharpes.get(RegimeType.TREND_UP, 0.0), 3),
                trend_down_pf=round(regime_pfs.get(RegimeType.TREND_DOWN, 1.0), 3),
                trend_down_sharpe=round(regime_sharpes.get(RegimeType.TREND_DOWN, 0.0), 3),
                range_pf=round(regime_pfs.get(RegimeType.RANGE, 1.0), 3),
                range_sharpe=round(regime_sharpes.get(RegimeType.RANGE, 0.0), 3),
                expansion_pf=round(regime_pfs.get(RegimeType.EXPANSION, 1.0), 3),
                expansion_sharpe=round(regime_sharpes.get(RegimeType.EXPANSION, 0.0), 3),
                crisis_pf=round(regime_pfs.get(RegimeType.CRISIS, 1.0), 3),
                crisis_sharpe=round(regime_sharpes.get(RegimeType.CRISIS, 0.0), 3),
                best_regime=best,
                worst_regime=worst,
                regime_spread=round(regime_pfs[best] - regime_pfs[worst], 3),
                is_regime_dependent=regime_pfs[best] - regime_pfs[worst] > 0.3
            )
        
        # Generate cross-asset edges
        for strat, _, family in strategies:
            asset_pfs = {}
            asset_sharpes = {}
            
            for ac in AssetClass:
                mod = self._get_asset_modifier(family, ac)
                pf = self._get_family_base_pf(family) * mod
                asset_pfs[ac] = pf
                asset_sharpes[ac] = (pf - 1) * 2 + 0.3
            
            best = max(asset_pfs, key=asset_pfs.get)
            worst = min(asset_pfs, key=asset_pfs.get)
            
            # Calculate consistency
            pf_values = list(asset_pfs.values())
            mean_pf = sum(pf_values) / len(pf_values)
            std_pf = math.sqrt(sum((p - mean_pf) ** 2 for p in pf_values) / len(pf_values))
            consistency = 1 - (std_pf / mean_pf) if mean_pf > 0 else 0
            
            self.cross_asset_edges[strat] = CrossAssetEdge(
                strategy=strat,
                family=family,
                equity_pf=round(asset_pfs.get(AssetClass.EQUITY, 1.0), 3),
                equity_sharpe=round(asset_sharpes.get(AssetClass.EQUITY, 0.0), 3),
                crypto_pf=round(asset_pfs.get(AssetClass.CRYPTO, 1.0), 3),
                crypto_sharpe=round(asset_sharpes.get(AssetClass.CRYPTO, 0.0), 3),
                fx_pf=round(asset_pfs.get(AssetClass.FX, 1.0), 3),
                fx_sharpe=round(asset_sharpes.get(AssetClass.FX, 0.0), 3),
                commodity_pf=round(asset_pfs.get(AssetClass.COMMODITY, 1.0), 3),
                commodity_sharpe=round(asset_sharpes.get(AssetClass.COMMODITY, 0.0), 3),
                best_asset_class=best,
                worst_asset_class=worst,
                cross_asset_consistency=round(max(0, consistency), 3),
                is_asset_specific=consistency < 0.5
            )
        
        # Generate family robustness
        for family in StrategyFamily:
            family_strategies = [s for s in self.regime_edges.values() if s.family == family]
            
            if family_strategies:
                avg_pf = sum(s.trend_up_pf for s in family_strategies) / len(family_strategies)
                pf_std = math.sqrt(sum((s.trend_up_pf - avg_pf) ** 2 for s in family_strategies) / len(family_strategies))
                
                self.family_robustness[family.value] = FamilyRobustness(
                    family=family,
                    avg_pf=round(avg_pf, 3),
                    avg_sharpe=round((avg_pf - 1) * 2, 3),
                    strategy_count=len(family_strategies),
                    pf_std=round(pf_std, 3),
                    stability_score=round(1 - pf_std / avg_pf if avg_pf > 0 else 0, 3),
                    all_regime_positive=all(s.crisis_pf > 1.0 for s in family_strategies),
                    worst_regime_pf=round(min(s.crisis_pf for s in family_strategies), 3),
                    robustness_level=self._classify_robustness(avg_pf, pf_std)
                )
        
        # Generate edge decay
        for strat, _, family in strategies:
            base_pf = self._get_family_base_pf(family)
            current_pf = base_pf * 0.9  # Simulated current
            historical_pf = base_pf * 1.1  # Simulated historical
            
            decay_rate = (current_pf / historical_pf - 1) * 100  # Percentage
            
            self.edge_decays[strat] = EdgeDecay(
                strategy=strat,
                family=family,
                current_pf=round(current_pf, 3),
                historical_pf=round(historical_pf, 3),
                current_sharpe=round((current_pf - 1) * 2, 3),
                historical_sharpe=round((historical_pf - 1) * 2, 3),
                pf_decay_rate=round(decay_rate, 2),
                sharpe_decay_rate=round(decay_rate * 1.2, 2),
                lookback_years=10,
                recent_years=3,
                is_decaying=decay_rate < -5,
                decay_severity=self._classify_decay(decay_rate)
            )
        
        # Generate fragility analyses
        for strat, _, family in strategies:
            regime_edge = self.regime_edges.get(strat)
            asset_edge = self.cross_asset_edges.get(strat)
            
            regime_dependent = regime_edge.is_regime_dependent if regime_edge else False
            asset_specific = asset_edge.is_asset_specific if asset_edge else False
            
            # Count working conditions
            working = 0
            total = 0
            for key, entry in self.edge_map.items():
                if entry.strategy == strat:
                    total += 1
                    if entry.pf > 1.0:
                        working += 1
            
            fragility = 1 - (working / total) if total > 0 else 1.0
            if regime_dependent:
                fragility += 0.2
            if asset_specific:
                fragility += 0.2
            fragility = min(1.0, fragility)
            
            self.fragility_analyses[strat] = FragilityAnalysis(
                strategy=strat,
                family=family,
                requires_specific_regime=regime_dependent,
                required_regimes=[regime_edge.best_regime] if regime_dependent and regime_edge else [],
                requires_specific_asset=asset_specific,
                required_assets=[asset_edge.best_asset_class.value] if asset_specific and asset_edge else [],
                fragility_score=round(fragility, 3),
                working_conditions=working,
                total_conditions=total,
                fragility_level=self._classify_fragility(fragility)
            )
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def _get_family_base_pf(self, family: StrategyFamily) -> float:
        """Get base PF for family"""
        base_pfs = {
            StrategyFamily.TREND: 1.35,
            StrategyFamily.BREAKOUT: 1.20,
            StrategyFamily.MOMENTUM: 1.25,
            StrategyFamily.MEAN_REVERSION: 1.30,
            StrategyFamily.VOLATILITY: 1.15,
            StrategyFamily.CARRY: 1.10
        }
        return base_pfs.get(family, 1.0)
    
    def _get_regime_modifier(self, family: StrategyFamily, regime: RegimeType) -> float:
        """Get regime modifier for family"""
        modifiers = {
            StrategyFamily.TREND: {
                RegimeType.TREND_UP: 1.2, RegimeType.TREND_DOWN: 1.1,
                RegimeType.RANGE: 0.7, RegimeType.EXPANSION: 1.1,
                RegimeType.CONTRACTION: 0.9, RegimeType.CRISIS: 0.8
            },
            StrategyFamily.BREAKOUT: {
                RegimeType.TREND_UP: 1.1, RegimeType.TREND_DOWN: 0.9,
                RegimeType.RANGE: 0.6, RegimeType.EXPANSION: 1.3,
                RegimeType.CONTRACTION: 0.8, RegimeType.CRISIS: 0.7
            },
            StrategyFamily.MOMENTUM: {
                RegimeType.TREND_UP: 1.3, RegimeType.TREND_DOWN: 0.8,
                RegimeType.RANGE: 0.7, RegimeType.EXPANSION: 1.1,
                RegimeType.CONTRACTION: 0.9, RegimeType.CRISIS: 0.6
            },
            StrategyFamily.MEAN_REVERSION: {
                RegimeType.TREND_UP: 0.8, RegimeType.TREND_DOWN: 0.9,
                RegimeType.RANGE: 1.3, RegimeType.EXPANSION: 0.8,
                RegimeType.CONTRACTION: 1.1, RegimeType.CRISIS: 1.0
            }
        }
        family_mods = modifiers.get(family, {})
        return family_mods.get(regime, 1.0)
    
    def _get_asset_modifier(self, family: StrategyFamily, asset_class: AssetClass) -> float:
        """Get asset class modifier for family"""
        modifiers = {
            StrategyFamily.TREND: {
                AssetClass.EQUITY: 1.1, AssetClass.CRYPTO: 1.2,
                AssetClass.FX: 0.9, AssetClass.COMMODITY: 1.0
            },
            StrategyFamily.BREAKOUT: {
                AssetClass.EQUITY: 1.0, AssetClass.CRYPTO: 1.3,
                AssetClass.FX: 0.8, AssetClass.COMMODITY: 0.9
            },
            StrategyFamily.MOMENTUM: {
                AssetClass.EQUITY: 1.2, AssetClass.CRYPTO: 1.1,
                AssetClass.FX: 0.9, AssetClass.COMMODITY: 0.95
            },
            StrategyFamily.MEAN_REVERSION: {
                AssetClass.EQUITY: 1.0, AssetClass.CRYPTO: 0.9,
                AssetClass.FX: 1.1, AssetClass.COMMODITY: 1.0
            }
        }
        family_mods = modifiers.get(family, {})
        return family_mods.get(asset_class, 1.0)
    
    def _classify_edge(self, pf: float, sharpe: float) -> EdgeStrength:
        """Classify edge strength"""
        if pf < 0.9 or sharpe < 0:
            return EdgeStrength.NEGATIVE
        elif pf < 1.0 or sharpe < 0.3:
            return EdgeStrength.NONE
        elif pf < 1.1 or sharpe < 0.5:
            return EdgeStrength.WEAK
        elif pf < 1.3 or sharpe < 1.0:
            return EdgeStrength.MEDIUM
        else:
            return EdgeStrength.STRONG
    
    def _classify_robustness(self, avg_pf: float, pf_std: float) -> str:
        """Classify family robustness"""
        stability = 1 - (pf_std / avg_pf) if avg_pf > 0 else 0
        if stability > 0.8 and avg_pf > 1.2:
            return "ANTIFRAGILE"
        elif stability > 0.6 and avg_pf > 1.1:
            return "ROBUST"
        elif stability > 0.4:
            return "MEDIUM"
        else:
            return "FRAGILE"
    
    def _classify_decay(self, rate: float) -> str:
        """Classify decay severity"""
        if rate > -5:
            return "NONE"
        elif rate > -15:
            return "MILD"
        elif rate > -30:
            return "MODERATE"
        else:
            return "SEVERE"
    
    def _classify_fragility(self, score: float) -> str:
        """Classify fragility level"""
        if score < 0.3:
            return "ROBUST"
        elif score < 0.5:
            return "MEDIUM"
        elif score < 0.7:
            return "FRAGILE"
        else:
            return "VERY_FRAGILE"
    
    # ============================================
    # Analysis Methods
    # ============================================
    
    def analyze_strategy(self, strategy_id: str) -> Dict:
        """Complete edge analysis for a strategy"""
        
        # Collect all data
        map_entries = [e for e in self.edge_map.values() if e.strategy == strategy_id]
        decade_data = [d for d in self.decade_analyses.values() if d.strategy == strategy_id]
        regime_data = self.regime_edges.get(strategy_id)
        asset_data = self.cross_asset_edges.get(strategy_id)
        decay_data = self.edge_decays.get(strategy_id)
        fragility_data = self.fragility_analyses.get(strategy_id)
        
        if not map_entries:
            return {"error": "Strategy not found"}
        
        # Calculate summary
        avg_pf = sum(e.pf for e in map_entries) / len(map_entries)
        avg_sharpe = sum(e.sharpe for e in map_entries) / len(map_entries)
        
        # Best/worst conditions
        best_entry = max(map_entries, key=lambda e: e.pf)
        worst_entry = min(map_entries, key=lambda e: e.pf)
        
        return {
            "strategy_id": strategy_id,
            "summary": {
                "avg_pf": round(avg_pf, 3),
                "avg_sharpe": round(avg_sharpe, 3),
                "edge_strength": self._classify_edge(avg_pf, avg_sharpe).value,
                "conditions_analyzed": len(map_entries)
            },
            "best_condition": {
                "asset": best_entry.asset,
                "regime": best_entry.regime.value,
                "pf": best_entry.pf,
                "sharpe": best_entry.sharpe
            },
            "worst_condition": {
                "asset": worst_entry.asset,
                "regime": worst_entry.regime.value,
                "pf": worst_entry.pf,
                "sharpe": worst_entry.sharpe
            },
            "regime_analysis": self._regime_edge_to_dict(regime_data) if regime_data else None,
            "asset_analysis": self._cross_asset_to_dict(asset_data) if asset_data else None,
            "decay_analysis": self._decay_to_dict(decay_data) if decay_data else None,
            "fragility": self._fragility_to_dict(fragility_data) if fragility_data else None
        }
    
    def generate_report(self) -> EdgeReport:
        """Generate comprehensive edge report"""
        
        report_id = f"EDGE_RPT_{uuid.uuid4().hex[:8]}"
        now = int(time.time() * 1000)
        
        # Count strategies
        strategies = set(e.strategy for e in self.edge_map.values())
        with_edge = set(e.strategy for e in self.edge_map.values() if e.pf > 1.0)
        decaying = set(d.strategy for d in self.edge_decays.values() if d.is_decaying)
        
        # Find best performers
        best_entries = sorted(self.edge_map.values(), key=lambda e: e.pf, reverse=True)
        strongest = best_entries[0] if best_entries else None
        
        # Family analysis
        family_avgs = {}
        for family in StrategyFamily:
            entries = [e for e in self.edge_map.values() 
                      if any(s.family == family for s in self.regime_edges.values() if s.strategy == e.strategy)]
            if entries:
                family_avgs[family] = sum(e.pf for e in entries) / len(entries)
        
        strongest_family = max(family_avgs, key=family_avgs.get) if family_avgs else StrategyFamily.TREND
        weakest_family = min(family_avgs, key=family_avgs.get) if family_avgs else StrategyFamily.BREAKOUT
        
        # Recommendations
        recommendations = []
        if len(decaying) > len(strategies) * 0.3:
            recommendations.append("Warning: Over 30% of strategies show edge decay")
        if strongest_family:
            recommendations.append(f"Focus research on {strongest_family.value} family (strongest edge)")
        
        report = EdgeReport(
            report_id=report_id,
            total_strategies=len(strategies),
            strategies_with_edge=len(with_edge),
            strategies_decaying=len(decaying),
            strongest_strategy=strongest.strategy if strongest else "",
            strongest_family=strongest_family,
            best_regime=RegimeType.TREND_UP,
            best_asset_class=AssetClass.CRYPTO,
            weakest_strategy=min(self.edge_map.values(), key=lambda e: e.pf).strategy if self.edge_map else "",
            most_fragile_family=weakest_family,
            worst_regime=RegimeType.CRISIS,
            recommendations=recommendations,
            created_at=now
        )
        
        self.reports[report_id] = report
        return report
    
    # ============================================
    # Query Methods
    # ============================================
    
    def get_edge_map(
        self,
        strategy: str = None,
        asset: str = None,
        regime: str = None,
        min_pf: float = 0.0
    ) -> List[Dict]:
        """Get filtered edge map"""
        
        results = list(self.edge_map.values())
        
        if strategy:
            results = [e for e in results if e.strategy == strategy]
        if asset:
            results = [e for e in results if e.asset == asset]
        if regime:
            results = [e for e in results if e.regime.value == regime]
        if min_pf > 0:
            results = [e for e in results if e.pf >= min_pf]
        
        return [self._edge_map_to_dict(e) for e in results]
    
    def get_decade_analysis(self, strategy: str = None) -> List[Dict]:
        """Get decade analysis"""
        results = list(self.decade_analyses.values())
        if strategy:
            results = [d for d in results if d.strategy == strategy]
        return [self._decade_to_dict(d) for d in results]
    
    def get_regime_edges(self, strategy: str = None) -> List[Dict]:
        """Get regime edge analysis"""
        results = list(self.regime_edges.values())
        if strategy:
            results = [r for r in results if r.strategy == strategy]
        return [self._regime_edge_to_dict(r) for r in results]
    
    def get_cross_asset_edges(self, strategy: str = None) -> List[Dict]:
        """Get cross-asset edge analysis"""
        results = list(self.cross_asset_edges.values())
        if strategy:
            results = [c for c in results if c.strategy == strategy]
        return [self._cross_asset_to_dict(c) for c in results]
    
    def get_family_robustness(self, family: str = None) -> List[Dict]:
        """Get family robustness analysis"""
        results = list(self.family_robustness.values())
        if family:
            results = [f for f in results if f.family.value == family]
        return [self._family_to_dict(f) for f in results]
    
    def get_edge_decay(self, strategy: str = None) -> List[Dict]:
        """Get edge decay analysis"""
        results = list(self.edge_decays.values())
        if strategy:
            results = [d for d in results if d.strategy == strategy]
        return [self._decay_to_dict(d) for d in results]
    
    def get_fragility(self, strategy: str = None) -> List[Dict]:
        """Get fragility analysis"""
        results = list(self.fragility_analyses.values())
        if strategy:
            results = [f for f in results if f.strategy == strategy]
        return [self._fragility_to_dict(f) for f in results]
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phaseA",
            "status": "ok",
            "edge_map_entries": len(self.edge_map),
            "decade_analyses": len(self.decade_analyses),
            "regime_edges": len(self.regime_edges),
            "cross_asset_edges": len(self.cross_asset_edges),
            "family_analyses": len(self.family_robustness),
            "decay_analyses": len(self.edge_decays),
            "fragility_analyses": len(self.fragility_analyses),
            "reports": len(self.reports),
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Serialization
    # ============================================
    
    def _edge_map_to_dict(self, e: EdgeMapEntry) -> Dict:
        return {
            "strategy": e.strategy,
            "asset": e.asset,
            "asset_class": e.asset_class.value,
            "regime": e.regime.value,
            "trades": e.trades,
            "pf": e.pf,
            "sharpe": e.sharpe,
            "win_rate": e.win_rate,
            "edge_strength": e.edge_strength.value
        }
    
    def _decade_to_dict(self, d: DecadeAnalysis) -> Dict:
        return {
            "strategy": d.strategy,
            "family": d.family.value,
            "decade": d.decade,
            "trades": d.trades,
            "pf": d.pf,
            "sharpe": d.sharpe,
            "win_rate": d.win_rate,
            "vs_previous_pf": d.vs_previous_decade_pf,
            "edge_strength": d.edge_strength.value
        }
    
    def _regime_edge_to_dict(self, r: RegimeEdge) -> Dict:
        return {
            "strategy": r.strategy,
            "family": r.family.value,
            "by_regime": {
                "TREND_UP": {"pf": r.trend_up_pf, "sharpe": r.trend_up_sharpe},
                "TREND_DOWN": {"pf": r.trend_down_pf, "sharpe": r.trend_down_sharpe},
                "RANGE": {"pf": r.range_pf, "sharpe": r.range_sharpe},
                "EXPANSION": {"pf": r.expansion_pf, "sharpe": r.expansion_sharpe},
                "CRISIS": {"pf": r.crisis_pf, "sharpe": r.crisis_sharpe}
            },
            "best_regime": r.best_regime.value,
            "worst_regime": r.worst_regime.value,
            "regime_spread": r.regime_spread,
            "is_regime_dependent": r.is_regime_dependent
        }
    
    def _cross_asset_to_dict(self, c: CrossAssetEdge) -> Dict:
        return {
            "strategy": c.strategy,
            "family": c.family.value,
            "by_asset_class": {
                "EQUITY": {"pf": c.equity_pf, "sharpe": c.equity_sharpe},
                "CRYPTO": {"pf": c.crypto_pf, "sharpe": c.crypto_sharpe},
                "FX": {"pf": c.fx_pf, "sharpe": c.fx_sharpe},
                "COMMODITY": {"pf": c.commodity_pf, "sharpe": c.commodity_sharpe}
            },
            "best_asset_class": c.best_asset_class.value,
            "worst_asset_class": c.worst_asset_class.value,
            "consistency": c.cross_asset_consistency,
            "is_asset_specific": c.is_asset_specific
        }
    
    def _family_to_dict(self, f: FamilyRobustness) -> Dict:
        return {
            "family": f.family.value,
            "avg_pf": f.avg_pf,
            "avg_sharpe": f.avg_sharpe,
            "strategy_count": f.strategy_count,
            "stability_score": f.stability_score,
            "all_regime_positive": f.all_regime_positive,
            "worst_regime_pf": f.worst_regime_pf,
            "robustness_level": f.robustness_level
        }
    
    def _decay_to_dict(self, d: EdgeDecay) -> Dict:
        return {
            "strategy": d.strategy,
            "family": d.family.value,
            "current_pf": d.current_pf,
            "historical_pf": d.historical_pf,
            "pf_decay_rate": d.pf_decay_rate,
            "sharpe_decay_rate": d.sharpe_decay_rate,
            "is_decaying": d.is_decaying,
            "decay_severity": d.decay_severity
        }
    
    def _fragility_to_dict(self, f: FragilityAnalysis) -> Dict:
        return {
            "strategy": f.strategy,
            "family": f.family.value,
            "requires_specific_regime": f.requires_specific_regime,
            "required_regimes": [r.value for r in f.required_regimes],
            "requires_specific_asset": f.requires_specific_asset,
            "fragility_score": f.fragility_score,
            "working_conditions": f.working_conditions,
            "total_conditions": f.total_conditions,
            "fragility_level": f.fragility_level
        }
    
    def _report_to_dict(self, r: EdgeReport) -> Dict:
        return {
            "report_id": r.report_id,
            "total_strategies": r.total_strategies,
            "strategies_with_edge": r.strategies_with_edge,
            "strategies_decaying": r.strategies_decaying,
            "strongest_strategy": r.strongest_strategy,
            "strongest_family": r.strongest_family.value,
            "best_regime": r.best_regime.value,
            "best_asset_class": r.best_asset_class.value,
            "weakest_strategy": r.weakest_strategy,
            "most_fragile_family": r.most_fragile_family.value,
            "worst_regime": r.worst_regime.value,
            "recommendations": r.recommendations,
            "created_at": r.created_at
        }


# Singleton
edge_research_engine = EdgeResearchEngine()
