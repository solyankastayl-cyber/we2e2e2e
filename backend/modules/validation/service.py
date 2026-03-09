"""
Phase 8: Validation Service
Main orchestrating service for quant validation.
"""
import time
import asyncio
from typing import Dict, List, Optional, Any

from .types import (
    SimulationResult,
    ReplayState,
    MonteCarloResult,
    StressTestResult,
    AccuracyMetrics,
    FailureAnalysis,
    ValidationReport,
    VALIDATION_CONFIG
)
from .simulation import SimulationEngine
from .replay import ReplayEngine, replay_state_to_dict
from .montecarlo import MonteCarloEngine, monte_carlo_to_dict
from .stress import StressTestEngine, stress_test_to_dict
from .accuracy import AccuracyEngine, accuracy_to_dict
from .failures import FailureAnalyzer, failure_analysis_to_dict
from .report import ReportGenerator, report_to_dict
from .real_simulation import RealDataSimulator
from .market_data import market_data_router, fetch_market_data


class ValidationService:
    """
    Main Validation Service.
    
    Orchestrates:
    1. Historical Simulation
    2. Market Replay
    3. Monte Carlo Testing
    4. Stress Testing
    5. Accuracy Measurement
    6. Failure Analysis
    7. Report Generation
    8. Real Data Simulation (Phase 8.5)
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        
        # Initialize all engines
        self.simulation_engine = SimulationEngine(db, config)
        self.replay_engine = ReplayEngine(db, config)
        self.monte_carlo_engine = MonteCarloEngine(db, config)
        self.stress_engine = StressTestEngine(db, config)
        self.accuracy_engine = AccuracyEngine(db, config)
        self.failure_analyzer = FailureAnalyzer(db, config)
        self.report_generator = ReportGenerator(config)
        
        # Phase 8.5: Real data simulator
        self.real_simulator = RealDataSimulator(db, config)
    
    # ==================
    # Real Data (Phase 8.5)
    # ==================
    
    async def fetch_candles(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2022-01-01",
        end_date: str = "2024-01-01",
        provider: str = None
    ) -> Dict[str, Any]:
        """Fetch candles from Coinbase or fallback provider"""
        return await fetch_market_data(symbol, timeframe, start_date, end_date, provider)
    
    async def run_real_simulation(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2022-01-01",
        end_date: str = "2024-01-01",
        initial_capital: float = 100000.0
    ) -> Dict[str, Any]:
        """Run simulation on real Binance data"""
        result = await self.real_simulator.run(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        return self._simulation_to_dict(result)
    
    async def run_validation_batch(
        self,
        symbols: List[str] = None,
        timeframes: List[str] = None,
        start_date: str = "2022-01-01",
        end_date: str = "2024-01-01"
    ) -> Dict[str, Any]:
        """
        Run validation batch on multiple symbols/timeframes.
        Default: BTC 4H, 1H, 1D (Phase 8.5 first batch)
        """
        symbols = symbols or ["BTCUSDT"]
        timeframes = timeframes or ["4h", "1h", "1d"]
        
        results = []
        
        for symbol in symbols:
            for tf in timeframes:
                try:
                    result = await self.real_simulator.run(
                        symbol=symbol,
                        timeframe=tf,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    # Run failure analysis on real trades
                    failure_analysis = None
                    if result.trade_list:
                        failure_analysis = self.failure_analyzer.analyze(result.trade_list)
                    
                    results.append({
                        "symbol": symbol,
                        "timeframe": tf,
                        "runId": result.run_id,
                        "trades": result.trades,
                        "winRate": result.win_rate,
                        "profitFactor": result.profit_factor,
                        "maxDrawdown": result.max_drawdown,
                        "sharpeRatio": result.sharpe_ratio,
                        "totalR": result.total_r,
                        "avgR": result.avg_r,
                        "strategyBreakdown": result.strategy_breakdown,
                        "regimeBreakdown": result.regime_breakdown,
                        "topFailures": [f.value for f in failure_analysis.top_failures[:5]] if failure_analysis else [],
                        "status": result.status
                    })
                except Exception as e:
                    results.append({
                        "symbol": symbol,
                        "timeframe": tf,
                        "status": "FAILED",
                        "error": str(e)
                    })
        
        # Calculate batch summary
        successful = [r for r in results if r.get("status") == "COMPLETED"]
        
        avg_win_rate = sum(r["winRate"] for r in successful) / len(successful) if successful else 0
        avg_pf = sum(r["profitFactor"] for r in successful) / len(successful) if successful else 0
        avg_sharpe = sum(r["sharpeRatio"] for r in successful) / len(successful) if successful else 0
        
        # Aggregate strategy performance
        strategy_totals: Dict[str, Dict] = {}
        for r in successful:
            for strategy, data in r.get("strategyBreakdown", {}).items():
                if strategy not in strategy_totals:
                    strategy_totals[strategy] = {"trades": 0, "wins": 0, "totalR": 0}
                strategy_totals[strategy]["trades"] += data.get("trades", 0)
                strategy_totals[strategy]["wins"] += data.get("wins", 0)
                strategy_totals[strategy]["totalR"] += data.get("totalR", 0)
        
        # Calculate strategy rankings
        strategy_rankings = []
        for strategy, data in strategy_totals.items():
            if data["trades"] > 0:
                strategy_rankings.append({
                    "strategy": strategy,
                    "trades": data["trades"],
                    "winRate": round(data["wins"] / data["trades"], 4),
                    "totalR": round(data["totalR"], 2),
                    "avgR": round(data["totalR"] / data["trades"], 4)
                })
        
        strategy_rankings.sort(key=lambda x: x["avgR"], reverse=True)
        
        # Aggregate failures
        all_failures: Dict[str, int] = {}
        for r in successful:
            for failure in r.get("topFailures", []):
                all_failures[failure] = all_failures.get(failure, 0) + 1
        
        top_failures = sorted(all_failures.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "batchId": f"batch_{int(time.time() * 1000)}",
            "symbols": symbols,
            "timeframes": timeframes,
            "startDate": start_date,
            "endDate": end_date,
            "runsCompleted": len(successful),
            "runsFailed": len(results) - len(successful),
            "summary": {
                "avgWinRate": round(avg_win_rate, 4),
                "avgProfitFactor": round(avg_pf, 2),
                "avgSharpeRatio": round(avg_sharpe, 2),
                "totalTrades": sum(r.get("trades", 0) for r in successful)
            },
            "strategyRankings": strategy_rankings,
            "topFailures": [{"type": f, "count": c} for f, c in top_failures],
            "results": results,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    # ==================
    # Simulation
    # ==================
    
    def run_simulation(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2019-01-01",
        end_date: str = "2024-01-01",
        initial_capital: float = 100000.0,
        isolation_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run historical simulation.
        """
        result = self.simulation_engine.run(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            isolation_run_id=isolation_run_id
        )
        
        return self._simulation_to_dict(result)
    
    def get_simulation(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation result"""
        result = self.simulation_engine.get_run(run_id)
        if result:
            return self._simulation_to_dict(result)
        return None
    
    def list_simulations(self, symbol: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """List simulations"""
        return self.simulation_engine.list_runs(symbol, limit)
    
    # ==================
    # Replay
    # ==================
    
    def start_replay(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2024-01-01",
        end_date: str = "2024-03-01"
    ) -> Dict[str, Any]:
        """Start market replay"""
        state = self.replay_engine.start(symbol, timeframe, start_date, end_date)
        return replay_state_to_dict(state)
    
    def step_replay(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Step replay forward one bar"""
        state = self.replay_engine.step(run_id)
        if state:
            return replay_state_to_dict(state)
        return None
    
    def run_replay_to_completion(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Run replay to completion"""
        state = self.replay_engine.run_to_completion(run_id)
        if state:
            return replay_state_to_dict(state)
        return None
    
    def get_replay_state(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get current replay state"""
        state = self.replay_engine.get_state(run_id)
        if state:
            return replay_state_to_dict(state)
        return None
    
    def get_replay_events(self, run_id: str) -> Dict[str, Any]:
        """Get replay events"""
        return self.replay_engine.get_events(run_id)
    
    def pause_replay(self, run_id: str) -> bool:
        """Pause replay"""
        return self.replay_engine.pause(run_id)
    
    def resume_replay(self, run_id: str) -> bool:
        """Resume replay"""
        return self.replay_engine.resume(run_id)
    
    def stop_replay(self, run_id: str) -> bool:
        """Stop replay"""
        return self.replay_engine.stop(run_id)
    
    def list_replays(self, limit: int = 20) -> List[Dict]:
        """List replays"""
        return self.replay_engine.list_replays(limit)
    
    # ==================
    # Monte Carlo
    # ==================
    
    def run_monte_carlo(
        self,
        base_win_rate: float = 0.60,
        base_profit_factor: float = 1.5,
        iterations: int = 1000
    ) -> Dict[str, Any]:
        """Run Monte Carlo simulation"""
        result = self.monte_carlo_engine.run(
            base_win_rate=base_win_rate,
            base_profit_factor=base_profit_factor,
            iterations=iterations
        )
        return monte_carlo_to_dict(result)
    
    def get_monte_carlo(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get Monte Carlo result"""
        result = self.monte_carlo_engine.get_result(run_id)
        if result:
            return monte_carlo_to_dict(result)
        return None
    
    # ==================
    # Stress Test
    # ==================
    
    def run_stress_test(
        self,
        scenarios: Optional[List[str]] = None,
        load_levels: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Run stress test"""
        result = self.stress_engine.run(scenarios, load_levels)
        return stress_test_to_dict(result)
    
    def get_stress_test(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get stress test result"""
        result = self.stress_engine.get_result(run_id)
        if result:
            return stress_test_to_dict(result)
        return None
    
    # ==================
    # Accuracy
    # ==================
    
    def calculate_accuracy(self) -> Dict[str, Any]:
        """Calculate system accuracy"""
        result = self.accuracy_engine.calculate()
        return accuracy_to_dict(result)
    
    def get_accuracy(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get accuracy result"""
        result = self.accuracy_engine.get_result(run_id)
        if result:
            return accuracy_to_dict(result)
        return None
    
    # ==================
    # Failures
    # ==================
    
    def analyze_failures(self) -> Dict[str, Any]:
        """Analyze system failures"""
        result = self.failure_analyzer.analyze()
        return failure_analysis_to_dict(result)
    
    def get_failure_analysis(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get failure analysis"""
        result = self.failure_analyzer.get_result(run_id)
        if result:
            return failure_analysis_to_dict(result)
        return None
    
    # ==================
    # Report
    # ==================
    
    def generate_report(
        self,
        simulation_run_id: Optional[str] = None,
        run_full_validation: bool = True,
        isolation_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive validation report.
        
        Args:
            simulation_run_id: Existing simulation to use
            run_full_validation: Run all validation steps
            isolation_context: Validation isolation context
        """
        simulation_result = None
        accuracy_metrics = None
        failure_analysis = None
        monte_carlo_result = None
        
        if simulation_run_id:
            simulation_result = self.simulation_engine.get_run(simulation_run_id)
        
        if run_full_validation:
            # Run simulation if not provided
            if not simulation_result:
                simulation_result = self.simulation_engine.run()
            
            # Run accuracy
            accuracy_metrics = self.accuracy_engine.calculate()
            
            # Run failure analysis
            if simulation_result and simulation_result.trade_list:
                failure_analysis = self.failure_analyzer.analyze(simulation_result.trade_list)
            else:
                failure_analysis = self.failure_analyzer.analyze()
            
            # Run Monte Carlo
            if simulation_result:
                monte_carlo_result = self.monte_carlo_engine.run(
                    base_win_rate=simulation_result.win_rate,
                    base_profit_factor=simulation_result.profit_factor
                )
            else:
                monte_carlo_result = self.monte_carlo_engine.run()
        
        report = self.report_generator.generate(
            simulation_result=simulation_result,
            accuracy_metrics=accuracy_metrics,
            failure_analysis=failure_analysis,
            monte_carlo_result=monte_carlo_result,
            isolation_context=isolation_context
        )
        
        return report_to_dict(report)
    
    def get_report(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get validation report"""
        report = self.report_generator.get_report(run_id)
        if report:
            return report_to_dict(report)
        return None
    
    def list_reports(self, limit: int = 20) -> List[Dict]:
        """List validation reports"""
        return self.report_generator.list_reports(limit)
    
    # ==================
    # Health
    # ==================
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": self.config.get("enabled", True),
            "version": self.config.get("version", "validation_v1_phase8"),
            "status": "ok",
            "components": {
                "simulation_engine": "ok",
                "replay_engine": "ok",
                "monte_carlo_engine": "ok",
                "stress_engine": "ok",
                "accuracy_engine": "ok",
                "failure_analyzer": "ok",
                "report_generator": "ok"
            },
            "config": {
                "minTradesForSignificance": self.config.get("min_trades_for_significance", 30),
                "monteCarloIterations": self.config.get("monte_carlo_iterations", 1000),
                "stressLevels": self.config.get("stress_levels", [10, 50, 100, 500, 1000])
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    # ==================
    # Private
    # ==================
    
    def _simulation_to_dict(self, result: SimulationResult) -> Dict[str, Any]:
        """Convert SimulationResult to dict"""
        return {
            "runId": result.run_id,
            "config": {
                "symbol": result.config.symbol,
                "timeframe": result.config.timeframe,
                "startDate": result.config.start_date,
                "endDate": result.config.end_date,
                "initialCapital": result.config.initial_capital
            },
            "trades": result.trades,
            "wins": result.wins,
            "losses": result.losses,
            "winRate": result.win_rate,
            "profitFactor": result.profit_factor,
            "totalPnL": result.total_pnl,
            "totalR": result.total_r,
            "avgR": result.avg_r,
            "maxDrawdown": result.max_drawdown,
            "sharpeRatio": result.sharpe_ratio,
            "maxConsecutiveWins": result.max_consecutive_wins,
            "maxConsecutiveLosses": result.max_consecutive_losses,
            "avgTradeDuration": result.avg_trade_duration,
            "bestTradeR": result.best_trade_r,
            "worstTradeR": result.worst_trade_r,
            "regimeBreakdown": result.regime_breakdown,
            "strategyBreakdown": result.strategy_breakdown,
            "startedAt": result.started_at,
            "completedAt": result.completed_at,
            "durationMs": result.duration_ms,
            "status": result.status
        }
