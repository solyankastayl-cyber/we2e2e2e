"""
Alpha Tournament Engine
=======================

Phase 9.29 - Core tournament engine for alpha competition.
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .types import (
    TournamentCandidate, TournamentBucket, TournamentScorecard,
    TournamentRound, TournamentRun, TournamentHistory,
    TournamentVerdict, TournamentStage, TournamentStatus,
    TournamentConfig, DEFAULT_BUCKETS
)


class AlphaTournamentEngine:
    """
    Core engine for alpha tournament system.
    
    Pipeline:
    1. Admission - Filter candidates by basic quality
    2. Bucket Assignment - Group by family/asset/timeframe
    3. Scorecard Evaluation - Compute metrics and scores
    4. Ranking - Rank within bucket
    5. Promotion/Rejection - Apply verdicts
    """
    
    def __init__(self, config: Optional[TournamentConfig] = None):
        self.config = config or TournamentConfig()
        
        # Buckets
        self.buckets: Dict[str, TournamentBucket] = {}
        self._init_buckets()
        
        # Candidates
        self.candidates: Dict[str, TournamentCandidate] = {}
        
        # Scorecards
        self.scorecards: Dict[str, TournamentScorecard] = {}
        
        # History
        self.history: Dict[str, TournamentHistory] = {}
        
        # Runs
        self.runs: Dict[str, TournamentRun] = {}
    
    def _init_buckets(self):
        """Initialize default buckets"""
        for bucket in DEFAULT_BUCKETS:
            self.buckets[bucket.bucket_id] = bucket
    
    # ============================================
    # Admission Stage
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
    ) -> TournamentCandidate:
        """
        Admit a candidate to the tournament.
        
        Checks basic admission criteria.
        """
        
        candidate = TournamentCandidate(
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
        
        # Check admission criteria
        admitted, reasons = self._check_admission(candidate)
        candidate.admitted = admitted
        candidate.admission_reasons = reasons
        
        if admitted:
            # Assign to bucket
            bucket_id = self._assign_bucket(candidate)
            candidate.bucket_id = bucket_id
            
            # Add to bucket
            if bucket_id in self.buckets:
                self.buckets[bucket_id].candidate_alpha_ids.append(alpha_id)
                self.buckets[bucket_id].candidate_count += 1
        
        self.candidates[alpha_id] = candidate
        
        # Initialize history
        if alpha_id not in self.history:
            self.history[alpha_id] = TournamentHistory(alpha_id=alpha_id)
        
        return candidate
    
    def _check_admission(self, candidate: TournamentCandidate) -> Tuple[bool, List[str]]:
        """Check if candidate meets admission criteria"""
        
        reasons = []
        admitted = True
        
        # Check validation score
        if candidate.validation_score < self.config.min_validation_score:
            admitted = False
            reasons.append(f"Validation score {candidate.validation_score} < {self.config.min_validation_score}")
        
        # Check crowding score
        if candidate.crowding_score > self.config.max_crowding_score:
            admitted = False
            reasons.append(f"Crowding score {candidate.crowding_score} > {self.config.max_crowding_score}")
        
        # Check orthogonality score
        if candidate.orthogonality_score < self.config.min_orthogonality_score:
            admitted = False
            reasons.append(f"Orthogonality score {candidate.orthogonality_score} < {self.config.min_orthogonality_score}")
        
        # Check registry status
        if candidate.registry_status not in ["VALIDATED", "SHADOW", "LIMITED"]:
            admitted = False
            reasons.append(f"Invalid registry status: {candidate.registry_status}")
        
        if admitted:
            reasons.append("All admission criteria met")
        
        return admitted, reasons
    
    def _assign_bucket(self, candidate: TournamentCandidate) -> str:
        """Assign candidate to appropriate bucket"""
        
        family = candidate.family
        
        # Primary asset class (first in list)
        asset_class = candidate.asset_classes[0] if candidate.asset_classes else "ALL"
        
        # Primary timeframe
        timeframe = candidate.timeframes[0] if candidate.timeframes else "1D"
        
        # Try to find exact match
        bucket_id = f"{family}_{asset_class}_{timeframe}"
        
        if bucket_id in self.buckets:
            return bucket_id
        
        # Try family + ALL
        bucket_id = f"{family}_ALL_{timeframe}"
        if bucket_id in self.buckets:
            return bucket_id
        
        # Fall back to EXPERIMENTAL
        return "EXPERIMENTAL_ALL_1D"
    
    # ============================================
    # Scorecard Evaluation
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
    ) -> Optional[TournamentScorecard]:
        """Evaluate scorecard for a candidate"""
        
        candidate = self.candidates.get(alpha_id)
        if not candidate or not candidate.admitted:
            return None
        
        scorecard = TournamentScorecard(
            alpha_id=alpha_id,
            bucket_id=candidate.bucket_id,
            profit_factor=profit_factor,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            cagr=cagr,
            win_rate=win_rate,
            stability_score=stability_score,
            regime_robustness=regime_robustness,
            orthogonality_score=candidate.orthogonality_score,
            crowding_penalty=candidate.crowding_score,
            evaluated_at=int(time.time() * 1000)
        )
        
        # Compute final score
        final_score = self._compute_final_score(scorecard)
        scorecard.final_score = final_score
        
        self.scorecards[alpha_id] = scorecard
        
        return scorecard
    
    def _compute_final_score(self, scorecard: TournamentScorecard) -> float:
        """Compute final tournament score"""
        
        # Normalize metrics to 0-1 scale
        sharpe_norm = min(1.0, max(0, scorecard.sharpe / 3))  # Sharpe 3 = perfect
        pf_norm = min(1.0, max(0, (scorecard.profit_factor - 1) / 2))  # PF 3 = perfect
        stability_norm = scorecard.stability_score
        regime_norm = scorecard.regime_robustness
        orth_norm = scorecard.orthogonality_score
        
        # Drawdown penalty (lower is better)
        dd_penalty = min(0.3, scorecard.max_drawdown)
        
        # Compute weighted score
        final_score = (
            self.config.sharpe_weight * sharpe_norm +
            self.config.pf_weight * pf_norm +
            self.config.stability_weight * stability_norm +
            self.config.regime_weight * regime_norm +
            self.config.orthogonality_weight * orth_norm -
            self.config.crowding_penalty_weight * scorecard.crowding_penalty -
            0.1 * dd_penalty  # Additional DD penalty
        )
        
        return round(max(0, min(1, final_score)), 4)
    
    # ============================================
    # Ranking & Verdict
    # ============================================
    
    def rank_bucket(self, bucket_id: str) -> List[TournamentScorecard]:
        """Rank all candidates within a bucket"""
        
        bucket = self.buckets.get(bucket_id)
        if not bucket:
            return []
        
        # Get scorecards for bucket
        bucket_scorecards = [
            self.scorecards[aid] 
            for aid in bucket.candidate_alpha_ids 
            if aid in self.scorecards
        ]
        
        # Sort by final score descending
        bucket_scorecards.sort(key=lambda s: s.final_score, reverse=True)
        
        # Assign ranks
        for i, sc in enumerate(bucket_scorecards):
            sc.bucket_rank = i + 1
        
        return bucket_scorecards
    
    def apply_verdicts(self, bucket_id: str) -> Dict[str, List[str]]:
        """Apply verdicts to candidates in bucket"""
        
        bucket = self.buckets.get(bucket_id)
        if not bucket:
            return {"promoted": [], "kept": [], "rejected": []}
        
        # Rank first
        scorecards = self.rank_bucket(bucket_id)
        
        promoted = []
        kept = []
        rejected = []
        
        promotions_count = 0
        
        for sc in scorecards:
            reasons = []
            
            # Check promotion
            if (sc.final_score >= self.config.promote_threshold and 
                promotions_count < self.config.max_promotions_per_bucket):
                sc.verdict = TournamentVerdict.PROMOTE
                reasons.append(f"Score {sc.final_score} >= {self.config.promote_threshold}")
                reasons.append(f"Rank #{sc.bucket_rank} in bucket")
                promoted.append(sc.alpha_id)
                promotions_count += 1
            
            # Check keep
            elif sc.final_score >= self.config.keep_threshold:
                sc.verdict = TournamentVerdict.KEEP
                reasons.append(f"Score {sc.final_score} between keep and promote threshold")
                kept.append(sc.alpha_id)
            
            # Reject
            else:
                sc.verdict = TournamentVerdict.REJECT
                reasons.append(f"Score {sc.final_score} < {self.config.reject_threshold}")
                rejected.append(sc.alpha_id)
            
            sc.verdict_reasons = reasons
        
        # Update bucket
        bucket.winner_ids = promoted
        bucket.rejected_ids = rejected
        
        return {
            "promoted": promoted,
            "kept": kept,
            "rejected": rejected
        }
    
    # ============================================
    # Tournament Run
    # ============================================
    
    def run_tournament(
        self,
        bucket_ids: List[str] = None
    ) -> TournamentRun:
        """
        Run complete tournament cycle.
        
        If bucket_ids is None, runs across all active buckets.
        """
        
        run_id = f"tourney_{int(time.time())}"
        
        if bucket_ids is None:
            bucket_ids = [b.bucket_id for b in self.buckets.values() if b.is_active]
        
        run = TournamentRun(
            run_id=run_id,
            bucket_ids=bucket_ids,
            status=TournamentStatus.RUNNING,
            started_at=int(time.time() * 1000)
        )
        
        total_promoted = 0
        total_kept = 0
        total_rejected = 0
        family_promotions: Dict[str, int] = defaultdict(int)
        
        # Process each bucket
        for bucket_id in bucket_ids:
            bucket = self.buckets.get(bucket_id)
            if not bucket:
                continue
            
            # Skip if not enough candidates
            if bucket.candidate_count < bucket.min_candidates_required:
                continue
            
            # Apply verdicts
            results = self.apply_verdicts(bucket_id)
            
            # Check family quota
            family = bucket.family
            allowed_promotions = min(
                len(results["promoted"]),
                self.config.max_promotions_per_family - family_promotions[family]
            )
            
            # Limit promotions
            final_promoted = results["promoted"][:allowed_promotions]
            demoted_to_keep = results["promoted"][allowed_promotions:]
            
            family_promotions[family] += len(final_promoted)
            
            total_promoted += len(final_promoted)
            total_kept += len(results["kept"]) + len(demoted_to_keep)
            total_rejected += len(results["rejected"])
            
            # Create round
            round_obj = TournamentRound(
                round_id=f"{run_id}_{bucket_id}",
                stage=TournamentStage.PROMOTION_GATE,
                bucket_id=bucket_id,
                candidate_ids=bucket.candidate_alpha_ids,
                promoted_ids=final_promoted,
                kept_ids=results["kept"] + demoted_to_keep,
                rejected_ids=results["rejected"],
                total_candidates=bucket.candidate_count,
                total_promoted=len(final_promoted),
                total_rejected=len(results["rejected"]),
                started_at=int(time.time() * 1000),
                completed_at=int(time.time() * 1000)
            )
            
            run.rounds.append(round_obj)
            
            # Store scorecards in run
            for aid in bucket.candidate_alpha_ids:
                if aid in self.scorecards:
                    run.scorecards[aid] = self.scorecards[aid]
        
        # Update run stats
        run.total_candidates = sum(b.candidate_count for b in self.buckets.values())
        run.total_promoted = total_promoted
        run.total_kept = total_kept
        run.total_rejected = total_rejected
        run.status = TournamentStatus.COMPLETED
        run.completed_at = int(time.time() * 1000)
        
        # Update history
        self._update_history(run)
        
        self.runs[run_id] = run
        
        return run
    
    def _update_history(self, run: TournamentRun):
        """Update history for all participants"""
        
        for alpha_id, scorecard in run.scorecards.items():
            if alpha_id not in self.history:
                self.history[alpha_id] = TournamentHistory(alpha_id=alpha_id)
            
            hist = self.history[alpha_id]
            hist.tournaments_entered += 1
            
            if scorecard.verdict == TournamentVerdict.PROMOTE:
                hist.tournaments_won += 1
            elif scorecard.verdict == TournamentVerdict.REJECT:
                hist.tournaments_lost += 1
            
            if scorecard.final_score > hist.best_score:
                hist.best_score = scorecard.final_score
            
            if scorecard.bucket_rank < hist.best_rank or hist.best_rank == 0:
                hist.best_rank = scorecard.bucket_rank
            
            hist.run_history.append({
                "run_id": run.run_id,
                "bucket_id": scorecard.bucket_id,
                "score": scorecard.final_score,
                "rank": scorecard.bucket_rank,
                "verdict": scorecard.verdict.value,
                "timestamp": run.completed_at
            })
    
    # ============================================
    # Query Methods
    # ============================================
    
    def get_bucket_results(self, bucket_id: str) -> Optional[Dict]:
        """Get results for a bucket"""
        
        bucket = self.buckets.get(bucket_id)
        if not bucket:
            return None
        
        scorecards = self.rank_bucket(bucket_id)
        
        return {
            "bucket_id": bucket_id,
            "family": bucket.family,
            "asset_class": bucket.asset_class,
            "timeframe": bucket.timeframe,
            "candidate_count": bucket.candidate_count,
            "rankings": [
                {
                    "alpha_id": sc.alpha_id,
                    "rank": sc.bucket_rank,
                    "score": sc.final_score,
                    "verdict": sc.verdict.value
                }
                for sc in scorecards
            ]
        }
    
    def get_alpha_history(self, alpha_id: str) -> Optional[Dict]:
        """Get tournament history for alpha"""
        
        hist = self.history.get(alpha_id)
        if not hist:
            return None
        
        return {
            "alpha_id": alpha_id,
            "tournaments_entered": hist.tournaments_entered,
            "tournaments_won": hist.tournaments_won,
            "tournaments_lost": hist.tournaments_lost,
            "win_rate": hist.tournaments_won / hist.tournaments_entered if hist.tournaments_entered > 0 else 0,
            "best_score": hist.best_score,
            "best_rank": hist.best_rank,
            "recent_history": hist.run_history[-10:]
        }
    
    def clear_candidates(self):
        """Clear all candidates for new tournament cycle"""
        self.candidates.clear()
        self.scorecards.clear()
        
        for bucket in self.buckets.values():
            bucket.candidate_alpha_ids.clear()
            bucket.candidate_count = 0
            bucket.winner_ids.clear()
            bucket.rejected_ids.clear()


# Singleton instance
tournament_engine = AlphaTournamentEngine()
