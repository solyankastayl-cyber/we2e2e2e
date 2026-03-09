"""
Phase 8: Accuracy Engine
Measures system prediction accuracy.
"""
import time
import random
from typing import Dict, List, Optional, Any

from .types import (
    AccuracyMetrics,
    VALIDATION_CONFIG
)


class AccuracyEngine:
    """
    Accuracy Engine.
    
    Measures:
    - Direction accuracy (market direction predictions)
    - Scenario accuracy (scenario predictions)
    - Structure accuracy (market structure detection)
    - Timing accuracy (entry/exit timing)
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        self._results: Dict[str, AccuracyMetrics] = {}
    
    def calculate(
        self,
        trades: Optional[List[Dict]] = None,
        predictions: Optional[List[Dict]] = None
    ) -> AccuracyMetrics:
        """
        Calculate accuracy metrics.
        
        Args:
            trades: List of trade results with predictions
            predictions: List of system predictions with outcomes
            
        Returns:
            AccuracyMetrics with all accuracy measures
        """
        run_id = f"accuracy_{int(time.time() * 1000)}"
        
        # Generate mock accuracy data if not provided
        # In production, this would analyze actual predictions vs outcomes
        if not predictions:
            predictions = self._generate_mock_predictions()
        
        # Calculate direction accuracy
        direction_preds = [p for p in predictions if p.get("type") == "direction"]
        direction_correct = len([p for p in direction_preds if p.get("correct")])
        direction_accuracy = direction_correct / len(direction_preds) if direction_preds else 0
        
        # Calculate scenario accuracy
        scenario_preds = [p for p in predictions if p.get("type") == "scenario"]
        scenario_correct = len([p for p in scenario_preds if p.get("correct")])
        scenario_accuracy = scenario_correct / len(scenario_preds) if scenario_preds else 0
        
        # Calculate structure accuracy
        structure_preds = [p for p in predictions if p.get("type") == "structure"]
        structure_correct = len([p for p in structure_preds if p.get("correct")])
        structure_accuracy = structure_correct / len(structure_preds) if structure_preds else 0
        
        # Calculate timing accuracy
        timing_preds = [p for p in predictions if p.get("type") == "timing"]
        timing_correct = len([p for p in timing_preds if p.get("correct")])
        timing_accuracy = timing_correct / len(timing_preds) if timing_preds else 0
        
        # Calculate regime accuracy
        regime_preds = [p for p in predictions if p.get("type") == "regime"]
        regime_correct = len([p for p in regime_preds if p.get("correct")])
        regime_accuracy = regime_correct / len(regime_preds) if regime_preds else 0
        
        # Calculate MTF alignment accuracy
        mtf_preds = [p for p in predictions if p.get("type") == "mtf"]
        mtf_correct = len([p for p in mtf_preds if p.get("correct")])
        mtf_accuracy = mtf_correct / len(mtf_preds) if mtf_preds else 0
        
        # Calculate memory recall accuracy
        memory_preds = [p for p in predictions if p.get("type") == "memory"]
        memory_correct = len([p for p in memory_preds if p.get("correct")])
        memory_accuracy = memory_correct / len(memory_preds) if memory_preds else 0
        
        # Calculate confidence calibration
        calibration = self._calculate_calibration(predictions)
        
        result = AccuracyMetrics(
            run_id=run_id,
            direction_accuracy=round(direction_accuracy, 4),
            scenario_accuracy=round(scenario_accuracy, 4),
            structure_accuracy=round(structure_accuracy, 4),
            timing_accuracy=round(timing_accuracy, 4),
            regime_accuracy=round(regime_accuracy, 4),
            mtf_alignment_accuracy=round(mtf_accuracy, 4),
            memory_recall_accuracy=round(memory_accuracy, 4),
            confidence_calibration=round(calibration["calibration"], 4),
            overconfidence_rate=round(calibration["overconfidence"], 4),
            underconfidence_rate=round(calibration["underconfidence"], 4),
            total_predictions=len(predictions),
            direction_predictions=len(direction_preds),
            scenario_predictions=len(scenario_preds),
            timestamp=int(time.time() * 1000)
        )
        
        self._results[run_id] = result
        
        return result
    
    def get_result(self, run_id: str) -> Optional[AccuracyMetrics]:
        """Get accuracy result by ID"""
        return self._results.get(run_id)
    
    def _generate_mock_predictions(self) -> List[Dict]:
        """
        Generate mock predictions for testing.
        Simulates a system with slight edge.
        """
        predictions = []
        pred_types = [
            ("direction", 0.62),  # 62% direction accuracy
            ("scenario", 0.57),  # 57% scenario accuracy
            ("structure", 0.61),  # 61% structure accuracy
            ("timing", 0.54),  # 54% timing accuracy
            ("regime", 0.65),  # 65% regime accuracy
            ("mtf", 0.68),  # 68% MTF alignment accuracy
            ("memory", 0.52)  # 52% memory recall accuracy
        ]
        
        for pred_type, base_accuracy in pred_types:
            num_preds = random.randint(200, 400)
            
            for i in range(num_preds):
                # Vary accuracy slightly
                accuracy = base_accuracy + random.uniform(-0.05, 0.05)
                correct = random.random() < accuracy
                confidence = random.uniform(0.4, 0.9)
                
                predictions.append({
                    "id": f"pred_{pred_type}_{i}",
                    "type": pred_type,
                    "correct": correct,
                    "confidence": confidence,
                    "timestamp": int(time.time() * 1000) - i * 3600000
                })
        
        return predictions
    
    def _calculate_calibration(self, predictions: List[Dict]) -> Dict[str, float]:
        """
        Calculate confidence calibration.
        
        Well-calibrated: when confidence = 70%, accuracy ≈ 70%
        """
        if not predictions:
            return {"calibration": 0, "overconfidence": 0, "underconfidence": 0}
        
        # Group by confidence bucket
        buckets = {i/10: {"correct": 0, "total": 0} for i in range(1, 10)}
        
        for pred in predictions:
            conf = pred.get("confidence", 0.5)
            bucket_key = round(conf * 10) / 10
            bucket_key = min(0.9, max(0.1, bucket_key))
            
            buckets[bucket_key]["total"] += 1
            if pred.get("correct"):
                buckets[bucket_key]["correct"] += 1
        
        # Calculate calibration error
        total_error = 0
        total_samples = 0
        overconfident = 0
        underconfident = 0
        
        for bucket_conf, data in buckets.items():
            if data["total"] > 0:
                actual_accuracy = data["correct"] / data["total"]
                error = bucket_conf - actual_accuracy
                total_error += abs(error) * data["total"]
                total_samples += data["total"]
                
                if error > 0.1:  # Overconfident
                    overconfident += data["total"]
                elif error < -0.1:  # Underconfident
                    underconfident += data["total"]
        
        calibration = 1 - (total_error / total_samples) if total_samples > 0 else 0
        
        return {
            "calibration": calibration,
            "overconfidence": overconfident / total_samples if total_samples > 0 else 0,
            "underconfidence": underconfident / total_samples if total_samples > 0 else 0
        }


def accuracy_to_dict(metrics: AccuracyMetrics) -> Dict[str, Any]:
    """Convert AccuracyMetrics to JSON-serializable dict"""
    return {
        "runId": metrics.run_id,
        "directionAccuracy": metrics.direction_accuracy,
        "scenarioAccuracy": metrics.scenario_accuracy,
        "structureAccuracy": metrics.structure_accuracy,
        "timingAccuracy": metrics.timing_accuracy,
        "regimeAccuracy": metrics.regime_accuracy,
        "mtfAlignmentAccuracy": metrics.mtf_alignment_accuracy,
        "memoryRecallAccuracy": metrics.memory_recall_accuracy,
        "confidenceCalibration": metrics.confidence_calibration,
        "overconfidenceRate": metrics.overconfidence_rate,
        "underconfidenceRate": metrics.underconfidence_rate,
        "totalPredictions": metrics.total_predictions,
        "directionPredictions": metrics.direction_predictions,
        "scenarioPredictions": metrics.scenario_predictions,
        "timestamp": metrics.timestamp
    }
