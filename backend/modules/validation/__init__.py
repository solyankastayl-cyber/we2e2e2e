"""
Phase 8: Quant Validation Layer
Final validation layer to answer: "Does the system have real edge?"
"""

from .types import (
    SimulationConfig,
    SimulationResult,
    ReplayState,
    MonteCarloResult,
    StressTestResult,
    AccuracyMetrics,
    FailureAnalysis,
    ValidationReport,
    FailureType,
    TradeOutcome
)
from .simulation import SimulationEngine
from .replay import ReplayEngine
from .montecarlo import MonteCarloEngine
from .stress import StressTestEngine
from .accuracy import AccuracyEngine
from .failures import FailureAnalyzer
from .report import ReportGenerator
from .service import ValidationService

__all__ = [
    'SimulationConfig',
    'SimulationResult',
    'ReplayState',
    'MonteCarloResult',
    'StressTestResult',
    'AccuracyMetrics',
    'FailureAnalysis',
    'ValidationReport',
    'FailureType',
    'TradeOutcome',
    'SimulationEngine',
    'ReplayEngine',
    'MonteCarloEngine',
    'StressTestEngine',
    'AccuracyEngine',
    'FailureAnalyzer',
    'ReportGenerator',
    'ValidationService'
]
