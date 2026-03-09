"""
Admin Control Center
====================

Phase C - Isolated admin module for system control.

This module:
- ONLY aggregates data from other modules via their APIs
- ONLY triggers actions via public interfaces
- NEVER performs calculations or analytics
- NEVER has cross-dependencies from other modules

Admin Control Center = READ + TRIGGER + MONITOR
"""

import time
from typing import Dict, List, Optional, Any


class AdminControlCenter:
    """
    Quant Control Center - Isolated Admin Module.
    
    Aggregates system state and provides control interface.
    """
    
    def __init__(self):
        self._module_refs = {}
        self._last_refresh = 0
        self._cached_state = {}
    
    def _load_modules(self):
        """Lazy load module references"""
        try:
            from modules.edge_lab.engine import edge_research_engine
            self._module_refs['edge_lab'] = edge_research_engine
        except ImportError:
            pass
        
        try:
            from modules.microstructure_lab.engine import microstructure_engine
            self._module_refs['microstructure'] = microstructure_engine
        except ImportError:
            pass
        
        try:
            from modules.research_loop.engine import research_loop_engine
            self._module_refs['research_loop'] = research_loop_engine
        except ImportError:
            pass
        
        try:
            from modules.global_risk_brain.engine import global_risk_brain
            self._module_refs['risk_brain'] = global_risk_brain
        except ImportError:
            pass
        
        try:
            from modules.shadow_portfolio.service import shadow_portfolio_service
            self._module_refs['shadow_portfolio'] = shadow_portfolio_service
        except ImportError:
            pass
        
        try:
            from modules.alpha_tournament.service import alpha_tournament_service
            self._module_refs['tournament'] = alpha_tournament_service
        except ImportError:
            pass
        
        try:
            from modules.alpha_registry.service import alpha_registry_service
            self._module_refs['registry'] = alpha_registry_service
        except ImportError:
            pass
        
        try:
            from modules.research_memory.engine import research_memory
            self._module_refs['memory'] = research_memory
        except ImportError:
            pass
        
        try:
            from modules.capital_simulation.engine import capital_simulation_engine
            self._module_refs['capital_sim'] = capital_simulation_engine
        except ImportError:
            pass
        
        try:
            from modules.policy_engine.engine import policy_engine
            self._module_refs['policies'] = policy_engine
        except ImportError:
            pass
        
        try:
            from modules.dataset_registry.engine import dataset_registry
            self._module_refs['datasets'] = dataset_registry
        except ImportError:
            pass
        
        try:
            from modules.experiment_tracker.engine import experiment_tracker
            self._module_refs['experiments'] = experiment_tracker
        except ImportError:
            pass
    
    # ============================================
    # Dashboard Aggregators
    # ============================================
    
    def get_edge_dashboard(self) -> Dict:
        """Aggregate edge intelligence data"""
        self._load_modules()
        
        edge = self._module_refs.get('edge_lab')
        if not edge:
            return {"error": "Edge Lab not available"}
        
        # Get family robustness
        families = edge.get_family_robustness()
        
        # Get top strategies by edge
        edge_map = edge.get_edge_map(min_pf=1.1)[:10]
        
        # Get decay data
        decays = edge.get_edge_decay()
        decaying_count = len([d for d in decays if d.get('is_decaying')])
        
        # Get fragility
        fragilities = edge.get_fragility()
        fragile_count = len([f for f in fragilities if f.get('fragility_level') in ['FRAGILE', 'VERY_FRAGILE']])
        
        return {
            "families": families,
            "top_strategies": edge_map,
            "decay_summary": {
                "total_analyzed": len(decays),
                "decaying": decaying_count,
                "decay_rate": round(decaying_count / max(1, len(decays)), 2)
            },
            "fragility_summary": {
                "total_analyzed": len(fragilities),
                "fragile_count": fragile_count,
                "fragility_rate": round(fragile_count / max(1, len(fragilities)), 2)
            },
            "timestamp": int(time.time() * 1000)
        }
    
    def get_execution_dashboard(self) -> Dict:
        """Aggregate execution/microstructure data"""
        self._load_modules()
        
        micro = self._module_refs.get('microstructure')
        capital = self._module_refs.get('capital_sim')
        
        data = {"timestamp": int(time.time() * 1000)}
        
        if micro:
            profiles = list(micro.spread_profiles.keys())
            data["assets_profiled"] = len(profiles)
            data["scenarios_available"] = len(micro.scenarios)
            data["fragility_analyses"] = len(micro.fragility_analyses)
            
            # Recent fills summary
            recent_fills = micro.fill_results[-50:] if micro.fill_results else []
            if recent_fills:
                data["recent_fills"] = {
                    "count": len(recent_fills),
                    "avg_cost_bps": round(sum(f.total_cost_bps for f in recent_fills) / len(recent_fills), 2),
                    "partial_rate": round(sum(1 for f in recent_fills if f.was_partial) / len(recent_fills), 2)
                }
        
        if capital:
            data["capital_profiles"] = len(capital.capital_profiles)
            data["capacity_analyses"] = len(capital.capacity_analyses)
        
        return data
    
    def get_alpha_dashboard(self) -> Dict:
        """Aggregate alpha factory data"""
        self._load_modules()
        
        registry = self._module_refs.get('registry')
        tournament = self._module_refs.get('tournament')
        
        data = {"timestamp": int(time.time() * 1000)}
        
        if registry:
            try:
                health = registry.get_health()
                data["registry"] = {
                    "total_alphas": health.get("total_alphas", 0),
                    "active_alphas": health.get("active_alphas", 0)
                }
            except:
                data["registry"] = {"status": "available"}
        
        if tournament:
            try:
                health = tournament.get_health()
                data["tournament"] = {
                    "status": health.get("status", "ok"),
                    "total_tournaments": health.get("total_tournaments", 0)
                }
            except:
                data["tournament"] = {"status": "available"}
        
        return data
    
    def get_risk_dashboard(self) -> Dict:
        """Aggregate risk/governance data"""
        self._load_modules()
        
        risk = self._module_refs.get('risk_brain')
        policies = self._module_refs.get('policies')
        
        data = {"timestamp": int(time.time() * 1000)}
        
        if risk:
            state = risk.get_state()
            data["risk_state"] = state.get("state")
            data["envelope"] = state.get("envelope")
            data["allocation"] = state.get("allocation")
            data["active_policies"] = state.get("active_policies", [])
            data["total_transitions"] = len(risk.transitions)
        
        if policies:
            policy_list = policies.list_policies()
            data["governance_policies"] = len(policy_list)
        
        return data
    
    def get_research_dashboard(self) -> Dict:
        """Aggregate research loop data"""
        self._load_modules()
        
        loop = self._module_refs.get('research_loop')
        memory = self._module_refs.get('memory')
        experiments = self._module_refs.get('experiments')
        
        data = {"timestamp": int(time.time() * 1000)}
        
        if loop:
            health = loop.get_health()
            data["loop"] = {
                "status": health.get("status"),
                "total_cycles": health.get("total_cycles", 0),
                "modules_loaded": health.get("modules_loaded", {})
            }
            
            # Get recent cycles
            cycles = loop.list_cycles(limit=5)
            data["recent_cycles"] = cycles
        
        if memory:
            health = memory.get_health()
            data["memory"] = {
                "total_entries": health.get("total_entries", 0),
                "total_patterns": health.get("total_patterns", 0),
                "compute_saved": health.get("compute_saved", 0)
            }
        
        if experiments:
            stats = experiments.get_stats()
            data["experiments"] = stats
        
        return data
    
    def get_shadow_dashboard(self) -> Dict:
        """Aggregate shadow portfolio data"""
        self._load_modules()
        
        shadow = self._module_refs.get('shadow_portfolio')
        
        data = {"timestamp": int(time.time() * 1000)}
        
        if shadow:
            try:
                health = shadow.get_health()
                data["shadow"] = {
                    "status": health.get("status", "ok"),
                    "portfolios": health.get("total_portfolios", 0),
                    "strategies": health.get("total_strategies", 0)
                }
            except:
                data["shadow"] = {"status": "available"}
        
        return data
    
    def get_system_dashboard(self) -> Dict:
        """Aggregate system telemetry"""
        self._load_modules()
        
        datasets = self._module_refs.get('datasets')
        
        data = {
            "modules_loaded": len(self._module_refs),
            "available_modules": list(self._module_refs.keys()),
            "timestamp": int(time.time() * 1000)
        }
        
        if datasets:
            health = datasets.get_health()
            data["datasets"] = {
                "total": health.get("total_datasets", 0),
                "total_rows": health.get("total_rows", 0),
                "assets": health.get("assets", [])
            }
        
        return data
    
    # ============================================
    # Control Actions
    # ============================================
    
    def trigger_research_cycle(self, loop_id: str = "LOOP_DEFAULT") -> Dict:
        """Trigger a research loop cycle"""
        self._load_modules()
        
        loop = self._module_refs.get('research_loop')
        if not loop:
            return {"error": "Research Loop not available"}
        
        result = loop.run_cycle(loop_id)
        return loop._cycle_to_dict(result)
    
    def override_risk_state(self, state: str, reason: str = "") -> Dict:
        """Override risk state"""
        self._load_modules()
        
        risk = self._module_refs.get('risk_brain')
        if not risk:
            return {"error": "Risk Brain not available"}
        
        from modules.global_risk_brain.types import RiskState
        try:
            risk_state = RiskState(state)
            risk.override_state(risk_state, reason)
            return risk.get_state()
        except ValueError:
            return {"error": f"Invalid state: {state}"}
    
    def create_experiment(self, name: str, **kwargs) -> Dict:
        """Create a new experiment"""
        self._load_modules()
        
        experiments = self._module_refs.get('experiments')
        if not experiments:
            return {"error": "Experiment Tracker not available"}
        
        exp = experiments.create(name, **kwargs)
        return experiments._to_dict(exp)
    
    # ============================================
    # Full Dashboard
    # ============================================
    
    def get_full_dashboard(self) -> Dict:
        """Get complete system dashboard"""
        return {
            "edge": self.get_edge_dashboard(),
            "execution": self.get_execution_dashboard(),
            "alpha": self.get_alpha_dashboard(),
            "risk": self.get_risk_dashboard(),
            "research": self.get_research_dashboard(),
            "shadow": self.get_shadow_dashboard(),
            "system": self.get_system_dashboard(),
            "timestamp": int(time.time() * 1000)
        }
    
    def get_health(self) -> Dict:
        """Get control center health"""
        self._load_modules()
        
        return {
            "enabled": True,
            "version": "phaseC",
            "status": "ok",
            "modules_connected": len(self._module_refs),
            "module_list": list(self._module_refs.keys()),
            "timestamp": int(time.time() * 1000)
        }


# Singleton
admin_control_center = AdminControlCenter()
