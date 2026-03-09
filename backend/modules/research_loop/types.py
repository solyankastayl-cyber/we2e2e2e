"""
Research Loop Engine Types
==========================

Phase 9.33 - Data structures for automated research cycle.

Research Loop Pipeline:
1. Feature Factory → generates/mutates features
2. Alpha Generator → creates alpha signals
3. Alpha Registry → registers candidates
4. Alpha Tournament → compares and ranks
5. Shadow Portfolio → simulates execution
6. Research Memory → records outcomes

The loop runs continuously, learning from failures.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class LoopPhase(str, Enum):
    """Phases of the research loop"""
    IDLE = "IDLE"
    FEATURE_GENERATION = "FEATURE_GENERATION"
    ALPHA_GENERATION = "ALPHA_GENERATION"
    REGISTRY_SUBMIT = "REGISTRY_SUBMIT"
    TOURNAMENT_RUN = "TOURNAMENT_RUN"
    SHADOW_ADMISSION = "SHADOW_ADMISSION"
    MEMORY_UPDATE = "MEMORY_UPDATE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LoopMode(str, Enum):
    """Loop execution modes"""
    MANUAL = "MANUAL"           # Single run, triggered manually
    SCHEDULED = "SCHEDULED"     # Runs on schedule
    CONTINUOUS = "CONTINUOUS"   # Runs continuously with cooldown


class LoopStatus(str, Enum):
    """Loop status"""
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    ERROR = "ERROR"


@dataclass
class LoopConfig:
    """Configuration for research loop"""
    loop_id: str = ""
    name: str = "Default Research Loop"
    
    # Execution mode
    mode: LoopMode = LoopMode.MANUAL
    
    # Feature generation
    max_mutations_per_cycle: int = 20
    mutation_categories: List[str] = field(default_factory=lambda: ["ARITHMETIC", "TEMPORAL"])
    base_features: List[str] = field(default_factory=list)
    
    # Alpha generation
    max_alphas_per_cycle: int = 10
    alpha_families: List[str] = field(default_factory=lambda: ["MOMENTUM", "MEAN_REVERSION", "BREAKOUT"])
    
    # Quality gates
    min_feature_quality: float = 0.6
    min_alpha_sharpe: float = 0.5
    max_crowding: float = 0.85
    
    # Tournament
    tournament_rounds: int = 3
    min_tournament_score: float = 0.4
    
    # Shadow admission
    require_shadow_approval: bool = True
    shadow_observation_days: int = 30
    
    # Memory
    record_all_failures: bool = True
    check_memory_before_generate: bool = True
    
    # Scheduling
    cooldown_seconds: int = 3600  # 1 hour between cycles
    max_cycles_per_day: int = 24
    
    # Assets
    target_assets: List[str] = field(default_factory=lambda: ["BTC", "SPX"])
    target_timeframes: List[str] = field(default_factory=lambda: ["1D", "4H"])


@dataclass
class LoopCycleResult:
    """Result of a single research loop cycle"""
    cycle_id: str
    loop_id: str
    
    # Phase results
    phase: LoopPhase = LoopPhase.IDLE
    phase_history: List[str] = field(default_factory=list)
    
    # Feature generation
    features_generated: int = 0
    features_passed: int = 0
    features_rejected: int = 0
    best_feature_id: str = ""
    best_feature_score: float = 0.0
    
    # Alpha generation
    alphas_generated: int = 0
    alphas_registered: int = 0
    alphas_rejected: int = 0
    best_alpha_id: str = ""
    best_alpha_sharpe: float = 0.0
    
    # Tournament
    tournament_id: str = ""
    tournament_winner: str = ""
    tournament_rounds_completed: int = 0
    
    # Shadow admission
    alphas_admitted_to_shadow: int = 0
    alphas_rejected_from_shadow: int = 0
    
    # Memory
    failures_recorded: int = 0
    patterns_updated: int = 0
    memory_blocks_hit: int = 0  # Blocked by memory check
    
    # Timing
    started_at: int = 0
    completed_at: int = 0
    duration_seconds: float = 0.0
    
    # Status
    success: bool = False
    error_message: str = ""
    
    # Metrics
    compute_cost: float = 0.0  # Estimated compute units used


@dataclass
class LoopState:
    """Current state of the research loop"""
    loop_id: str
    status: LoopStatus = LoopStatus.STOPPED
    current_phase: LoopPhase = LoopPhase.IDLE
    
    # Cycle tracking
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    
    # Current cycle
    current_cycle_id: str = ""
    cycles_today: int = 0
    
    # Cumulative results
    total_features_generated: int = 0
    total_alphas_generated: int = 0
    total_alphas_admitted: int = 0
    total_failures_recorded: int = 0
    
    # Timing
    last_cycle_at: int = 0
    next_cycle_at: int = 0
    
    # Config
    config: Optional[LoopConfig] = None


@dataclass
class LoopEvent:
    """Event during loop execution"""
    event_id: str
    cycle_id: str
    phase: LoopPhase
    
    event_type: str  # STARTED, COMPLETED, FAILED, SKIPPED, BLOCKED
    entity_type: str = ""  # FEATURE, ALPHA, TOURNAMENT, etc.
    entity_id: str = ""
    
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    timestamp: int = 0


@dataclass
class LoopMetrics:
    """Aggregated metrics for research loop"""
    loop_id: str
    
    # Efficiency
    feature_pass_rate: float = 0.0
    alpha_admission_rate: float = 0.0
    tournament_win_rate: float = 0.0
    memory_block_rate: float = 0.0
    
    # Quality
    avg_feature_quality: float = 0.0
    avg_alpha_sharpe: float = 0.0
    avg_tournament_score: float = 0.0
    
    # Productivity
    features_per_cycle: float = 0.0
    alphas_per_cycle: float = 0.0
    admissions_per_cycle: float = 0.0
    
    # Learning
    unique_patterns_found: int = 0
    compute_saved_by_memory: int = 0
    
    computed_at: int = 0
