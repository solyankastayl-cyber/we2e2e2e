"""
Alpha Tournament Service
========================

Phase 9.29 - Service layer for alpha tournament operations.
"""

import time
from typing import Dict, List, Optional, Any

from .types import (
    TournamentCandidate, TournamentBucket, TournamentScorecard,
    TournamentRun, TournamentConfig, TournamentVerdict
)
from .engine import tournament_engine


class AlphaTournamentService:
    """
    Service for managing alpha tournaments.
    
    Provides:
    - Candidate admission
    - Bucket management
    - Tournament execution
    - Results analysis
    """
    
    def __init__(self):
        self.engine = tournament_engine
    
    # ============================================
    # Candidate Management
    # ============================================
    
    def admit_candidate(
        self,
        alpha_id: str,
        name: str,
        family: str,
        asset_classes: List[str],
        timeframes: List[str],
        validation_score: float,
        orthogonality_score: float,
        crowding_score: float,
        registry_status: str = "VALIDATED"
    ) -> Dict:
        """Admit a candidate to tournament"""
        
        candidate = self.engine.admit_candidate(
            alpha_id=alpha_id,
            name=name,
            family=family,
            asset_classes=asset_classes,
            timeframes=timeframes,
            validation_score=validation_score,
            orthogonality_score=orthogonality_score,
            crowding_score=crowding_score,
            registry_status=registry_status
        )
        
        return {
            "alpha_id": candidate.alpha_id,
            "admitted": candidate.admitted,
            "bucket_id": candidate.bucket_id,
            "reasons": candidate.admission_reasons
        }
    
    def get_candidates(self, bucket_id: str = None) -> Dict:
        """Get all candidates, optionally filtered by bucket"""
        
        candidates = list(self.engine.candidates.values())
        
        if bucket_id:
            candidates = [c for c in candidates if c.bucket_id == bucket_id]
        
        return {
            "total": len(candidates),
            "candidates": [
                {
                    "alpha_id": c.alpha_id,
                    "name": c.name,
                    "family": c.family,
                    "bucket_id": c.bucket_id,
                    "admitted": c.admitted,
                    "validation_score": c.validation_score
                }
                for c in candidates
            ]
        }
    
    # ============================================
    # Scorecard Management
    # ============================================
    
    def evaluate_scorecard(
        self,
        alpha_id: str,
        profit_factor: float = 0.0,
        sharpe: float = 0.0,
        max_drawdown: float = 0.0,
        cagr: float = 0.0,
        win_rate: float = 0.0,
        stability_score: float = 0.0,
        regime_robustness: float = 0.0
    ) -> Dict:
        """Evaluate scorecard for candidate"""
        
        scorecard = self.engine.evaluate_scorecard(
            alpha_id=alpha_id,
            profit_factor=profit_factor,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            cagr=cagr,
            win_rate=win_rate,
            stability_score=stability_score,
            regime_robustness=regime_robustness
        )
        
        if not scorecard:
            return {"error": "Candidate not found or not admitted"}
        
        return self._scorecard_to_dict(scorecard)
    
    def get_scorecard(self, alpha_id: str) -> Optional[Dict]:
        """Get scorecard for alpha"""
        
        scorecard = self.engine.scorecards.get(alpha_id)
        if not scorecard:
            return None
        
        return self._scorecard_to_dict(scorecard)
    
    # ============================================
    # Bucket Management
    # ============================================
    
    def get_buckets(self) -> Dict:
        """Get all tournament buckets"""
        
        return {
            "total": len(self.engine.buckets),
            "buckets": [
                {
                    "bucket_id": b.bucket_id,
                    "family": b.family,
                    "asset_class": b.asset_class,
                    "timeframe": b.timeframe,
                    "candidate_count": b.candidate_count,
                    "is_active": b.is_active
                }
                for b in self.engine.buckets.values()
            ]
        }
    
    def get_bucket_results(self, bucket_id: str) -> Optional[Dict]:
        """Get results for a bucket"""
        return self.engine.get_bucket_results(bucket_id)
    
    def create_bucket(
        self,
        bucket_id: str,
        family: str,
        asset_class: str,
        timeframe: str
    ) -> Dict:
        """Create a new bucket"""
        
        if bucket_id in self.engine.buckets:
            return {"error": f"Bucket {bucket_id} already exists"}
        
        bucket = TournamentBucket(
            bucket_id=bucket_id,
            family=family,
            asset_class=asset_class,
            timeframe=timeframe
        )
        
        self.engine.buckets[bucket_id] = bucket
        
        return {
            "bucket_id": bucket_id,
            "created": True
        }
    
    # ============================================
    # Tournament Execution
    # ============================================
    
    def run_tournament(self, bucket_ids: List[str] = None) -> Dict:
        """Run a complete tournament cycle"""
        
        run = self.engine.run_tournament(bucket_ids)
        
        return self._run_to_dict(run)
    
    def run_bucket_tournament(self, bucket_id: str) -> Dict:
        """Run tournament for single bucket"""
        
        run = self.engine.run_tournament([bucket_id])
        
        return self._run_to_dict(run)
    
    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get tournament run by ID"""
        
        run = self.engine.runs.get(run_id)
        if not run:
            return None
        
        return self._run_to_dict(run)
    
    def list_runs(self, limit: int = 20) -> Dict:
        """List recent tournament runs"""
        
        runs = sorted(
            self.engine.runs.values(),
            key=lambda r: r.completed_at,
            reverse=True
        )[:limit]
        
        return {
            "total": len(self.engine.runs),
            "runs": [
                {
                    "run_id": r.run_id,
                    "status": r.status.value,
                    "total_candidates": r.total_candidates,
                    "total_promoted": r.total_promoted,
                    "total_rejected": r.total_rejected,
                    "completed_at": r.completed_at
                }
                for r in runs
            ]
        }
    
    # ============================================
    # History
    # ============================================
    
    def get_alpha_history(self, alpha_id: str) -> Optional[Dict]:
        """Get tournament history for alpha"""
        return self.engine.get_alpha_history(alpha_id)
    
    # ============================================
    # Management
    # ============================================
    
    def clear_candidates(self) -> Dict:
        """Clear all candidates for new cycle"""
        self.engine.clear_candidates()
        return {"cleared": True}
    
    def update_config(
        self,
        min_validation_score: float = None,
        promote_threshold: float = None,
        max_promotions_per_cycle: int = None
    ) -> Dict:
        """Update tournament configuration"""
        
        config = self.engine.config
        
        if min_validation_score is not None:
            config.min_validation_score = min_validation_score
        if promote_threshold is not None:
            config.promote_threshold = promote_threshold
        if max_promotions_per_cycle is not None:
            config.max_promotions_per_cycle = max_promotions_per_cycle
        
        return {"updated": True, "config": self._config_to_dict(config)}
    
    def get_config(self) -> Dict:
        """Get current configuration"""
        return self._config_to_dict(self.engine.config)
    
    # ============================================
    # Health Check
    # ============================================
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.29",
            "status": "ok",
            "total_buckets": len(self.engine.buckets),
            "active_buckets": len([b for b in self.engine.buckets.values() if b.is_active]),
            "total_candidates": len(self.engine.candidates),
            "total_runs": len(self.engine.runs),
            "supported_verdicts": [v.value for v in TournamentVerdict],
            "timestamp": int(time.time() * 1000)
        }
    
    def get_stats(self) -> Dict:
        """Get tournament statistics"""
        
        runs = list(self.engine.runs.values())
        
        total_promoted = sum(r.total_promoted for r in runs)
        total_rejected = sum(r.total_rejected for r in runs)
        
        return {
            "total_runs": len(runs),
            "total_promoted_all_time": total_promoted,
            "total_rejected_all_time": total_rejected,
            "buckets_by_family": {
                family: len([b for b in self.engine.buckets.values() if b.family == family])
                for family in set(b.family for b in self.engine.buckets.values())
            }
        }
    
    # ============================================
    # Helpers
    # ============================================
    
    def _scorecard_to_dict(self, sc: TournamentScorecard) -> Dict:
        return {
            "alpha_id": sc.alpha_id,
            "bucket_id": sc.bucket_id,
            "metrics": {
                "profit_factor": sc.profit_factor,
                "sharpe": sc.sharpe,
                "max_drawdown": sc.max_drawdown,
                "cagr": sc.cagr,
                "win_rate": sc.win_rate
            },
            "quality": {
                "stability": sc.stability_score,
                "regime_robustness": sc.regime_robustness,
                "orthogonality": sc.orthogonality_score,
                "crowding_penalty": sc.crowding_penalty
            },
            "final_score": sc.final_score,
            "bucket_rank": sc.bucket_rank,
            "verdict": sc.verdict.value,
            "verdict_reasons": sc.verdict_reasons
        }
    
    def _run_to_dict(self, run: TournamentRun) -> Dict:
        return {
            "run_id": run.run_id,
            "status": run.status.value,
            "bucket_ids": run.bucket_ids,
            "stats": {
                "total_candidates": run.total_candidates,
                "total_promoted": run.total_promoted,
                "total_kept": run.total_kept,
                "total_rejected": run.total_rejected
            },
            "rounds": [
                {
                    "round_id": r.round_id,
                    "bucket_id": r.bucket_id,
                    "promoted": r.promoted_ids,
                    "kept": r.kept_ids,
                    "rejected": r.rejected_ids
                }
                for r in run.rounds
            ],
            "started_at": run.started_at,
            "completed_at": run.completed_at
        }
    
    def _config_to_dict(self, config: TournamentConfig) -> Dict:
        return {
            "admission": {
                "min_validation_score": config.min_validation_score,
                "max_crowding_score": config.max_crowding_score,
                "min_orthogonality_score": config.min_orthogonality_score
            },
            "scoring_weights": {
                "sharpe": config.sharpe_weight,
                "pf": config.pf_weight,
                "stability": config.stability_weight,
                "regime": config.regime_weight,
                "orthogonality": config.orthogonality_weight,
                "crowding_penalty": config.crowding_penalty_weight
            },
            "thresholds": {
                "promote": config.promote_threshold,
                "keep": config.keep_threshold,
                "reject": config.reject_threshold
            },
            "quotas": {
                "max_promotions_per_cycle": config.max_promotions_per_cycle,
                "max_promotions_per_family": config.max_promotions_per_family,
                "max_promotions_per_bucket": config.max_promotions_per_bucket
            }
        }


# Singleton instance
tournament_service = AlphaTournamentService()
