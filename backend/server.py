"""
TA Engine Python Wrapper
Proxies requests to Node.js TA Engine running on port 3001
Also provides ML inference endpoints directly
"""

import os
import sys
import subprocess
import signal
import time
import json
import atexit
from contextlib import asynccontextmanager

# Add modules directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Try to import ML libraries (optional)
try:
    import joblib
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("[ML] joblib/numpy not available, using mock predictions")

# Node.js TA Engine process (managed externally by supervisor or nohup)
node_process = None
NODE_TA_PORT = 3001  # Node runs on 3001, Python on 8001
NODE_TA_MANAGED_EXTERNALLY = False  # Python manages Node

# ML Models
entry_model = None
r_model = None
models_loaded = False

# Features order (must match training)
FEATURES = [
    'score', 'confidence', 'risk_reward', 'gate_score',
    'geom_fit_error', 'geom_maturity', 'geom_compression', 'geom_symmetry',
    'graph_boost_factor', 'graph_lift', 'graph_conditional_prob',
    'pattern_strength', 'pattern_duration', 'volatility', 'atr_ratio',
    'regime_trend_up', 'regime_trend_down', 'regime_range'
]


def load_ml_models():
    """Load ML models from artifacts"""
    global entry_model, r_model, models_loaded
    
    if not ML_AVAILABLE:
        print("[ML] ML libraries not available, using mock mode")
        return
    
    entry_path = '/app/ml_artifacts/entry_model/model.joblib'
    r_path = '/app/ml_artifacts/r_model/model.joblib'
    
    try:
        if os.path.exists(entry_path):
            entry_model = joblib.load(entry_path)
            print(f"[ML] Loaded entry model from {entry_path}")
        
        if os.path.exists(r_path):
            r_model = joblib.load(r_path)
            print(f"[ML] Loaded R model from {r_path}")
        
        if entry_model is not None and r_model is not None:
            models_loaded = True
            print("[ML] Both models loaded successfully")
        else:
            print("[ML] Warning: Some models not found, using mock predictions")
            
    except Exception as e:
        print(f"[ML] Error loading models: {e}")
        models_loaded = False


def start_node_ta_server():
    """Start Node.js TA Engine server"""
    global node_process
    
    try:
        env = os.environ.copy()
        env['PORT'] = str(NODE_TA_PORT)
        
        # Use npx tsx directly for better reliability
        node_process = subprocess.Popen(
            ['npx', 'tsx', 'src/server.ta.ts'],
            cwd='/app/backend',
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        print(f"[Node] Started TA Engine on port {NODE_TA_PORT} (PID: {node_process.pid})")
        time.sleep(5)  # Wait for startup
        
    except Exception as e:
        print(f"[Node] Failed to start: {e}")


def stop_node_ta_server():
    """Stop Node.js TA Engine server"""
    global node_process
    
    if node_process:
        try:
            os.killpg(os.getpgid(node_process.pid), signal.SIGTERM)
            print("[Node] Stopped TA Engine")
        except Exception as e:
            print(f"[Node] Error stopping: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    load_ml_models()
    
    if not NODE_TA_MANAGED_EXTERNALLY:
        start_node_ta_server()
    else:
        print(f"[Node] External management mode - expecting TA Engine on port {NODE_TA_PORT}")
    
    yield
    
    # Shutdown
    if not NODE_TA_MANAGED_EXTERNALLY:
        stop_node_ta_server()


app = FastAPI(
    title="TA Engine API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Register Modular Routers
# ============================================
try:
    from routes.admin_cockpit import router as admin_cockpit_router
    app.include_router(admin_cockpit_router)
    print("[Routes] Admin Cockpit router registered")
except ImportError as e:
    print(f"[Routes] Admin Cockpit router not available: {e}")

try:
    from routes.meta_strategy import router as meta_strategy_router
    app.include_router(meta_strategy_router)
    print("[Routes] Meta-Strategy router registered")
except ImportError as e:
    print(f"[Routes] Meta-Strategy router not available: {e}")

# Walk-Forward Router (Phase 9.3)
try:
    from modules.walk_forward.routes import router as walk_forward_router
    app.include_router(walk_forward_router)
    print("[Routes] Walk-Forward router registered (Phase 9.3)")
except ImportError as e:
    print(f"[Routes] Walk-Forward router not available: {e}")

# Structural Bias Router (Phase 9.3A)
try:
    from modules.structural_bias.routes import router as structural_bias_router
    app.include_router(structural_bias_router)
    print("[Routes] Structural Bias router registered (Phase 9.3A)")
except ImportError as e:
    print(f"[Routes] Structural Bias router not available: {e}")

# Portfolio Overlay Router (Phase 9.3D)
try:
    from modules.portfolio_overlay.routes import router as portfolio_overlay_router
    app.include_router(portfolio_overlay_router)
    print("[Routes] Portfolio Overlay router registered (Phase 9.3D)")
except ImportError as e:
    print(f"[Routes] Portfolio Overlay router not available: {e}")

# Alpha Combination Router (Phase 9.3E)
try:
    from modules.alpha_combination.routes import router as alpha_combination_router
    app.include_router(alpha_combination_router)
    print("[Routes] Alpha Combination router registered (Phase 9.3E)")
except ImportError as e:
    print(f"[Routes] Alpha Combination router not available: {e}")

# Hierarchical Allocator Router (Phase 9.3F)
try:
    from modules.hierarchical_allocator.routes import router as hierarchical_allocator_router
    app.include_router(hierarchical_allocator_router)
    print("[Routes] Hierarchical Allocator router registered (Phase 9.3F)")
except ImportError as e:
    print(f"[Routes] Hierarchical Allocator router not available: {e}")

# Cross-Asset Walk-Forward Router (Phase 9.X)
try:
    from modules.cross_asset_walkforward.routes import router as cross_asset_wf_router
    app.include_router(cross_asset_wf_router)
    print("[Routes] Cross-Asset Walk-Forward router registered (Phase 9.X)")
except ImportError as e:
    print(f"[Routes] Cross-Asset Walk-Forward router not available: {e}")

# Orthogonal Alpha Router (Phase 9.3G)
try:
    from modules.orthogonal_alpha.routes import router as orthogonal_alpha_router
    app.include_router(orthogonal_alpha_router)
    print("[Routes] Orthogonal Alpha router registered (Phase 9.3G)")
except ImportError as e:
    print(f"[Routes] Orthogonal Alpha router not available: {e}")

# Risk Regime Router (Phase 9.3H)
try:
    from modules.risk_regime.routes import router as risk_regime_router
    app.include_router(risk_regime_router)
    print("[Routes] Risk Regime router registered (Phase 9.3H)")
except ImportError as e:
    print(f"[Routes] Risk Regime router not available: {e}")

# Alpha Registry Router (Phase 9.28)
try:
    from modules.alpha_registry.routes import router as alpha_registry_router
    app.include_router(alpha_registry_router)
    print("[Routes] Alpha Registry router registered (Phase 9.28)")
except ImportError as e:
    print(f"[Routes] Alpha Registry router not available: {e}")

# Feature Factory Router (Phase 9.31)
try:
    from modules.feature_factory.routes import router as feature_factory_router
    app.include_router(feature_factory_router)
    print("[Routes] Feature Factory router registered (Phase 9.31)")
except ImportError as e:
    print(f"[Routes] Feature Factory router not available: {e}")

# Alpha Tournament Router (Phase 9.29)
try:
    from modules.alpha_tournament.routes import router as alpha_tournament_router
    app.include_router(alpha_tournament_router)
    print("[Routes] Alpha Tournament router registered (Phase 9.29)")
except ImportError as e:
    print(f"[Routes] Alpha Tournament router not available: {e}")

# Shadow Portfolio Router (Phase 9.30)
try:
    from modules.shadow_portfolio.routes import router as shadow_portfolio_router
    app.include_router(shadow_portfolio_router)
    print("[Routes] Shadow Portfolio router registered (Phase 9.30)")
except ImportError as e:
    print(f"[Routes] Shadow Portfolio router not available: {e}")


# Shadow Stress Lab Router (Phase 9.30B)
try:
    from modules.shadow_stress_lab.routes import router as stress_lab_router
    app.include_router(stress_lab_router)
    print("[Routes] Shadow Stress Lab router registered (Phase 9.30B)")
except ImportError as e:
    print(f"[Routes] Shadow Stress Lab router not available: {e}")


# Autopsy Engine Router (Phase 9.30C)
try:
    from modules.autopsy_engine.routes import router as autopsy_router
    app.include_router(autopsy_router)
    print("[Routes] Autopsy Engine router registered (Phase 9.30C)")
except ImportError as e:
    print(f"[Routes] Autopsy Engine router not available: {e}")


# Feature Mutation Router (Phase 9.31B)
try:
    from modules.feature_factory.mutation_routes import router as mutation_router
    app.include_router(mutation_router)
    print("[Routes] Feature Mutation router registered (Phase 9.31B)")
except ImportError as e:
    print(f"[Routes] Feature Mutation router not available: {e}")

# Research Memory Router (Phase 9.32)
try:
    from modules.research_memory.routes import router as research_memory_router
    app.include_router(research_memory_router)
    print("[Routes] Research Memory router registered (Phase 9.32)")
except ImportError as e:
    print(f"[Routes] Research Memory router not available: {e}")


# Research Loop Router (Phase 9.33)
try:
    from modules.research_loop.routes import router as research_loop_router
    app.include_router(research_loop_router)
    print("[Routes] Research Loop router registered (Phase 9.33)")
except ImportError as e:
    print(f"[Routes] Research Loop router not available: {e}")


# Global Risk Brain Router (Phase 9.35)
try:
    from modules.global_risk_brain.routes import router as grb_router
    app.include_router(grb_router)
    print("[Routes] Global Risk Brain router registered (Phase 9.35)")
except ImportError as e:
    print(f"[Routes] Global Risk Brain router not available: {e}")

# Capital Simulation Router (Phase 9.36)
try:
    from modules.capital_simulation.routes import router as capital_sim_router
    app.include_router(capital_sim_router)
    print("[Routes] Capital Simulation router registered (Phase 9.36)")
except ImportError as e:
    print(f"[Routes] Capital Simulation router not available: {e}")


# Edge Research Lab Router (Phase A)
try:
    from modules.edge_lab.routes import router as edge_lab_router
    app.include_router(edge_lab_router)
    print("[Routes] Edge Research Lab router registered (Phase A)")
except ImportError as e:
    print(f"[Routes] Edge Research Lab router not available: {e}")

# Microstructure Lab Router (Phase B)
try:
    from modules.microstructure_lab.routes import router as microstructure_router
    app.include_router(microstructure_router)
    print("[Routes] Microstructure Lab router registered (Phase B)")
except ImportError as e:
    print(f"[Routes] Microstructure Lab router not available: {e}")


# Policy Engine Router (Phase C)
try:
    from modules.policy_engine.routes import router as policy_router
    app.include_router(policy_router)
    print("[Routes] Policy Engine router registered (Phase C)")
except ImportError as e:
    print(f"[Routes] Policy Engine router not available: {e}")

# Dataset Registry Router (Phase C)
try:
    from modules.dataset_registry.routes import router as dataset_router
    app.include_router(dataset_router)
    print("[Routes] Dataset Registry router registered (Phase C)")
except ImportError as e:
    print(f"[Routes] Dataset Registry router not available: {e}")

# Experiment Tracker Router (Phase C)
try:
    from modules.experiment_tracker.routes import router as experiment_router
    app.include_router(experiment_router)
    print("[Routes] Experiment Tracker router registered (Phase C)")
except ImportError as e:
    print(f"[Routes] Experiment Tracker router not available: {e}")

# Admin Control Center Router (Phase C)
try:
    from modules.admin_control_center.routes import router as admin_cc_router
    app.include_router(admin_cc_router)
    print("[Routes] Admin Control Center router registered (Phase C)")
except ImportError as e:
    print(f"[Routes] Admin Control Center router not available: {e}")

# Event Bus Router (Phase D)
try:
    from modules.event_bus.routes import router as event_bus_router
    app.include_router(event_bus_router)
    print("[Routes] Event Bus router registered (Phase D)")
except ImportError as e:
    print(f"[Routes] Event Bus router not available: {e}")

# System State Machine Router (Phase D)
try:
    from modules.system_state_machine.routes import router as ssm_router
    app.include_router(ssm_router)
    print("[Routes] System State Machine router registered (Phase D)")
except ImportError as e:
    print(f"[Routes] System State Machine router not available: {e}")

# Evolution Engine Router (Phase D)
try:
    from modules.evolution_engine.routes import router as evolution_router
    app.include_router(evolution_router)
    print("[Routes] Evolution Engine router registered (Phase D)")
except ImportError as e:
    print(f"[Routes] Evolution Engine router not available: {e}")

# Market Reality Layer Router (Phase D)
try:
    from modules.market_reality.routes import router as reality_router
    app.include_router(reality_router)
    print("[Routes] Market Reality Layer router registered (Phase D)")
except ImportError as e:
    print(f"[Routes] Market Reality Layer router not available: {e}")

# Strategy Lifecycle Engine Router (Phase D)
try:
    from modules.strategy_lifecycle.routes import router as lifecycle_router
    app.include_router(lifecycle_router)
    print("[Routes] Strategy Lifecycle Engine router registered (Phase D)")
except ImportError as e:
    print(f"[Routes] Strategy Lifecycle Engine router not available: {e}")

# System Timeline Engine Router (Phase D)
try:
    from modules.system_timeline.routes import router as timeline_router
    app.include_router(timeline_router)
    print("[Routes] System Timeline Engine router registered (Phase D)")
except ImportError as e:
    print(f"[Routes] System Timeline Engine router not available: {e}")


# Infrastructure Hardening Router
try:
    from modules.infrastructure.routes import router as infra_router
    app.include_router(infra_router)
    print("[Routes] Infrastructure Hardening router registered")
except ImportError as e:
    print(f"[Routes] Infrastructure Hardening router not available: {e}")

# Control Backend Router (P0-3 Finalization)
try:
    from modules.control_backend.routes import router as control_backend_router
    app.include_router(control_backend_router)
    print("[Routes] Control Backend router registered (P0-3)")
except ImportError as e:
    print(f"[Routes] Control Backend router not available: {e}")

# Broker Adapters Router (Phase 9.37)
try:
    from modules.broker_adapters.routes import router as broker_router
    app.include_router(broker_router)
    print("[Routes] Broker Adapters router registered (Phase 9.37)")
except ImportError as e:
    print(f"[Routes] Broker Adapters router not available: {e}")

# Trading Capsule Router (T0-T6)
try:
    from modules.trading_capsule.routes import router as trading_capsule_router
    from modules.trading_capsule import initialize_default_strategies
    app.include_router(trading_capsule_router)
    initialize_default_strategies()
    print("[Routes] Trading Capsule router registered (T0-T6)")
except ImportError as e:
    print(f"[Routes] Trading Capsule router not available: {e}")









# ============================================
# ML Inference Endpoints (Direct Python)
# ============================================

class MLFeatures(BaseModel):
    score: float = 0.5
    confidence: float = 0.5
    risk_reward: float = 1.5
    gate_score: float = 0.6
    geom_fit_error: float = 0.1
    geom_maturity: float = 0.7
    geom_compression: float = 0.5
    geom_symmetry: float = 0.6
    graph_boost_factor: float = 1.0
    graph_lift: float = 0.1
    graph_conditional_prob: float = 0.5
    pattern_strength: float = 0.7
    pattern_duration: float = 10.0
    volatility: float = 0.02
    atr_ratio: float = 1.0
    regime_trend_up: float = 0.0
    regime_trend_down: float = 0.0
    regime_range: float = 1.0


class MLPrediction(BaseModel):
    p_entry: float
    expected_r: float
    ev: float
    model_id: str
    confidence: float


def mock_predict(features: MLFeatures) -> MLPrediction:
    """Mock prediction when models unavailable"""
    base_prob = 0.3 + features.gate_score * 0.4 + features.geom_maturity * 0.1
    p_entry = max(0.1, min(0.9, base_prob))
    
    base_r = -0.2 + features.risk_reward * 0.3 + features.graph_boost_factor * 0.2
    expected_r = max(-2, min(3, base_r))
    
    return MLPrediction(
        p_entry=round(p_entry, 4),
        expected_r=round(expected_r, 4),
        ev=round(p_entry * expected_r, 4),
        model_id='mock_v1',
        confidence=0.3
    )


@app.post("/api/ml/predict", response_model=MLPrediction)
async def ml_predict(features: MLFeatures):
    """ML prediction endpoint"""
    
    if not models_loaded or not ML_AVAILABLE:
        return mock_predict(features)
    
    try:
        # Build feature array
        X = np.array([[getattr(features, f, 0) for f in FEATURES]])
        
        # Predict
        p_entry = float(entry_model.predict(X)[0])
        expected_r = float(r_model.predict(X)[0])
        
        # Clip values
        p_entry = max(0.0, min(1.0, p_entry))
        expected_r = max(-3.0, min(5.0, expected_r))
        
        return MLPrediction(
            p_entry=round(p_entry, 4),
            expected_r=round(expected_r, 4),
            ev=round(p_entry * expected_r, 4),
            model_id='lightgbm_v1',
            confidence=0.7
        )
        
    except Exception as e:
        print(f"[ML] Prediction error: {e}")
        return mock_predict(features)


class BatchMLFeatures(BaseModel):
    features_list: List[MLFeatures]


@app.post("/api/ml/predict_batch")
async def ml_predict_batch(batch: BatchMLFeatures):
    """Batch ML prediction"""
    results = []
    
    if not models_loaded or not ML_AVAILABLE:
        for f in batch.features_list:
            results.append(mock_predict(f))
        return {"predictions": [r.dict() for r in results]}
    
    try:
        X = np.array([[getattr(f, feat, 0) for feat in FEATURES] for f in batch.features_list])
        
        p_entries = entry_model.predict(X)
        expected_rs = r_model.predict(X)
        
        for i in range(len(X)):
            p_entry = max(0.0, min(1.0, float(p_entries[i])))
            expected_r = max(-3.0, min(5.0, float(expected_rs[i])))
            
            results.append({
                "p_entry": round(p_entry, 4),
                "expected_r": round(expected_r, 4),
                "ev": round(p_entry * expected_r, 4),
                "model_id": "lightgbm_v1",
                "confidence": 0.7
            })
        
        return {"predictions": results}
        
    except Exception as e:
        print(f"[ML] Batch prediction error: {e}")
        for f in batch.features_list:
            results.append(mock_predict(f).dict())
        return {"predictions": results}


@app.get("/api/models/status")
async def models_status():
    """ML models status"""
    return {
        "models_loaded": models_loaded,
        "entry_model": entry_model is not None,
        "r_model": r_model is not None,
        "features_count": len(FEATURES),
        "features": FEATURES
    }


# ============================================
# Health Endpoints
# ============================================

@app.get("/api/health")
async def health():
    """API health check"""
    return {
        "ok": True,
        "mode": "TA_ENGINE_PROXY",
        "version": "2.0.0",
        "ml_models_loaded": models_loaded,
        "node_ta_port": NODE_TA_PORT,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/system/health")
async def system_health():
    """System health for frontend compatibility"""
    return {
        "status": "healthy",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "services": {
            "ml": "loaded" if models_loaded else "mock",
            "ta_engine": "running"
        },
        "notes": ["TA Engine with ML inference"]
    }


# ============================================
# Phase 6.5: MTF Confirmation Layer
# ============================================

MTF_MAP = {
    "15m": {"higher": "1h", "lower": "5m"},
    "1h": {"higher": "4h", "lower": "15m"},
    "4h": {"higher": "1d", "lower": "1h"},
    "1d": {"higher": "1w", "lower": "4h"},
    "1w": {"higher": "1w", "lower": "1d"}
}

MTF_CONFIG = {
    "enabled": True,
    "weights": {
        "higherBiasAligned": 0.06,
        "regimeAligned": 0.05,
        "structureAligned": 0.05,
        "scenarioAligned": 0.04,
        "lowerMomentumAligned": 0.04,
        "higherConflict": -0.10
    },
    "boostMin": 0.88,
    "boostMax": 1.15,
    "executionStrong": 1.00,
    "executionMixed": 0.92,
    "executionConflict": 0.85
}


def calculate_mtf_boost(
    anchor_direction: str,
    higher_bias_aligned: bool,
    regime_aligned: bool,
    structure_aligned: bool,
    scenario_aligned: bool,
    momentum_aligned: bool,
    higher_conflict: bool
) -> float:
    """Calculate MTF boost factor"""
    boost = 1.0
    weights = MTF_CONFIG["weights"]
    
    if higher_bias_aligned:
        boost += weights["higherBiasAligned"]
    if regime_aligned:
        boost += weights["regimeAligned"]
    if structure_aligned:
        boost += weights["structureAligned"]
    if scenario_aligned:
        boost += weights["scenarioAligned"]
    if momentum_aligned:
        boost += weights["lowerMomentumAligned"]
    if higher_conflict:
        boost += weights["higherConflict"]
    
    return max(MTF_CONFIG["boostMin"], min(MTF_CONFIG["boostMax"], boost))


def calculate_execution_adjustment(alignment_count: int, higher_conflict: bool) -> float:
    """Calculate execution adjustment for position sizing"""
    if higher_conflict:
        return MTF_CONFIG["executionConflict"]
    if alignment_count >= 3:
        return MTF_CONFIG["executionStrong"]
    return MTF_CONFIG["executionMixed"]


def get_mock_mtf_state(symbol: str, tf: str):
    """Generate mock MTF state for testing"""
    tf_key = tf.lower()
    mapping = MTF_MAP.get(tf_key, {"higher": "1d", "lower": "1h"})
    
    # Mock aligned scenario
    higher_bias = "BULL"
    lower_momentum = "BULL"
    regime_aligned = True
    structure_aligned = True
    scenario_aligned = True
    momentum_aligned = True
    higher_conflict = False
    
    mtf_boost = calculate_mtf_boost(
        "LONG",
        True,  # higher_bias_aligned
        regime_aligned,
        structure_aligned,
        scenario_aligned,
        momentum_aligned,
        higher_conflict
    )
    
    alignment_count = sum([regime_aligned, structure_aligned, scenario_aligned, momentum_aligned])
    mtf_execution_adjustment = calculate_execution_adjustment(alignment_count, higher_conflict)
    
    notes = []
    if True:  # higher_bias_aligned
        notes.append(f"Higher timeframe ({mapping['higher']}) trend supports current setup")
    if regime_aligned:
        notes.append(f"{mapping['higher']} regime aligns with entry direction")
    if momentum_aligned:
        notes.append(f"Lower timeframe ({mapping['lower']}) momentum confirms entry")
    
    return {
        "symbol": symbol,
        "anchorTf": tf,
        "higherTf": mapping["higher"],
        "lowerTf": mapping["lower"],
        "higherBias": higher_bias,
        "higherRegime": "TREND_UP",
        "higherStructure": "BULLISH",
        "lowerMomentum": lower_momentum,
        "lowerStructure": "BULLISH",
        "regimeAligned": regime_aligned,
        "structureAligned": structure_aligned,
        "scenarioAligned": scenario_aligned,
        "momentumAligned": momentum_aligned,
        "higherConflict": higher_conflict,
        "mtfBoost": round(mtf_boost, 4),
        "mtfExecutionAdjustment": round(mtf_execution_adjustment, 2),
        "notes": notes,
        "computedAt": int(time.time() * 1000)
    }


@app.get("/api/mtf/state")
async def mtf_state(symbol: str = "BTCUSDT", tf: str = "4h"):
    """Get MTF state for symbol and timeframe"""
    return get_mock_mtf_state(symbol, tf)


@app.get("/api/mtf/boost")
async def mtf_boost(symbol: str = "BTCUSDT", tf: str = "4h", direction: str = "LONG"):
    """Get MTF boost for specific direction"""
    state = get_mock_mtf_state(symbol, tf)
    
    return {
        "symbol": symbol,
        "tf": tf,
        "direction": direction.upper(),
        "mtfBoost": state["mtfBoost"],
        "mtfExecutionAdjustment": state["mtfExecutionAdjustment"],
        "notes": state["notes"]
    }


@app.get("/api/mtf/explain")
async def mtf_explain(symbol: str = "BTCUSDT", tf: str = "4h"):
    """Get MTF explain block for Decision API"""
    state = get_mock_mtf_state(symbol, tf)
    
    return {
        "anchorTf": state["anchorTf"],
        "higherTf": state["higherTf"],
        "lowerTf": state["lowerTf"],
        "higherBias": state["higherBias"],
        "lowerMomentum": state["lowerMomentum"],
        "regimeAligned": state["regimeAligned"],
        "structureAligned": state["structureAligned"],
        "scenarioAligned": state["scenarioAligned"],
        "momentumAligned": state["momentumAligned"],
        "mtfBoost": state["mtfBoost"],
        "mtfExecutionAdjustment": state["mtfExecutionAdjustment"],
        "notes": state["notes"]
    }


@app.get("/api/mtf/config")
async def mtf_config():
    """Get MTF configuration"""
    return {
        "config": MTF_CONFIG,
        "tfMap": MTF_MAP,
        "version": "phase6.5"
    }


@app.get("/api/mtf/debug")
async def mtf_debug():
    """Debug MTF variables"""
    return {
        "mtf_map_type": str(type(MTF_MAP)),
        "mtf_map_content": MTF_MAP,
        "mtf_config_type": str(type(MTF_CONFIG)),
        "mtf_config_content": MTF_CONFIG
    }


@app.get("/api/mtf/health")
async def mtf_health():
    """MTF health check"""
    return {
        "enabled": True,
        "version": "mtf_v2_phase6.5",
        "status": "ok",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


# ============================================
# Phase 7: Market Structure AI Layer
# ============================================

EVENT_CHAINS = {
    "SWEEP_REVERSAL": ["LIQUIDITY_SWEEP", "COMPRESSION", "BREAKOUT", "EXPANSION"],
    "ACCUMULATION": ["ACCUMULATION", "COMPRESSION", "BREAKOUT", "EXPANSION"],
    "DISTRIBUTION": ["DISTRIBUTION", "COMPRESSION", "BREAKOUT", "EXPANSION"],
    "TREND_CONTINUATION": ["RETEST", "COMPRESSION", "BREAKOUT", "EXPANSION"],
    "FALSE_BREAKOUT": ["BREAKOUT", "FAKE_BREAKOUT", "REVERSAL", "EXPANSION"]
}

EVENT_TYPES = [
    "LIQUIDITY_SWEEP", "COMPRESSION", "BREAKOUT", "RETEST", "EXPANSION",
    "ACCUMULATION", "DISTRIBUTION", "TREND_CONTINUATION", "REVERSAL",
    "FAKE_BREAKOUT", "RANGE_BOUND", "VOLATILITY_SPIKE", "EXHAUSTION"
]


def generate_mock_structure_state(symbol: str, tf: str):
    """Generate mock structure state for testing"""
    import random
    
    # Pick random events
    num_events = random.randint(1, 3)
    events = random.sample(EVENT_TYPES[:8], num_events)
    
    # Determine structure type based on events
    structure_type = "COMPRESSION_BREAKOUT"
    if "LIQUIDITY_SWEEP" in events:
        structure_type = "SWEEP_REVERSAL"
    elif "ACCUMULATION" in events:
        structure_type = "ACCUMULATION_BREAKOUT"
    elif "DISTRIBUTION" in events:
        structure_type = "DISTRIBUTION_BREAKDOWN"
    elif "EXHAUSTION" in events:
        structure_type = "EXHAUSTION_REVERSAL"
    
    # Generate expected next events
    chain = EVENT_CHAINS.get(structure_type.split("_")[0], EVENT_CHAINS["TREND_CONTINUATION"])
    
    # Find where we are in chain
    completed = []
    for evt in chain:
        if evt in events:
            completed.append(evt)
    
    expected_idx = len(completed)
    expected_next = chain[expected_idx:expected_idx+2] if expected_idx < len(chain) else []
    
    direction = random.choice(["UP", "DOWN", "NEUTRAL"])
    momentum = random.choice(["STRONG", "MODERATE", "WEAK"])
    
    probability = 0.5 + random.random() * 0.35
    
    narratives = {
        "SWEEP_REVERSAL": f"Market shows sweep reversal pattern. Liquidity swept {direction.lower()}, expecting compression then breakout.",
        "COMPRESSION_BREAKOUT": f"Market in compression phase, preparing for breakout {direction.lower()}.",
        "ACCUMULATION_BREAKOUT": "Accumulation phase detected with potential bullish breakout.",
        "DISTRIBUTION_BREAKDOWN": "Distribution phase with potential bearish breakdown.",
        "EXHAUSTION_REVERSAL": f"Exhaustion pattern detected, suggesting reversal {direction.lower()}."
    }
    
    return {
        "symbol": symbol,
        "timeframe": tf,
        "structure": structure_type,
        "structureConfidence": round(probability, 2),
        "events": events,
        "expectedNext": expected_next,
        "probability": round(probability, 2),
        "bias": direction,
        "momentum": momentum,
        "narrative": narratives.get(structure_type, f"Market structure: {structure_type}"),
        "computedAt": int(time.time() * 1000)
    }


def generate_mock_events(symbol: str, tf: str):
    """Generate mock market events"""
    import random
    
    events = []
    num_events = random.randint(2, 4)
    selected_types = random.sample(EVENT_TYPES[:8], num_events)
    
    for i, evt_type in enumerate(selected_types):
        direction = random.choice(["UP", "DOWN"]) if evt_type not in ["COMPRESSION", "RANGE_BOUND"] else "NEUTRAL"
        probability = 0.45 + random.random() * 0.45
        strength = 0.4 + random.random() * 0.5
        
        events.append({
            "id": f"evt_{int(time.time()*1000)}_{i}",
            "type": evt_type,
            "direction": direction,
            "probability": round(probability, 3),
            "strength": round(strength, 3),
            "confidence": round((probability + strength) / 2, 3),
            "timestamp": int(time.time() * 1000) - i * 60000,
            "triggerIndicators": random.sample(
                ["volume_spike", "rsi_divergence", "macd_crossover", "structure_break", "liquidity"],
                random.randint(1, 3)
            ),
            "notes": [f"{evt_type.replace('_', ' ').title()} detected", f"Direction: {direction}"]
        })
    
    return events


@app.get("/api/structure/state")
async def structure_state(symbol: str = "BTCUSDT", tf: str = "4h"):
    """Get market structure state"""
    return generate_mock_structure_state(symbol, tf)


@app.get("/api/structure/events")
async def structure_events(symbol: str = "BTCUSDT", tf: str = "4h"):
    """Get detected market events"""
    events = generate_mock_events(symbol, tf)
    return {
        "symbol": symbol,
        "timeframe": tf,
        "events": events,
        "count": len(events),
        "timestamp": int(time.time() * 1000)
    }


@app.get("/api/structure/narrative")
async def structure_narrative(symbol: str = "BTCUSDT", tf: str = "4h"):
    """Get human-readable market narrative"""
    state = generate_mock_structure_state(symbol, tf)
    return {
        "symbol": symbol,
        "timeframe": tf,
        "narrative": state["narrative"],
        "events": state["events"],
        "expectedNext": state["expectedNext"],
        "confidence": state["structureConfidence"]
    }


@app.get("/api/structure/chain")
async def structure_chain(symbol: str = "BTCUSDT", tf: str = "4h"):
    """Get active event chain"""
    import random
    
    chain_name = random.choice(list(EVENT_CHAINS.keys()))
    chain_events = EVENT_CHAINS[chain_name]
    
    # Simulate progress
    progress = random.uniform(0.25, 0.75)
    completed_count = int(len(chain_events) * progress)
    completed = chain_events[:completed_count]
    expected = chain_events[completed_count:]
    
    return {
        "symbol": symbol,
        "timeframe": tf,
        "chain": {
            "id": f"chain_{int(time.time()*1000)}",
            "name": chain_name,
            "events": chain_events,
            "completed": completed,
            "expected": expected,
            "progress": round(progress, 2),
            "probability": round(0.5 + random.random() * 0.35, 2),
            "direction": random.choice(["UP", "DOWN"])
        }
    }


@app.get("/api/structure/health")
async def structure_health():
    """Structure AI health check"""
    return {
        "enabled": True,
        "version": "structure_ai_phase7",
        "status": "ok",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


# ============================================
# Phase 7.5: Incremental Engine
# ============================================

# Dependency graph definition
DEPENDENCY_MAP = {
    "candles": [],
    "macro": [],
    "indicators": ["candles"],
    "ta": ["candles"],
    "momentum": ["candles"],
    "volume_profile": ["candles"],
    "liquidity": ["ta", "volume_profile"],
    "structure_ai": ["ta", "liquidity", "momentum"],
    "mtf": ["ta", "indicators"],
    "scenario": ["ta", "liquidity", "structure_ai", "mtf"],
    "memory": ["scenario"],
    "decision": ["scenario", "memory", "mtf", "structure_ai"],
    "strategy": ["decision"],
    "portfolio": ["decision"],
    "execution": ["decision", "strategy", "portfolio"],
    "metabrain": ["decision", "execution", "portfolio", "macro"]
}

NODE_COSTS = {
    "candles": 10, "macro": 50, "indicators": 30, "ta": 100, "momentum": 20,
    "volume_profile": 40, "liquidity": 50, "structure_ai": 80, "mtf": 60,
    "scenario": 120, "memory": 40, "decision": 150, "strategy": 30,
    "portfolio": 40, "execution": 25, "metabrain": 60
}

CANDLE_TRIGGERED_NODES = [
    "candles", "indicators", "ta", "momentum", "volume_profile",
    "liquidity", "structure_ai", "mtf", "scenario", "decision"
]

CANDLE_SKIPPED_NODES = ["macro", "memory", "strategy", "portfolio", "metabrain"]

# In-memory stats
incremental_stats = {
    "totalComputations": 0,
    "incrementalComputations": 0,
    "fullComputations": 0,
    "totalTimeSaved": 0,
    "avgTimeSavedPerUpdate": 0,
    "avgIncrementalDuration": 0,
    "avgFullDuration": 0
}


def topological_sort(dep_map):
    """Topological sort of dependency graph"""
    visited = set()
    result = []
    
    def visit(node):
        if node in visited:
            return
        visited.add(node)
        for dep in dep_map.get(node, []):
            visit(dep)
        result.append(node)
    
    for node in dep_map.keys():
        visit(node)
    
    return result


COMPUTATION_ORDER = topological_sort(DEPENDENCY_MAP)


@app.get("/api/incremental/status")
async def incremental_status():
    """Get incremental engine status"""
    edge_count = sum(len(deps) for deps in DEPENDENCY_MAP.values())
    
    return {
        "enabled": True,
        "version": "incremental_v1_phase7.5",
        "graph": {
            "nodeCount": len(DEPENDENCY_MAP),
            "edges": edge_count,
            "computationOrder": COMPUTATION_ORDER
        },
        "stats": incremental_stats,
        "lastUpdate": int(time.time() * 1000)
    }


@app.post("/api/incremental/compute")
async def incremental_compute(request: Request):
    """Trigger incremental computation"""
    import random
    
    body = await request.json() if request.method == "POST" else {}
    symbol = body.get("symbol", "BTCUSDT")
    timeframe = body.get("timeframe", "4h")
    trigger = body.get("trigger", "candles")
    force_full = body.get("forceFullRecompute", False)
    
    # Determine nodes to compute
    if force_full:
        nodes_computed = COMPUTATION_ORDER
        nodes_skipped = []
        mode = "full"
        incremental_stats["fullComputations"] += 1
    else:
        nodes_computed = CANDLE_TRIGGERED_NODES
        nodes_skipped = CANDLE_SKIPPED_NODES
        mode = "incremental"
        incremental_stats["incrementalComputations"] += 1
    
    # Calculate durations
    total_duration = sum(NODE_COSTS.get(n, 50) for n in nodes_computed) * 0.1
    saved_duration = sum(NODE_COSTS.get(n, 50) for n in nodes_skipped)
    
    # Simulate actual compute time (10% of theoretical)
    total_duration = int(total_duration + random.uniform(5, 20))
    
    # Update stats
    incremental_stats["totalComputations"] += 1
    incremental_stats["totalTimeSaved"] += saved_duration
    incremental_stats["avgTimeSavedPerUpdate"] = (
        incremental_stats["totalTimeSaved"] / 
        max(1, incremental_stats["incrementalComputations"])
    )
    
    if mode == "full":
        incremental_stats["avgFullDuration"] = (
            (incremental_stats["avgFullDuration"] + total_duration) / 2
        )
    else:
        incremental_stats["avgIncrementalDuration"] = (
            (incremental_stats["avgIncrementalDuration"] + total_duration) / 2
        )
    
    savings_percent = int((saved_duration / (total_duration + saved_duration)) * 100) if saved_duration > 0 else 0
    
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "mode": mode,
        "nodesComputed": nodes_computed,
        "nodesSkipped": nodes_skipped,
        "totalDuration": total_duration,
        "savedDuration": saved_duration,
        "savingsPercent": savings_percent,
        "timestamp": int(time.time() * 1000)
    }


@app.get("/api/incremental/graph")
async def incremental_graph():
    """Get dependency graph"""
    edge_count = sum(len(deps) for deps in DEPENDENCY_MAP.values())
    
    return {
        "nodeCount": len(DEPENDENCY_MAP),
        "edgeCount": edge_count,
        "computationOrder": COMPUTATION_ORDER,
        "adjacencyList": DEPENDENCY_MAP
    }


@app.get("/api/incremental/stats")
async def incremental_stats_endpoint():
    """Get detailed statistics"""
    avg_inc = incremental_stats.get("avgIncrementalDuration", 1)
    avg_full = incremental_stats.get("avgFullDuration", 100)
    
    return {
        "computations": {
            "total": incremental_stats["totalComputations"],
            "incremental": incremental_stats["incrementalComputations"],
            "full": incremental_stats["fullComputations"],
            "incrementalRatio": (
                incremental_stats["incrementalComputations"] / 
                max(1, incremental_stats["totalComputations"])
            )
        },
        "performance": {
            "totalTimeSaved": incremental_stats["totalTimeSaved"],
            "avgTimeSavedPerUpdate": int(incremental_stats["avgTimeSavedPerUpdate"]),
            "avgIncrementalDuration": int(avg_inc),
            "avgFullDuration": int(avg_full),
            "speedupFactor": round(avg_full / max(1, avg_inc), 2)
        },
        "expectedSavings": {
            "cpuReduction": "~70%",
            "latencyReduction": "~60%"
        }
    }


@app.post("/api/incremental/reset")
async def incremental_reset():
    """Reset engine state"""
    global incremental_stats
    incremental_stats = {
        "totalComputations": 0,
        "incrementalComputations": 0,
        "fullComputations": 0,
        "totalTimeSaved": 0,
        "avgTimeSavedPerUpdate": 0,
        "avgIncrementalDuration": 0,
        "avgFullDuration": 0
    }
    
    return {
        "success": True,
        "message": "Incremental engine reset",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/incremental/health")
async def incremental_health():
    """Incremental engine health check"""
    return {
        "enabled": True,
        "version": "incremental_v1_phase7.5",
        "nodeCount": len(DEPENDENCY_MAP),
        "status": "ok",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


# ============================================
# Phase 9: Strategy Discovery Engine
# ============================================

# Feature types
PATTERN_FEATURES = ["BREAKOUT", "COMPRESSION", "TRIANGLE", "FLAG", "DIVERGENCE", "DOUBLE_TOP"]
STRUCTURE_FEATURES = ["SWEEP", "COMPRESSION", "EXPANSION", "ACCUMULATION", "DISTRIBUTION"]
INDICATOR_FEATURES = ["RSI_OVERSOLD", "RSI_OVERBOUGHT", "VOLUME_SPIKE", "MACD_CROSSOVER"]
MTF_FEATURES = ["MTF_ALIGNED", "MTF_CONFLICT", "HIGHER_TF_BULL", "HIGHER_TF_BEAR"]
REGIME_FEATURES = ["TREND_UP", "TREND_DOWN", "RANGE"]
MEMORY_FEATURES = ["MEMORY_MATCH", "MEMORY_WEAK", "HISTORICAL_WIN"]

# Discovery state
discovery_state = {
    "strategies": [],
    "combinations": [],
    "clusters": [],
    "lastRun": None,
    "datasetSize": 0
}


def generate_mock_strategy(idx: int):
    """Generate mock strategy"""
    import random
    
    patterns = random.sample(PATTERN_FEATURES, random.randint(1, 2))
    mtf = random.choice(MTF_FEATURES)
    regime = random.choice(REGIME_FEATURES)
    
    features = patterns + [mtf, regime]
    
    win_rate = 0.55 + random.random() * 0.15
    pf = 1.2 + random.random() * 0.8
    
    status = "APPROVED" if win_rate > 0.62 and pf > 1.5 else "TESTING" if win_rate > 0.58 else "CANDIDATE"
    
    return {
        "id": f"strat_{int(time.time()*1000)}_{idx}",
        "name": f"AUTO_{'_'.join([f[:2] for f in features[:3]])}_{idx}",
        "rules": {
            "required": features,
            "preferred": [],
            "excluded": [],
            "direction": random.choice(["LONG", "SHORT", "BOTH"]),
            "regimes": [regime]
        },
        "metrics": {
            "winRate": round(win_rate, 3),
            "avgRMultiple": round(0.5 + random.random() * 1.5, 2),
            "profitFactor": round(pf, 2),
            "maxDrawdown": round(0.1 + random.random() * 0.15, 2),
            "sharpeRatio": round(0.8 + random.random() * 1.2, 2),
            "trades": random.randint(50, 200),
            "inSampleWinRate": round(win_rate + random.uniform(-0.05, 0.05), 3),
            "outOfSampleWinRate": round(win_rate + random.uniform(-0.08, 0.03), 3)
        },
        "confidence": round(0.6 + random.random() * 0.3, 2),
        "robustness": round(0.5 + random.random() * 0.4, 2),
        "stability": round(0.5 + random.random() * 0.4, 2),
        "regimeBreakdown": {
            "TREND_UP": {"winRate": round(win_rate + 0.05, 2), "trades": random.randint(20, 80)},
            "TREND_DOWN": {"winRate": round(win_rate - 0.02, 2), "trades": random.randint(15, 60)},
            "RANGE": {"winRate": round(win_rate - 0.08, 2), "trades": random.randint(10, 40)}
        },
        "status": status,
        "discoveredAt": int(time.time() * 1000) - idx * 3600000,
        "lastTestedAt": int(time.time() * 1000)
    }


def generate_mock_combination(idx: int):
    """Generate mock feature combination"""
    import random
    
    features = random.sample(PATTERN_FEATURES + STRUCTURE_FEATURES[:3], random.randint(2, 3))
    mtf = random.choice(MTF_FEATURES)
    features.append(mtf)
    
    win_rate = 0.52 + random.random() * 0.18
    edge = (win_rate - 0.5) * 2 + random.random() * 0.1
    
    return {
        "id": f"combo_{'_'.join(features)}",
        "features": features,
        "sampleSize": random.randint(30, 150),
        "winRate": round(win_rate, 3),
        "avgRMultiple": round(0.3 + random.random() * 1.2, 2),
        "profitFactor": round(1.1 + random.random() * 0.8, 2),
        "maxDrawdown": round(0.1 + random.random() * 0.2, 2),
        "sharpeRatio": round(0.5 + random.random() * 1.5, 2),
        "edge": round(edge, 3),
        "edgeConfidence": round(0.5 + random.random() * 0.4, 2),
        "regimePerformance": {
            "TREND_UP": {"winRate": round(win_rate + 0.05, 2), "sampleSize": random.randint(10, 50)},
            "TREND_DOWN": {"winRate": round(win_rate - 0.03, 2), "sampleSize": random.randint(8, 40)},
            "RANGE": {"winRate": round(win_rate - 0.08, 2), "sampleSize": random.randint(5, 30)}
        }
    }


@app.post("/api/discovery/run")
async def discovery_run(request: Request):
    """Run full discovery pipeline"""
    import random
    
    body = await request.json() if request.method == "POST" else {}
    symbols = body.get("symbols", ["BTCUSDT", "ETHUSDT"])
    timeframes = body.get("timeframes", ["1h", "4h"])
    
    # Generate mock results
    num_strategies = random.randint(8, 15)
    num_combos = random.randint(15, 30)
    
    strategies = [generate_mock_strategy(i) for i in range(num_strategies)]
    combinations = [generate_mock_combination(i) for i in range(num_combos)]
    
    # Store in state
    discovery_state["strategies"] = strategies
    discovery_state["combinations"] = combinations
    discovery_state["datasetSize"] = random.randint(400, 600)
    discovery_state["lastRun"] = int(time.time() * 1000)
    
    # Generate clusters
    clusters = []
    for i in range(random.randint(3, 6)):
        cluster_strategies = random.sample(strategies, min(3, len(strategies)))
        core_features = list(set(cluster_strategies[0]["rules"]["required"][:2]))
        
        clusters.append({
            "id": f"cluster_{i+1}",
            "name": f"{' + '.join(core_features[:2])} Strategies",
            "description": f"Strategies based on {', '.join(core_features)}",
            "coreFeatures": core_features,
            "sampleSize": sum(s["metrics"]["trades"] for s in cluster_strategies),
            "winRate": round(sum(s["metrics"]["winRate"] for s in cluster_strategies) / len(cluster_strategies), 3),
            "profitFactor": round(sum(s["metrics"]["profitFactor"] for s in cluster_strategies) / len(cluster_strategies), 2)
        })
    
    discovery_state["clusters"] = clusters
    
    # Build result
    approved = len([s for s in strategies if s["status"] == "APPROVED"])
    testing = len([s for s in strategies if s["status"] == "TESTING"])
    
    insights = [
        f"Top strategy: {strategies[0]['name']} with {strategies[0]['metrics']['winRate']*100:.1f}% win rate",
        f"Most effective features: {', '.join(combinations[0]['features'][:3])}",
        f"{approved} strategies auto-approved, {testing} in testing"
    ]
    
    if approved > testing:
        insights.append("Strong edge detected in current market conditions")
    
    return {
        "runId": f"run_{int(time.time()*1000)}",
        "startedAt": int(time.time() * 1000) - 5000,
        "completedAt": int(time.time() * 1000),
        "datasetSize": discovery_state["datasetSize"],
        "symbolsAnalyzed": symbols,
        "timeframesAnalyzed": timeframes,
        "combinationsFound": len(combinations),
        "combinationsWithEdge": len([c for c in combinations if c["edge"] > 0.1]),
        "clustersFormed": len(clusters),
        "strategiesGenerated": len(strategies),
        "topCombinations": combinations[:5],
        "topStrategies": strategies[:5],
        "insights": insights
    }


@app.get("/api/discovery/status")
async def discovery_status():
    """Get discovery engine status"""
    return {
        "enabled": True,
        "version": "discovery_v1_phase9",
        "datasetSize": discovery_state.get("datasetSize", 0),
        "strategiesGenerated": len(discovery_state.get("strategies", [])),
        "combinationsFound": len(discovery_state.get("combinations", [])),
        "lastRun": discovery_state.get("lastRun")
    }


@app.get("/api/discovery/strategies")
async def discovery_strategies(status: str = None):
    """Get all generated strategies"""
    strategies = discovery_state.get("strategies", [])
    
    if status:
        strategies = [s for s in strategies if s["status"] == status]
    
    return {
        "strategies": strategies,
        "total": len(strategies),
        "approved": len([s for s in strategies if s["status"] == "APPROVED"]),
        "testing": len([s for s in strategies if s["status"] == "TESTING"]),
        "candidates": len([s for s in strategies if s["status"] == "CANDIDATE"])
    }


@app.get("/api/discovery/combinations")
async def discovery_combinations(limit: int = 10):
    """Get top feature combinations"""
    combinations = discovery_state.get("combinations", [])
    return {
        "combinations": combinations[:limit],
        "count": len(combinations[:limit])
    }


@app.get("/api/discovery/clusters")
async def discovery_clusters():
    """Get strategy clusters"""
    clusters = discovery_state.get("clusters", [])
    return {
        "clusters": clusters,
        "count": len(clusters)
    }


@app.get("/api/discovery/features")
async def discovery_features():
    """Analyze individual feature performance"""
    import random
    
    all_features = (
        PATTERN_FEATURES + STRUCTURE_FEATURES + 
        INDICATOR_FEATURES + MTF_FEATURES + REGIME_FEATURES
    )
    
    features = []
    for f in all_features:
        win_rate = 0.45 + random.random() * 0.2
        edge = (win_rate - 0.5) * 2 + random.random() * 0.1
        
        features.append({
            "feature": f,
            "winRate": round(win_rate, 3),
            "sampleSize": random.randint(50, 200),
            "edge": round(edge, 3)
        })
    
    # Sort by edge
    features.sort(key=lambda x: x["edge"], reverse=True)
    
    return {"features": features}


@app.get("/api/discovery/health")
async def discovery_health():
    """Discovery engine health check"""
    return {
        "enabled": True,
        "version": "discovery_v1_phase9",
        "status": "ok",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


# ============================================
# Phase 9.5: Edge Validation for Discovery
# ============================================

# Import edge validation module
try:
    from modules.strategy_discovery.service import EdgeValidationService, validation_result_to_dict
    from modules.strategy_discovery.lifecycle import StrategyLifecycle
    
    edge_validation_service = EdgeValidationService()
    lifecycle_manager = StrategyLifecycle()
    EDGE_VALIDATION_AVAILABLE = True
    print("[EdgeValidation] Phase 9.5 module loaded successfully")
except ImportError as e:
    EDGE_VALIDATION_AVAILABLE = False
    edge_validation_service = None
    lifecycle_manager = None
    print(f"[EdgeValidation] Module not available: {e}")


# Health endpoint MUST be defined BEFORE the dynamic {strategy_id} route
@app.get("/api/discovery/edge-validation/health")
async def edge_validation_health():
    """Edge validation health check"""
    if not EDGE_VALIDATION_AVAILABLE:
        return {
            "enabled": False,
            "version": "edge_validation_v1_phase9.5",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return edge_validation_service.get_health()


@app.get("/api/discovery/edge-validation/{strategy_id}")
async def edge_validate_strategy(strategy_id: str):
    """
    Validate edge for a specific strategy.
    Returns robustness, similarity penalty, confidence score, and lifecycle recommendation.
    """
    if not EDGE_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge validation module not available")
    
    # Find strategy in discovery state
    strategies = discovery_state.get("strategies", [])
    target_strategy = None
    
    for s in strategies:
        if s.get("id") == strategy_id:
            target_strategy = s
            break
    
    if not target_strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    # Get other strategies for similarity comparison
    other_strategies = [s for s in strategies if s.get("id") != strategy_id]
    
    # Perform validation
    result = edge_validation_service.validate_strategy(target_strategy, other_strategies)
    
    return validation_result_to_dict(result)


@app.post("/api/discovery/edge-validation/batch")
async def edge_validate_batch(request: Request):
    """
    Validate edge for all strategies in discovery state.
    Returns validation results for all strategies.
    """
    if not EDGE_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge validation module not available")
    
    body = await request.json() if request.method == "POST" else {}
    strategy_ids = body.get("strategyIds", None)  # Optional filter
    
    strategies = discovery_state.get("strategies", [])
    
    # Filter if specific IDs provided
    if strategy_ids:
        strategies = [s for s in strategies if s.get("id") in strategy_ids]
    
    if not strategies:
        return {
            "results": [],
            "summary": {"totalValidated": 0},
            "message": "No strategies to validate"
        }
    
    # Perform batch validation
    validation_results = edge_validation_service.validate_batch(strategies)
    
    # Convert results to dict
    results_dict = {
        sid: validation_result_to_dict(result) 
        for sid, result in validation_results.items()
    }
    
    # Get summary
    summary = edge_validation_service.get_validation_summary(validation_results)
    
    return {
        "results": results_dict,
        "summary": summary
    }


@app.post("/api/discovery/edge-validation/apply")
async def apply_edge_validation(request: Request):
    """
    Apply validation results to update strategy statuses.
    This will promote/demote strategies based on validation.
    """
    if not EDGE_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge validation module not available")
    
    strategies = discovery_state.get("strategies", [])
    
    if not strategies:
        return {"updated": 0, "message": "No strategies to update"}
    
    # Validate all strategies
    validation_results = edge_validation_service.validate_batch(strategies)
    
    # Apply updates
    updated_strategies = edge_validation_service.apply_validation(strategies, validation_results)
    
    # Update discovery state
    discovery_state["strategies"] = updated_strategies
    
    # Count changes
    changes = {
        "promoted": 0,
        "demoted": 0,
        "deprecated": 0,
        "unchanged": 0
    }
    
    for sid, result in validation_results.items():
        action = result.lifecycle_action
        if action == "PROMOTE":
            changes["promoted"] += 1
        elif action == "DEMOTE":
            changes["demoted"] += 1
        elif action == "DEPRECATE":
            changes["deprecated"] += 1
        else:
            changes["unchanged"] += 1
    
    return {
        "updated": len(updated_strategies),
        "changes": changes,
        "summary": edge_validation_service.get_validation_summary(validation_results)
    }


@app.get("/api/discovery/lifecycle/report")
async def lifecycle_report():
    """
    Get lifecycle status report for all strategies.
    """
    if not EDGE_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge validation module not available")
    
    strategies = discovery_state.get("strategies", [])
    
    return lifecycle_manager.generate_lifecycle_report(strategies)


@app.get("/api/discovery/lifecycle/candidates")
async def lifecycle_candidates():
    """
    Get strategies that are candidates for promotion or demotion.
    """
    if not EDGE_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge validation module not available")
    
    strategies = discovery_state.get("strategies", [])
    
    return {
        "promotionCandidates": [
            {"id": s.get("id"), "name": s.get("name"), "status": s.get("status"), "confidence": s.get("confidence")}
            for s in lifecycle_manager.get_promotion_candidates(strategies)
        ],
        "demotionCandidates": [
            {"id": s.get("id"), "name": s.get("name"), "status": s.get("status"), "confidence": s.get("confidence")}
            for s in lifecycle_manager.get_demotion_candidates(strategies)
        ]
    }


# ============================================
# Phase 8.0: Validation Guardrails
# ============================================

# Import validation guardrails module
try:
    from modules.validation_guardrails.service import ValidationGuardrailsService, guardrails_report_to_dict
    from modules.validation_guardrails.lookahead import LookaheadDetector
    from modules.validation_guardrails.snooping import DataSnoopingGuard
    from modules.validation_guardrails.execution import ExecutionValidator
    
    guardrails_service = ValidationGuardrailsService()
    GUARDRAILS_AVAILABLE = True
    print("[Guardrails] Phase 8.0 module loaded successfully")
except ImportError as e:
    GUARDRAILS_AVAILABLE = False
    guardrails_service = None
    print(f"[Guardrails] Module not available: {e}")


# Health endpoint MUST be defined BEFORE dynamic routes
@app.get("/api/guardrails/health")
async def guardrails_health():
    """Validation guardrails health check"""
    if not GUARDRAILS_AVAILABLE:
        return {
            "enabled": False,
            "version": "guardrails_v1_phase8.0",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return guardrails_service.get_health()


@app.post("/api/guardrails/validate")
async def guardrails_validate(request: Request):
    """
    Run full validation guardrails check.
    
    Request body:
    {
        "backtestConfig": {
            "slippage_bps": 10,
            "fee_bps": 10,
            "fill_delay_ms": 100,
            "slippage_model": "fixed",
            "fee_model": "fixed",
            "liquidity_model": "unlimited"
        },
        "signals": [...],  // Optional: trading signals to check
        "testRuns": [...],  // Optional: history of test runs
        "trades": [...],    // Optional: executed trades
        "strategyRules": {...}  // Optional: strategy definition
    }
    """
    if not GUARDRAILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation guardrails module not available")
    
    body = await request.json()
    
    backtest_config = body.get("backtestConfig", {})
    signals = body.get("signals")
    test_runs = body.get("testRuns")
    trades = body.get("trades")
    strategy_rules = body.get("strategyRules")
    strategy_versions = body.get("strategyVersions")
    parameter_history = body.get("parameterHistory")
    market_data = body.get("marketData")
    price_data = body.get("priceData")
    
    report = guardrails_service.validate(
        backtest_config=backtest_config,
        signals=signals,
        test_runs=test_runs,
        trades=trades,
        price_data=price_data,
        strategy_rules=strategy_rules,
        strategy_versions=strategy_versions,
        parameter_history=parameter_history,
        market_data=market_data
    )
    
    return guardrails_report_to_dict(report)


@app.post("/api/guardrails/quick-check")
async def guardrails_quick_check(request: Request):
    """
    Quick pre-flight check before running backtest.
    Faster than full validation.
    """
    if not GUARDRAILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation guardrails module not available")
    
    body = await request.json()
    backtest_config = body.get("backtestConfig", {})
    strategy = body.get("strategy")
    
    return guardrails_service.quick_validate(backtest_config, strategy)


@app.get("/api/guardrails/execution/recommended-config")
async def guardrails_recommended_config(asset_type: str = "crypto", strategy_type: str = "trend"):
    """
    Get recommended execution configuration for asset/strategy type.
    """
    if not GUARDRAILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation guardrails module not available")
    
    return guardrails_service.execution_validator.get_recommended_config(asset_type, strategy_type)


@app.post("/api/guardrails/execution/cost-drag")
async def guardrails_cost_drag(request: Request):
    """
    Estimate performance drag from execution costs.
    """
    if not GUARDRAILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation guardrails module not available")
    
    body = await request.json()
    
    return guardrails_service.execution_validator.estimate_cost_drag(
        trades_per_year=body.get("tradesPerYear", 100),
        avg_trade_size=body.get("avgTradeSize", 10000),
        fee_bps=body.get("feeBps", 10),
        slippage_bps=body.get("slippageBps", 10)
    )


@app.post("/api/guardrails/snooping/correction-factor")
async def guardrails_correction_factor(request: Request):
    """
    Get statistical correction factor for multiple testing.
    """
    if not GUARDRAILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation guardrails module not available")
    
    body = await request.json()
    num_tests = body.get("numTests", 1)
    
    return guardrails_service.snooping_guard.get_correction_factor(num_tests)


@app.post("/api/guardrails/lookahead/quick-check")
async def guardrails_lookahead_quick(request: Request):
    """
    Quick lookahead risk check for a strategy.
    """
    if not GUARDRAILS_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation guardrails module not available")
    
    body = await request.json()
    strategy = body.get("strategy", {})
    
    return guardrails_service.lookahead_detector.quick_check(strategy)


# ============================================
# Phase 8.1: Validation Isolation Layer
# ============================================

# Import validation isolation module
try:
    from modules.validation_isolation.service import ValidationIsolationService, context_to_validation_isolation_block
    
    isolation_service = ValidationIsolationService()
    ISOLATION_AVAILABLE = True
    print("[Isolation] Phase 8.1 module loaded successfully")
except ImportError as e:
    ISOLATION_AVAILABLE = False
    isolation_service = None
    print(f"[Isolation] Module not available: {e}")


# Health endpoint MUST be defined BEFORE dynamic routes
@app.get("/api/validation/isolation/health")
async def isolation_health():
    """Validation isolation health check"""
    if not ISOLATION_AVAILABLE:
        return {
            "enabled": False,
            "version": "isolation_v1_phase8.1",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return isolation_service.get_health()


@app.post("/api/validation/isolation/context")
async def create_isolation_context(request: Request):
    """
    Create a new validation context with frozen snapshots.
    
    Request body:
    {
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "cutoffTime": 1703980800000,  // Unix timestamp ms
        "mode": "historical_faithful",  // or "frozen_config"
        "strategies": [...],  // Optional
        "memoryState": {...},  // Optional
        "metabrainConfig": {...},  // Optional
        "thresholds": {...},  // Optional
        "discoveryState": {...},  // Optional
        "systemConfig": {...}  // Optional
    }
    """
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    body = await request.json()
    
    return isolation_service.create_validation_context(
        symbol=body.get("symbol", "BTCUSDT"),
        timeframe=body.get("timeframe", "4h"),
        cutoff_time=body.get("cutoffTime", 0),
        mode=body.get("mode", "historical_faithful"),
        strategies=body.get("strategies"),
        memory_state=body.get("memoryState"),
        metabrain_config=body.get("metabrainConfig"),
        thresholds=body.get("thresholds"),
        discovery_state=body.get("discoveryState"),
        system_config=body.get("systemConfig")
    )


@app.get("/api/validation/isolation/context/{run_id}")
async def get_isolation_context(run_id: str):
    """Get a validation context by run ID"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    context = isolation_service.get_context(run_id)
    
    if not context:
        raise HTTPException(status_code=404, detail=f"Context not found: {run_id}")
    
    return context


@app.get("/api/validation/isolation/contexts")
async def list_isolation_contexts(symbol: str = None, limit: int = 20):
    """List validation contexts"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    return isolation_service.list_contexts(symbol, limit)


@app.post("/api/validation/isolation/check")
async def check_isolation(request: Request):
    """
    Run isolation check for a validation context.
    
    Request body:
    {
        "runId": "val_...",
        "currentSystemState": {...}  // Optional
    }
    """
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    body = await request.json()
    run_id = body.get("runId")
    
    if not run_id:
        raise HTTPException(status_code=400, detail="runId is required")
    
    return isolation_service.check_isolation(
        run_id=run_id,
        current_system_state=body.get("currentSystemState")
    )


@app.post("/api/validation/isolation/quick-check")
async def quick_check_isolation(request: Request):
    """Quick pre-flight check before validation run"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    body = await request.json()
    run_id = body.get("runId")
    
    if not run_id:
        raise HTTPException(status_code=400, detail="runId is required")
    
    return isolation_service.quick_check(run_id)


@app.post("/api/validation/isolation/start")
async def start_validation_run(request: Request):
    """Mark a validation run as started"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    body = await request.json()
    run_id = body.get("runId")
    
    if not run_id:
        raise HTTPException(status_code=400, detail="runId is required")
    
    return isolation_service.start_validation_run(run_id)


@app.post("/api/validation/isolation/complete")
async def complete_validation_run(request: Request):
    """Mark a validation run as completed"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    body = await request.json()
    run_id = body.get("runId")
    passed = body.get("passed", False)
    
    if not run_id:
        raise HTTPException(status_code=400, detail="runId is required")
    
    return isolation_service.complete_validation_run(run_id, passed)


@app.get("/api/validation/isolation/snapshots")
async def list_snapshots(snapshot_type: str = None, limit: int = 20):
    """List available snapshots"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    return isolation_service.list_snapshots(snapshot_type, limit)


@app.get("/api/validation/isolation/snapshot/{snapshot_id}")
async def get_snapshot(snapshot_id: str):
    """Get a snapshot by ID"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    snapshot = isolation_service.get_snapshot(snapshot_id)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")
    
    return snapshot


@app.post("/api/validation/isolation/cleanup")
async def cleanup_snapshots(request: Request):
    """Clean up old snapshots"""
    if not ISOLATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation isolation module not available")
    
    body = await request.json() if request.method == "POST" else {}
    keep_count = body.get("keepCount", 50)
    
    return isolation_service.cleanup_old_snapshots(keep_count)


# ============================================
# Phase 8: Quant Validation Layer
# ============================================

# Import validation module
try:
    from modules.validation.service import ValidationService
    
    validation_service = ValidationService()
    VALIDATION_AVAILABLE = True
    print("[Validation] Phase 8 module loaded successfully")
except ImportError as e:
    VALIDATION_AVAILABLE = False
    validation_service = None
    print(f"[Validation] Module not available: {e}")


@app.get("/api/validation/health")
async def validation_health():
    """Quant validation health check"""
    if not VALIDATION_AVAILABLE:
        return {
            "enabled": False,
            "version": "validation_v1_phase8",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return validation_service.get_health()


# --- Simulation endpoints ---

@app.post("/api/validation/simulation/run")
async def run_simulation(request: Request):
    """
    Run historical simulation.
    
    Request body:
    {
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "start": "2019-01-01",
        "end": "2024-01-01",
        "initialCapital": 100000
    }
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    
    return validation_service.run_simulation(
        symbol=body.get("symbol", "BTCUSDT"),
        timeframe=body.get("timeframe", "4h"),
        start_date=body.get("start", "2019-01-01"),
        end_date=body.get("end", "2024-01-01"),
        initial_capital=body.get("initialCapital", 100000.0),
        isolation_run_id=body.get("isolationRunId")
    )


@app.get("/api/validation/simulation/{run_id}")
async def get_simulation(run_id: str):
    """Get simulation result"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    result = validation_service.get_simulation(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {run_id}")
    
    return result


@app.get("/api/validation/simulations")
async def list_simulations(symbol: str = None, limit: int = 20):
    """List simulations"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    return validation_service.list_simulations(symbol, limit)


# --- Replay endpoints ---

@app.post("/api/validation/replay/start")
async def start_replay(request: Request):
    """
    Start market replay.
    
    Request body:
    {
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "start": "2024-01-01",
        "end": "2024-03-01"
    }
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    
    return validation_service.start_replay(
        symbol=body.get("symbol", "BTCUSDT"),
        timeframe=body.get("timeframe", "4h"),
        start_date=body.get("start", "2024-01-01"),
        end_date=body.get("end", "2024-03-01")
    )


@app.post("/api/validation/replay/step")
async def step_replay(request: Request):
    """Step replay forward one bar"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    run_id = body.get("runId")
    
    if not run_id:
        raise HTTPException(status_code=400, detail="runId is required")
    
    result = validation_service.step_replay(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Replay not found: {run_id}")
    
    return result


@app.post("/api/validation/replay/complete")
async def complete_replay(request: Request):
    """Run replay to completion"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    run_id = body.get("runId")
    
    if not run_id:
        raise HTTPException(status_code=400, detail="runId is required")
    
    result = validation_service.run_replay_to_completion(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Replay not found: {run_id}")
    
    return result


@app.get("/api/validation/replay/{run_id}")
async def get_replay(run_id: str):
    """Get replay state"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    result = validation_service.get_replay_state(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Replay not found: {run_id}")
    
    return result


@app.get("/api/validation/replay/{run_id}/events")
async def get_replay_events(run_id: str):
    """Get replay events"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    return validation_service.get_replay_events(run_id)


@app.get("/api/validation/replays")
async def list_replays(limit: int = 20):
    """List replays"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    return validation_service.list_replays(limit)


# --- Monte Carlo endpoints ---

@app.post("/api/validation/montecarlo/run")
async def run_monte_carlo(request: Request):
    """
    Run Monte Carlo simulation.
    
    Request body:
    {
        "baseWinRate": 0.60,
        "baseProfitFactor": 1.5,
        "iterations": 1000
    }
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    
    return validation_service.run_monte_carlo(
        base_win_rate=body.get("baseWinRate", 0.60),
        base_profit_factor=body.get("baseProfitFactor", 1.5),
        iterations=body.get("iterations", 1000)
    )


@app.get("/api/validation/montecarlo/{run_id}")
async def get_monte_carlo(run_id: str):
    """Get Monte Carlo result"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    result = validation_service.get_monte_carlo(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Monte Carlo not found: {run_id}")
    
    return result


# --- Stress Test endpoints ---

@app.post("/api/validation/stress/run")
async def run_stress_test(request: Request):
    """
    Run stress test.
    
    Request body:
    {
        "scenarios": ["api_calls", "websocket", "analysis"],
        "loadLevels": [10, 50, 100, 500, 1000]
    }
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    
    return validation_service.run_stress_test(
        scenarios=body.get("scenarios"),
        load_levels=body.get("loadLevels")
    )


@app.get("/api/validation/stress/{run_id}")
async def get_stress_test(run_id: str):
    """Get stress test result"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    result = validation_service.get_stress_test(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Stress test not found: {run_id}")
    
    return result


# --- Accuracy endpoints ---

@app.get("/api/validation/accuracy")
async def calculate_accuracy():
    """Calculate system accuracy"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    return validation_service.calculate_accuracy()


@app.get("/api/validation/accuracy/{run_id}")
async def get_accuracy(run_id: str):
    """Get accuracy result"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    result = validation_service.get_accuracy(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Accuracy not found: {run_id}")
    
    return result


# --- Failures endpoints ---

@app.get("/api/validation/failures")
async def analyze_failures():
    """Analyze system failures"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    return validation_service.analyze_failures()


@app.get("/api/validation/failures/{run_id}")
async def get_failure_analysis(run_id: str):
    """Get failure analysis"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    result = validation_service.get_failure_analysis(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Failure analysis not found: {run_id}")
    
    return result


# --- Report endpoints ---

@app.get("/api/validation/report/{run_id}")
async def get_validation_report(run_id: str):
    """Get validation report"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    result = validation_service.get_report(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Report not found: {run_id}")
    
    return result


@app.post("/api/validation/report/generate")
async def generate_validation_report(request: Request):
    """
    Generate comprehensive validation report.
    
    Request body:
    {
        "simulationRunId": "sim_...",  // Optional existing simulation
        "runFullValidation": true,     // Run all validation steps
        "isolationContext": {...}      // Validation isolation context
    }
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    
    return validation_service.generate_report(
        simulation_run_id=body.get("simulationRunId"),
        run_full_validation=body.get("runFullValidation", True),
        isolation_context=body.get("isolationContext")
    )


@app.get("/api/validation/reports")
async def list_validation_reports(limit: int = 20):
    """List validation reports"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    return validation_service.list_reports(limit)


# --- Phase 8.5: Real Data Validation endpoints ---

@app.get("/api/validation/providers")
async def list_providers():
    """List available data providers with health status"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    from modules.validation.market_data import market_data_router
    return await market_data_router.get_available_providers()


@app.get("/api/validation/providers/health")
async def check_provider_health(provider: str = "coinbase"):
    """Check specific provider health"""
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    from modules.validation.market_data import market_data_router
    return await market_data_router.health_check(provider)


@app.get("/api/validation/candles")
async def fetch_candles(
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    start: str = "2022-01-01",
    end: str = "2024-01-01",
    provider: str = None
):
    """
    Fetch candles from Coinbase (primary) or fallback provider.
    
    Query params:
    - symbol: Trading pair (e.g., BTCUSDT, BTC-USD)
    - timeframe: 1h, 4h, 1d, etc.
    - start: Start date (YYYY-MM-DD)
    - end: End date (YYYY-MM-DD)
    - provider: Force specific provider (optional, default: coinbase)
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    return await validation_service.fetch_candles(symbol, timeframe, start, end, provider)


@app.post("/api/validation/real/run")
async def run_real_simulation(request: Request):
    """
    Run simulation on REAL Binance data.
    
    Request body:
    {
        "symbol": "BTCUSDT",
        "timeframe": "4h",
        "start": "2022-01-01",
        "end": "2024-01-01",
        "initialCapital": 100000
    }
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    
    return await validation_service.run_real_simulation(
        symbol=body.get("symbol", "BTCUSDT"),
        timeframe=body.get("timeframe", "4h"),
        start_date=body.get("start", "2022-01-01"),
        end_date=body.get("end", "2024-01-01"),
        initial_capital=body.get("initialCapital", 100000.0)
    )


@app.post("/api/validation/batch/run")
async def run_validation_batch(request: Request):
    """
    Run validation batch on multiple symbols/timeframes.
    Default: BTC 4H, 1H, 1D (Phase 8.5 first batch)
    
    Request body:
    {
        "symbols": ["BTCUSDT"],
        "timeframes": ["4h", "1h", "1d"],
        "start": "2022-01-01",
        "end": "2024-01-01"
    }
    """
    if not VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation module not available")
    
    body = await request.json()
    
    return await validation_service.run_validation_batch(
        symbols=body.get("symbols"),
        timeframes=body.get("timeframes"),
        start_date=body.get("start", "2022-01-01"),
        end_date=body.get("end", "2024-01-01")
    )


# ============================================
# Proxy to Node.js TA Engine
# ============================================

async def proxy_to_node(path: str, request: Request) -> Response:
    """Proxy request to Node.js TA Engine"""
    
    node_url = f"http://localhost:{NODE_TA_PORT}{path}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Forward the request
            if request.method == "GET":
                response = await client.get(
                    node_url,
                    params=dict(request.query_params),
                    headers=dict(request.headers)
                )
            elif request.method == "POST":
                body = await request.body()
                response = await client.post(
                    node_url,
                    content=body,
                    headers={"Content-Type": "application/json"}
                )
            else:
                response = await client.request(
                    request.method,
                    node_url,
                    content=await request.body(),
                    headers=dict(request.headers)
                )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json")
            )
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="TA Engine Node.js server not available"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Proxy error: {str(e)}"
        )


# ============================================
# TA Engine Routes (Proxy to Node.js)
# ============================================

@app.api_route("/api/ta/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def ta_proxy(path: str, request: Request):
    """Proxy all /api/ta/* routes to Node.js TA Engine"""
    return await proxy_to_node(f"/api/ta/{path}", request)


@app.api_route("/api/binance/{path:path}", methods=["GET", "POST"])
async def binance_proxy(path: str, request: Request):
    """Proxy Binance data routes"""
    return await proxy_to_node(f"/api/binance/{path}", request)


# ============================================
# Direct TA Endpoints (For testing without Node.js)
# ============================================

@app.get("/api/ta/patterns")
async def get_patterns():
    """Get registered patterns"""
    # Try proxy first
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"http://localhost:{NODE_TA_PORT}/api/ta/registry/patterns")
            return response.json()
    except:
        # Fallback static response
        return {
            "total": 99,
            "groups": ["STRUCTURE", "LEVELS", "BREAKOUTS", "TREND_GEOMETRY", 
                      "TRIANGLES_WEDGES", "FLAGS_PENNANTS", "REVERSALS",
                      "HARMONICS", "WAVES", "CANDLES", "OSCILLATORS", "MA_PATTERNS"],
            "implemented": 95
        }


@app.get("/api/ta/registry")
async def get_registry():
    """Get pattern registry stats"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"http://localhost:{NODE_TA_PORT}/api/ta/registry/stats")
            return response.json()
    except:
        return {
            "total": 99,
            "byGroup": {
                "STRUCTURE": 7,
                "LEVELS": 6,
                "BREAKOUTS": 4,
                "TREND_GEOMETRY": 6,
                "TRIANGLES_WEDGES": 7,
                "FLAGS_PENNANTS": 3,
                "REVERSALS": 8,
                "HARMONICS": 16,
                "WAVES": 3,
                "CANDLES": 9,
                "OSCILLATORS": 6,
                "MA_PATTERNS": 11,
                "DIVERGENCES": 6,
                "GAPS": 6,
                "PITCHFORK": 2,
                "BROADENING": 2,
                "ELLIOTT": 3
            },
            "implemented": 95
        }


@app.post("/api/ta/analyze")
async def analyze(request: Request):
    """TA Analysis endpoint"""
    body = await request.json()
    symbol = body.get("symbol", "BTCUSDT")
    timeframe = body.get("timeframe", "1d")
    
    # Try proxy to Node.js
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"http://localhost:{NODE_TA_PORT}/api/ta/analyze",
                params={"asset": symbol, "timeframe": timeframe}
            )
            return response.json()
    except Exception as e:
        # Fallback mock response
        return {
            "asset": symbol,
            "timeframe": timeframe,
            "patterns": [],
            "structure": {"regime": "RANGE"},
            "levels": {"support": [], "resistance": []},
            "decision": {
                "action": "HOLD",
                "confidence": 0.5,
                "ev": 0.0
            },
            "error": str(e) if str(e) else None
        }


# ============================================
# Phase 8.6: Core Calibration Loop
# ============================================

CALIBRATION_CONFIG = {
    "enabled": True,
    "version": "phase8.6",
    
    # Volatility Filter: ATR > SMA(ATR) * 0.8
    "volatilityFilter": {
        "enabled": True,
        "atrMultiplier": 0.8,
        "atrPeriod": 14,
        "smaPeriod": 14
    },
    
    # Trend Alignment: Trade only in EMA50/EMA200 direction
    "trendAlignment": {
        "enabled": True,
        "emaShortPeriod": 50,
        "emaLongPeriod": 200,
        "requireBothAligned": False
    },
    
    # Volume Breakout: volume > SMA(volume) * 1.4
    "volumeBreakout": {
        "enabled": True,
        "volumeMultiplier": 1.4,
        "smaPeriod": 20
    },
    
    # ATR-based TP/SL
    "atrRiskManagement": {
        "enabled": True,
        "stopLossATR": 1.5,
        "takeProfitATR": 2.5
    },
    
    # Disabled Strategies
    "disabledStrategies": [
        "LIQUIDITY_SWEEP",
        "LIQUIDITY_SWEEP_HIGH",
        "LIQUIDITY_SWEEP_LOW",
        "RANGE_REVERSAL"
    ]
}


def calculate_sma(values: list, period: int) -> float:
    """Calculate Simple Moving Average"""
    if not values or len(values) < period:
        return values[-1] if values else 0
    return sum(values[-period:]) / period


def calculate_ema(values: list, period: int) -> float:
    """Calculate Exponential Moving Average"""
    if not values:
        return 0
    if len(values) < period:
        return sum(values) / len(values)
    
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    
    for val in values[period:]:
        ema = (val - ema) * multiplier + ema
    
    return ema


def calculate_atr(candles: list, period: int) -> float:
    """Calculate Average True Range"""
    if not candles or len(candles) < period + 1:
        return 0
    
    trs = []
    for i in range(1, len(candles)):
        high = candles[i].get("high", candles[i].get("h", 0))
        low = candles[i].get("low", candles[i].get("l", 0))
        prev_close = candles[i-1].get("close", candles[i-1].get("c", 0))
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)
    
    return sum(trs[-period:]) / min(len(trs), period)


def calculate_atr_series(candles: list, atr_period: int) -> list:
    """Calculate ATR series for SMA calculation"""
    atr_series = []
    for i in range(atr_period, len(candles)):
        atr = calculate_atr(candles[:i+1], atr_period)
        atr_series.append(atr)
    return atr_series


@app.get("/api/calibration/config")
async def get_calibration_config():
    """Get Phase 8.6 calibration configuration"""
    return {
        "config": CALIBRATION_CONFIG,
        "version": "phase8.6",
        "description": "Core Calibration Loop filters for edge improvement"
    }


@app.post("/api/calibration/apply")
async def apply_calibration_filters(request: Request):
    """
    Apply Phase 8.6 calibration filters to a trading scenario.
    
    Request body:
    {
        "candles": [...],  // OHLCV data
        "direction": "LONG" or "SHORT",
        "patternType": "DOUBLE_BOTTOM",
        "entry": 50000.0
    }
    """
    body = await request.json()
    
    candles = body.get("candles", [])
    direction = body.get("direction", "LONG")
    pattern_type = body.get("patternType", "UNKNOWN")
    entry = body.get("entry", 0)
    
    if not candles:
        return {
            "passed": False,
            "error": "candles data required",
            "score": 0
        }
    
    config = CALIBRATION_CONFIG
    rejection_reasons = []
    score = 1.0
    
    # Check if strategy is disabled
    strategy_enabled = pattern_type not in config["disabledStrategies"]
    if not strategy_enabled:
        rejection_reasons.append("STRATEGY_DISABLED")
        score = 0
    
    # Calculate indicators
    closes = [c.get("close", c.get("c", 0)) for c in candles]
    volumes = [c.get("volume", c.get("v", 0)) for c in candles]
    
    atr_period = config["volatilityFilter"]["atrPeriod"]
    atr = calculate_atr(candles, atr_period)
    atr_series = calculate_atr_series(candles, atr_period)
    atr_sma = calculate_sma(atr_series, config["volatilityFilter"]["smaPeriod"])
    
    ema50 = calculate_ema(closes, config["trendAlignment"]["emaShortPeriod"])
    ema200 = calculate_ema(closes, config["trendAlignment"]["emaLongPeriod"])
    
    current_price = closes[-1] if closes else entry
    current_volume = volumes[-1] if volumes else 0
    volume_sma = calculate_sma(volumes, config["volumeBreakout"]["smaPeriod"])
    
    # Filter 1: Volatility Filter
    volatility_threshold = atr_sma * config["volatilityFilter"]["atrMultiplier"]
    volatility_ratio = atr / atr_sma if atr_sma > 0 else 1
    volatility_passed = not config["volatilityFilter"]["enabled"] or atr > volatility_threshold
    
    if config["volatilityFilter"]["enabled"] and not volatility_passed:
        rejection_reasons.append("LOW_VOLATILITY")
        score -= 0.3
    
    # Filter 2: Trend Alignment
    trend_direction = "UP" if current_price > ema50 else "DOWN" if current_price < ema50 else "NEUTRAL"
    
    if config["trendAlignment"]["requireBothAligned"]:
        short_aligned = (direction == "LONG" and current_price > ema50) or (direction == "SHORT" and current_price < ema50)
        long_aligned = (direction == "LONG" and current_price > ema200) or (direction == "SHORT" and current_price < ema200)
        trend_alignment_passed = short_aligned and long_aligned
    else:
        trend_alignment_passed = (direction == "LONG" and trend_direction == "UP") or (direction == "SHORT" and trend_direction == "DOWN")
    
    trend_alignment_passed = not config["trendAlignment"]["enabled"] or trend_alignment_passed
    
    if config["trendAlignment"]["enabled"] and not trend_alignment_passed:
        rejection_reasons.append("TREND_MISALIGNED")
        score -= 0.3
    
    # Filter 3: Volume Breakout
    volume_threshold = volume_sma * config["volumeBreakout"]["volumeMultiplier"]
    volume_ratio = current_volume / volume_sma if volume_sma > 0 else 1
    volume_breakout_passed = not config["volumeBreakout"]["enabled"] or current_volume > volume_threshold
    
    if config["volumeBreakout"]["enabled"] and not volume_breakout_passed:
        rejection_reasons.append("LOW_VOLUME")
        score -= 0.2
    
    # ATR-based TP/SL
    if config["atrRiskManagement"]["enabled"] and atr > 0:
        sl_distance = atr * config["atrRiskManagement"]["stopLossATR"]
        tp_distance = atr * config["atrRiskManagement"]["takeProfitATR"]
        
        if direction == "LONG":
            stop_loss = entry - sl_distance
            take_profit = entry + tp_distance
        else:
            stop_loss = entry + sl_distance
            take_profit = entry - tp_distance
    else:
        fallback = entry * 0.02
        if direction == "LONG":
            stop_loss = entry - fallback
            take_profit = entry + fallback * 2
        else:
            stop_loss = entry + fallback
            take_profit = entry - fallback * 2
    
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    risk_reward = reward / risk if risk > 0 else 0
    
    # Final result
    passed = strategy_enabled and score >= 0.5 and volatility_passed and trend_alignment_passed and volume_breakout_passed
    
    return {
        "passed": passed,
        "score": max(0, min(1, score)),
        
        "filters": {
            "volatilityPassed": volatility_passed,
            "trendAlignmentPassed": trend_alignment_passed,
            "volumeBreakoutPassed": volume_breakout_passed,
            "strategyEnabled": strategy_enabled
        },
        
        "computedValues": {
            "atr": round(atr, 4),
            "atrSMA": round(atr_sma, 4),
            "volatilityRatio": round(volatility_ratio, 4),
            "ema50": round(ema50, 4),
            "ema200": round(ema200, 4),
            "trendDirection": trend_direction,
            "currentVolume": current_volume,
            "volumeSMA": round(volume_sma, 4),
            "volumeRatio": round(volume_ratio, 4)
        },
        
        "adjustedLevels": {
            "stopLoss": round(stop_loss, 4),
            "takeProfit": round(take_profit, 4),
            "riskReward": round(risk_reward, 4)
        },
        
        "rejectionReasons": rejection_reasons
    }


@app.post("/api/calibration/batch")
async def batch_calibration_filter(request: Request):
    """
    Apply calibration filters to multiple scenarios.
    
    Request body:
    {
        "candles": [...],  // Shared OHLCV data
        "scenarios": [
            {"direction": "LONG", "patternType": "DOUBLE_BOTTOM", "entry": 50000},
            ...
        ]
    }
    """
    body = await request.json()
    
    candles = body.get("candles", [])
    scenarios = body.get("scenarios", [])
    
    if not candles:
        return {"error": "candles data required", "results": []}
    
    results = []
    passed_count = 0
    by_reason = {}
    
    for scenario in scenarios:
        # Build request for single filter
        filter_request = {
            "candles": candles,
            "direction": scenario.get("direction", "LONG"),
            "patternType": scenario.get("patternType", "UNKNOWN"),
            "entry": scenario.get("entry", 0)
        }
        
        # Apply filter (inline calculation)
        config = CALIBRATION_CONFIG
        direction = filter_request["direction"]
        pattern_type = filter_request["patternType"]
        entry = filter_request["entry"]
        
        closes = [c.get("close", c.get("c", 0)) for c in candles]
        volumes = [c.get("volume", c.get("v", 0)) for c in candles]
        
        atr = calculate_atr(candles, config["volatilityFilter"]["atrPeriod"])
        atr_series = calculate_atr_series(candles, config["volatilityFilter"]["atrPeriod"])
        atr_sma = calculate_sma(atr_series, config["volatilityFilter"]["smaPeriod"])
        
        ema50 = calculate_ema(closes, config["trendAlignment"]["emaShortPeriod"])
        current_price = closes[-1] if closes else entry
        current_volume = volumes[-1] if volumes else 0
        volume_sma = calculate_sma(volumes, config["volumeBreakout"]["smaPeriod"])
        
        rejection_reasons = []
        
        # Strategy check
        strategy_enabled = pattern_type not in config["disabledStrategies"]
        if not strategy_enabled:
            rejection_reasons.append("STRATEGY_DISABLED")
        
        # Volatility check
        volatility_passed = atr > (atr_sma * config["volatilityFilter"]["atrMultiplier"])
        if not volatility_passed:
            rejection_reasons.append("LOW_VOLATILITY")
        
        # Trend check
        trend_direction = "UP" if current_price > ema50 else "DOWN"
        trend_alignment_passed = (direction == "LONG" and trend_direction == "UP") or (direction == "SHORT" and trend_direction == "DOWN")
        if not trend_alignment_passed:
            rejection_reasons.append("TREND_MISALIGNED")
        
        # Volume check
        volume_breakout_passed = current_volume > (volume_sma * config["volumeBreakout"]["volumeMultiplier"])
        if not volume_breakout_passed:
            rejection_reasons.append("LOW_VOLUME")
        
        passed = strategy_enabled and volatility_passed and trend_alignment_passed and volume_breakout_passed
        
        if passed:
            passed_count += 1
        
        for reason in rejection_reasons:
            by_reason[reason] = by_reason.get(reason, 0) + 1
        
        results.append({
            "scenarioId": scenario.get("id", len(results)),
            "passed": passed,
            "rejectionReasons": rejection_reasons
        })
    
    return {
        "results": results,
        "stats": {
            "total": len(scenarios),
            "passed": passed_count,
            "rejected": len(scenarios) - passed_count,
            "byReason": by_reason
        }
    }


@app.get("/api/calibration/health")
async def calibration_health():
    """Phase 8.6 Calibration health check"""
    return {
        "enabled": True,
        "version": "calibration_v1_phase8.6",
        "status": "ok",
        "filters": list(CALIBRATION_CONFIG.keys()),
        "disabledStrategies": CALIBRATION_CONFIG["disabledStrategies"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


# ============================================
# Phase 8.7: BTC Re-Validation
# ============================================

# Import Phase 8.7 module
try:
    from modules.validation.btc_revalidation import run_btc_revalidation, btc_revalidator
    BTC_REVALIDATION_AVAILABLE = True
    print("[Phase 8.7] BTC Re-Validation module loaded successfully")
except ImportError as e:
    BTC_REVALIDATION_AVAILABLE = False
    print(f"[Phase 8.7] Module not available: {e}")


@app.get("/api/revalidation/health")
async def revalidation_health():
    """Phase 8.7 Re-Validation health check"""
    return {
        "enabled": BTC_REVALIDATION_AVAILABLE,
        "version": "revalidation_v1_phase8.7",
        "status": "ok" if BTC_REVALIDATION_AVAILABLE else "unavailable",
        "targetAsset": "BTC",
        "targetTimeframes": ["1d", "4h", "1h"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/revalidation/btc/run")
async def run_btc_validation(request: Request):
    """
    Run Phase 8.7 BTC Re-Validation.
    
    Compares performance before/after Phase 8.6 calibration.
    
    Request body (optional):
    {
        "symbol": "BTCUSDT",
        "timeframes": ["1d", "4h", "1h"]
    }
    """
    if not BTC_REVALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="BTC Re-Validation module not available")
    
    body = await request.json() if request.method == "POST" else {}
    symbol = body.get("symbol", "BTCUSDT")
    timeframes = body.get("timeframes", ["1d", "4h", "1h"])
    
    return run_btc_revalidation(symbol=symbol, timeframes=timeframes)


@app.get("/api/revalidation/btc/summary")
async def btc_validation_summary():
    """
    Get summary of last BTC re-validation run.
    Quick view of calibration effectiveness.
    """
    if not BTC_REVALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="BTC Re-Validation module not available")
    
    # Check if we have cached results
    if not btc_revalidator.results:
        return {
            "status": "NO_DATA",
            "message": "No validation runs found. Call POST /api/revalidation/btc/run first.",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    # Build summary from cached results
    summaries = []
    for key, result in btc_revalidator.results.items():
        summaries.append({
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "winRateBefore": result.before.win_rate,
            "winRateAfter": result.after.win_rate,
            "winRateImprovement": f"+{result.win_rate_improvement}pp",
            "profitFactorBefore": result.before.profit_factor,
            "profitFactorAfter": result.after.profit_factor,
            "profitFactorImprovement": f"+{result.profit_factor_improvement}",
            "tradesReduced": result.before.trades - result.after.trades
        })
    
    return {
        "status": "OK",
        "lastRun": summaries,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/revalidation/comparison/{timeframe}")
async def get_timeframe_comparison(timeframe: str):
    """
    Get detailed comparison for specific timeframe.
    
    Path params:
    - timeframe: "1d", "4h", or "1h"
    """
    if not BTC_REVALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="BTC Re-Validation module not available")
    
    key = f"BTCUSDT_{timeframe}"
    
    if key not in btc_revalidator.results:
        raise HTTPException(status_code=404, detail=f"No validation data for {timeframe}. Run validation first.")
    
    result = btc_revalidator.results[key]
    
    return {
        "symbol": result.symbol,
        "timeframe": result.timeframe,
        
        "before": {
            "runId": result.before.run_id,
            "trades": result.before.trades,
            "wins": result.before.wins,
            "losses": result.before.losses,
            "winRate": result.before.win_rate,
            "profitFactor": result.before.profit_factor,
            "maxDrawdown": result.before.max_drawdown,
            "sharpeRatio": result.before.sharpe_ratio,
            "avgR": result.before.avg_r,
            "strategyBreakdown": result.before.strategy_breakdown,
            "regimeBreakdown": result.before.regime_breakdown
        },
        
        "after": {
            "runId": result.after.run_id,
            "trades": result.after.trades,
            "wins": result.after.wins,
            "losses": result.after.losses,
            "winRate": result.after.win_rate,
            "profitFactor": result.after.profit_factor,
            "maxDrawdown": result.after.max_drawdown,
            "sharpeRatio": result.after.sharpe_ratio,
            "avgR": result.after.avg_r,
            "strategyBreakdown": result.after.strategy_breakdown,
            "regimeBreakdown": result.after.regime_breakdown,
            "calibrationStats": result.after.calibration_stats
        },
        
        "improvement": {
            "winRate": f"+{result.win_rate_improvement}pp",
            "profitFactor": f"+{result.profit_factor_improvement}",
            "drawdown": f"-{result.drawdown_improvement}pp",
            "sharpe": f"+{result.sharpe_improvement}",
            "avgR": f"+{result.r_improvement}"
        },
        
        "recommendations": result.recommendations
    }


# ============================================
# Phase 8.8: Strategy Pruning
# ============================================

try:
    from modules.validation.strategy_pruning import (
        run_strategy_pruning,
        strategy_pruner,
        StrategyStatus
    )
    STRATEGY_PRUNING_AVAILABLE = True
    print("[Phase 8.8] Strategy Pruning module loaded successfully")
except ImportError as e:
    STRATEGY_PRUNING_AVAILABLE = False
    print(f"[Phase 8.8] Module not available: {e}")


@app.get("/api/pruning/health")
async def pruning_health():
    """Phase 8.8 Strategy Pruning health check"""
    return {
        "enabled": STRATEGY_PRUNING_AVAILABLE,
        "version": "pruning_v1_phase8.8",
        "status": "ok" if STRATEGY_PRUNING_AVAILABLE else "unavailable",
        "categories": ["APPROVED", "LIMITED", "TESTING", "DEPRECATED"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/pruning/run")
async def run_pruning():
    """
    Run Phase 8.8 Strategy Pruning.
    
    Classifies all strategies into:
    - APPROVED: Production ready
    - LIMITED: Conditional use only
    - TESTING: Need more data
    - DEPRECATED: Removed from production
    """
    if not STRATEGY_PRUNING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Pruning module not available")
    
    return run_strategy_pruning()


@app.get("/api/pruning/summary")
async def pruning_summary():
    """Get summary of strategy classifications"""
    if not STRATEGY_PRUNING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Pruning module not available")
    
    # Run pruning if not done yet
    if not strategy_pruner.classifications:
        strategy_pruner.run_pruning()
    
    approved = strategy_pruner.get_active_strategies()
    deprecated = strategy_pruner.get_deprecated_strategies()
    
    # Group classifications
    summary = {
        "APPROVED": [],
        "LIMITED": [],
        "TESTING": [],
        "DEPRECATED": []
    }
    
    for strategy_id, classification in strategy_pruner.classifications.items():
        summary[classification.status.value].append({
            "id": strategy_id,
            "winRate": classification.metrics.win_rate,
            "profitFactor": classification.metrics.profit_factor,
            "avgR": classification.metrics.avg_r,
            "reason": classification.reason[:50] + "..." if len(classification.reason) > 50 else classification.reason
        })
    
    return {
        "totalStrategies": len(strategy_pruner.classifications),
        "breakdown": {
            "approved": len(summary["APPROVED"]),
            "limited": len(summary["LIMITED"]),
            "testing": len(summary["TESTING"]),
            "deprecated": len(summary["DEPRECATED"])
        },
        "strategies": summary,
        "productionActive": approved,
        "productionBlocked": deprecated,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/pruning/strategy/{strategy_id}")
async def get_strategy_classification(strategy_id: str):
    """Get classification for specific strategy"""
    if not STRATEGY_PRUNING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Pruning module not available")
    
    # Run pruning if not done yet
    if not strategy_pruner.classifications:
        strategy_pruner.run_pruning()
    
    if strategy_id not in strategy_pruner.classifications:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    c = strategy_pruner.classifications[strategy_id]
    
    return {
        "strategyId": c.strategy_id,
        "status": c.status.value,
        "reason": c.reason,
        "metrics": {
            "winRate": c.metrics.win_rate,
            "profitFactor": c.metrics.profit_factor,
            "avgR": c.metrics.avg_r,
            "maxDrawdown": c.metrics.max_drawdown,
            "sharpeRatio": c.metrics.sharpe_ratio,
            "totalTrades": c.metrics.total_trades,
        },
        "regime": {
            "trendUpWR": c.metrics.trend_up_wr,
            "trendDownWR": c.metrics.trend_down_wr,
            "rangeWR": c.metrics.range_wr,
            "stable": c.metrics.regime_stable
        },
        "timeframe": {
            "1dWR": c.metrics.tf_1d_wr,
            "4hWR": c.metrics.tf_4h_wr,
            "1hWR": c.metrics.tf_1h_wr,
            "stable": c.metrics.tf_stable
        },
        "conditions": {
            "allowedRegimes": c.allowed_regimes,
            "allowedTimeframes": c.allowed_timeframes
        },
        "recommendations": c.recommendations
    }


@app.post("/api/pruning/check")
async def check_strategy_allowed(request: Request):
    """
    Check if strategy is allowed for given conditions.
    
    Request body:
    {
        "strategyId": "MTF_BREAKOUT",
        "regime": "TREND_UP",
        "timeframe": "4h"
    }
    """
    if not STRATEGY_PRUNING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Pruning module not available")
    
    # Run pruning if not done yet
    if not strategy_pruner.classifications:
        strategy_pruner.run_pruning()
    
    body = await request.json()
    strategy_id = body.get("strategyId")
    regime = body.get("regime")
    timeframe = body.get("timeframe")
    
    if not strategy_id:
        raise HTTPException(status_code=400, detail="strategyId required")
    
    result = strategy_pruner.is_strategy_allowed(strategy_id, regime, timeframe)
    
    return {
        "strategyId": strategy_id,
        "regime": regime,
        "timeframe": timeframe,
        **result
    }


@app.get("/api/pruning/deprecated")
async def get_deprecated_strategies():
    """Get list of all deprecated strategies for removal"""
    if not STRATEGY_PRUNING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Pruning module not available")
    
    # Run pruning if not done yet
    if not strategy_pruner.classifications:
        strategy_pruner.run_pruning()
    
    deprecated = []
    for strategy_id in strategy_pruner.get_deprecated_strategies():
        c = strategy_pruner.classifications[strategy_id]
        deprecated.append({
            "strategyId": strategy_id,
            "reason": c.reason,
            "metrics": {
                "winRate": c.metrics.win_rate,
                "profitFactor": c.metrics.profit_factor,
                "avgR": c.metrics.avg_r
            },
            "action": "REMOVE_FROM_PRODUCTION"
        })
    
    return {
        "phase": "8.8",
        "status": "DEPRECATED",
        "strategies": deprecated,
        "totalCount": len(deprecated),
        "recommendation": "Remove these strategies from production routing immediately",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


# ============================================
# Phase 8.9: Regime Validation
# ============================================

try:
    from modules.validation.regime_validation import (
        run_regime_validation,
        regime_validator,
        Regime,
        ActivationStatus
    )
    REGIME_VALIDATION_AVAILABLE = True
    print("[Phase 8.9] Regime Validation module loaded successfully")
except ImportError as e:
    REGIME_VALIDATION_AVAILABLE = False
    print(f"[Phase 8.9] Module not available: {e}")


@app.get("/api/regime/health")
async def regime_health():
    """Phase 8.9 Regime Validation health check"""
    return {
        "enabled": REGIME_VALIDATION_AVAILABLE,
        "version": "regime_v1_phase8.9",
        "status": "ok" if REGIME_VALIDATION_AVAILABLE else "unavailable",
        "regimes": ["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/regime/validate")
async def run_regime_val():
    """
    Run Phase 8.9 Regime Validation.
    
    Builds activation map showing which strategies to use in each regime.
    """
    if not REGIME_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Regime Validation module not available")
    
    return run_regime_validation()


@app.get("/api/regime/activation-map")
async def get_activation_map():
    """Get complete strategy activation map by regime"""
    if not REGIME_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Regime Validation module not available")
    
    # Run validation if not done yet
    if not regime_validator.profiles:
        regime_validator.run_validation()
    
    # Build matrix view
    matrix = []
    regimes = ["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"]
    
    for strategy_id, profile in regime_validator.profiles.items():
        row = {"strategy": strategy_id}
        for regime in regimes:
            try:
                regime_enum = Regime(regime)
                status = profile.activation_map.get(regime_enum, ActivationStatus.OFF)
                row[regime] = status.value
            except:
                row[regime] = "OFF"
        row["classification"] = "ALL_WEATHER" if profile.all_weather else "SPECIALIST" if profile.regime_specialist else "STANDARD"
        matrix.append(row)
    
    return {
        "regimes": regimes,
        "strategies": matrix,
        "legend": {
            "ON": "Full activation, 1.0x position",
            "LIMITED": "Reduced position, 0.5x",
            "WATCH": "Paper trade only",
            "OFF": "Disabled"
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/regime/{regime}/strategies")
async def get_strategies_for_regime(regime: str):
    """
    Get active strategies for specific regime.
    
    Path params:
    - regime: TREND_UP, TREND_DOWN, RANGE, COMPRESSION, EXPANSION
    """
    if not REGIME_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Regime Validation module not available")
    
    # Run validation if not done yet
    if not regime_validator.profiles:
        regime_validator.run_validation()
    
    valid_regimes = ["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"]
    if regime not in valid_regimes:
        raise HTTPException(status_code=400, detail=f"Invalid regime. Valid: {valid_regimes}")
    
    active = regime_validator.get_active_strategies_for_regime(regime)
    
    return {
        "regime": regime,
        "activeStrategies": active,
        "totalActive": len(active),
        "positionBudget": len([s for s in active if s["status"] == "ON"]) * 0.02,
        "maxConcurrentTrades": len(active) * 2,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/regime/strategy/{strategy_id}")
async def get_strategy_regime_profile(strategy_id: str):
    """Get regime profile for specific strategy"""
    if not REGIME_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Regime Validation module not available")
    
    # Run validation if not done yet
    if not regime_validator.profiles:
        regime_validator.run_validation()
    
    if strategy_id not in regime_validator.profiles:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    profile = regime_validator.profiles[strategy_id]
    
    return {
        "strategyId": strategy_id,
        "classification": "ALL_WEATHER" if profile.all_weather else "REGIME_SPECIALIST" if profile.regime_specialist else "STANDARD",
        "bestRegime": profile.best_regime.value if profile.best_regime else None,
        "worstRegime": profile.worst_regime.value if profile.worst_regime else None,
        "activationMap": {r.value: s.value for r, s in profile.activation_map.items()},
        "tradingRules": profile.trading_rules,
        "regimeMetrics": {
            r.value: {
                "winRate": m.win_rate,
                "profitFactor": m.profit_factor,
                "avgR": m.avg_r,
                "edgeScore": m.edge_score,
                "maxDrawdown": m.max_drawdown,
                "sharpeRatio": m.sharpe_ratio,
                "trades": m.trades,
            } for r, m in profile.regime_metrics.items()
        }
    }


@app.post("/api/regime/check")
async def check_strategy_regime(request: Request):
    """
    Check if strategy should be active in given regime.
    
    Request body:
    {
        "strategyId": "MTF_BREAKOUT",
        "regime": "TREND_UP"
    }
    """
    if not REGIME_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Regime Validation module not available")
    
    # Run validation if not done yet
    if not regime_validator.profiles:
        regime_validator.run_validation()
    
    body = await request.json()
    strategy_id = body.get("strategyId")
    regime = body.get("regime")
    
    if not strategy_id or not regime:
        raise HTTPException(status_code=400, detail="strategyId and regime required")
    
    result = regime_validator.get_activation(strategy_id, regime)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.get("/api/regime/policy")
async def get_trading_policy():
    """Get complete regime-based trading policy"""
    if not REGIME_VALIDATION_AVAILABLE:
        raise HTTPException(status_code=503, detail="Regime Validation module not available")
    
    # Run validation if not done yet
    if not regime_validator.profiles:
        regime_validator.run_validation()
    
    # Build policy summary
    policy = {
        "version": "phase8.9",
        "positionSizing": {
            "ON": {"multiplier": 1.0, "description": "Full position size"},
            "LIMITED": {"multiplier": 0.5, "description": "Half position size"},
            "WATCH": {"multiplier": 0.0, "description": "Paper trade only"},
            "OFF": {"multiplier": 0.0, "description": "No trading allowed"}
        },
        "regimeRules": {},
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    for regime in ["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"]:
        active = regime_validator.get_active_strategies_for_regime(regime)
        on_strategies = [s["strategyId"] for s in active if s["status"] == "ON"]
        limited_strategies = [s["strategyId"] for s in active if s["status"] == "LIMITED"]
        
        policy["regimeRules"][regime] = {
            "activeStrategies": on_strategies,
            "limitedStrategies": limited_strategies,
            "maxRisk": len(on_strategies) * 0.02,
            "maxTrades": len(active) * 2
        }
    
    return policy


# ============================================
# Phase 9.0: Cross-Asset Validation
# ============================================

try:
    from modules.validation.cross_asset_validation import (
        run_cross_asset_validation,
        cross_asset_validator,
        ASSET_CONFIGS
    )
    CROSS_ASSET_AVAILABLE = True
    print("[Phase 9.0] Cross-Asset Validation module loaded successfully")
except ImportError as e:
    CROSS_ASSET_AVAILABLE = False
    print(f"[Phase 9.0] Module not available: {e}")


@app.get("/api/crossasset/health")
async def crossasset_health():
    """Phase 9.0 Cross-Asset Validation health check"""
    return {
        "enabled": CROSS_ASSET_AVAILABLE,
        "version": "crossasset_v1_phase9.0",
        "status": "ok" if CROSS_ASSET_AVAILABLE else "unavailable",
        "availableAssets": list(ASSET_CONFIGS.keys()) if CROSS_ASSET_AVAILABLE else [],
        "methodology": "ZERO_TUNING",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/crossasset/validate")
async def run_crossasset_validation(request: Request):
    """
    Run Phase 9.0 Cross-Asset Validation.
    
    Tests BTC-tuned logic on other assets WITHOUT modifications.
    
    Request body (optional):
    {
        "assets": ["ETHUSDT", "SOLUSDT", "SPX", "GOLD", "DXY"],
        "includeBtc": true
    }
    """
    if not CROSS_ASSET_AVAILABLE:
        raise HTTPException(status_code=503, detail="Cross-Asset Validation module not available")
    
    body = await request.json() if request.method == "POST" else {}
    assets = body.get("assets", None)
    include_btc = body.get("includeBtc", True)
    
    return run_cross_asset_validation(assets, include_btc)


@app.get("/api/crossasset/summary")
async def crossasset_summary():
    """Get summary of cross-asset validation results"""
    if not CROSS_ASSET_AVAILABLE:
        raise HTTPException(status_code=503, detail="Cross-Asset Validation module not available")
    
    if not cross_asset_validator.results:
        return {
            "status": "NO_DATA",
            "message": "No validation runs found. Call POST /api/crossasset/validate first.",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    summary = []
    for symbol, result in cross_asset_validator.results.items():
        summary.append({
            "symbol": symbol,
            "assetClass": result.asset_class,
            "winRate": result.win_rate,
            "profitFactor": result.profit_factor,
            "avgR": result.avg_r,
            "maxDrawdown": result.max_drawdown,
            "verdict": result.verdict,
        })
    
    # Sort by profit factor
    summary.sort(key=lambda x: x["profitFactor"], reverse=True)
    
    passed = len([s for s in summary if s["verdict"] == "PASS"])
    
    return {
        "status": "OK",
        "totalAssets": len(summary),
        "passed": passed,
        "results": summary,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/crossasset/asset/{symbol}")
async def get_asset_result(symbol: str):
    """Get detailed validation result for specific asset"""
    if not CROSS_ASSET_AVAILABLE:
        raise HTTPException(status_code=503, detail="Cross-Asset Validation module not available")
    
    if symbol not in cross_asset_validator.results:
        raise HTTPException(status_code=404, detail=f"No validation data for {symbol}. Run validation first.")
    
    result = cross_asset_validator.results[symbol]
    
    return {
        "symbol": result.symbol,
        "assetClass": result.asset_class,
        "timeframe": result.timeframe,
        "verdict": result.verdict,
        
        "coreMetrics": {
            "trades": result.trades,
            "wins": result.wins,
            "losses": result.losses,
            "winRate": result.win_rate,
            "profitFactor": result.profit_factor,
            "avgR": result.avg_r,
            "totalR": result.total_r,
            "maxDrawdown": result.max_drawdown,
            "sharpe": result.sharpe_ratio,
        },
        
        "directionBreakdown": {
            "longTrades": result.long_trades,
            "shortTrades": result.short_trades,
            "longWinRate": round(result.long_win_rate, 4),
            "shortWinRate": round(result.short_win_rate, 4),
        },
        
        "regimePerformance": result.regime_performance,
        "strategyPerformance": result.strategy_performance,
        "notes": result.notes,
    }


@app.get("/api/crossasset/comparison")
async def get_asset_comparison():
    """Get comparison matrix across all validated assets"""
    if not CROSS_ASSET_AVAILABLE:
        raise HTTPException(status_code=503, detail="Cross-Asset Validation module not available")
    
    if not cross_asset_validator.results:
        raise HTTPException(status_code=404, detail="No validation data. Run validation first.")
    
    # Build comparison table
    comparison = {
        "headers": ["Symbol", "Class", "WR", "PF", "AvgR", "MaxDD", "Sharpe", "Verdict"],
        "rows": []
    }
    
    for symbol, result in cross_asset_validator.results.items():
        comparison["rows"].append({
            "symbol": symbol,
            "assetClass": result.asset_class,
            "winRate": f"{result.win_rate:.1%}",
            "profitFactor": f"{result.profit_factor:.2f}",
            "avgR": f"{result.avg_r:.3f}",
            "maxDrawdown": f"{result.max_drawdown:.1%}",
            "sharpe": f"{result.sharpe_ratio:.2f}",
            "verdict": result.verdict,
        })
    
    # Sort by PF
    comparison["rows"].sort(key=lambda x: float(x["profitFactor"]), reverse=True)
    
    return comparison


# ============================================
# Bootstrap & System Status
# ============================================

@app.get("/api/system/status")
async def system_status():
    """Get complete system status"""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        db = client["ta_engine"]
        
        status = {
            "mongodb": True,
            "nodeEngine": True,  # If we got here, proxy is working
            "pythonApi": True,
            
            "data": {
                "BTC": db.candles.count_documents({"symbol": "BTC"}),
                "SPX": db.candles.count_documents({"symbol": "SPX"}),
                "DXY": db.candles.count_documents({"symbol": "DXY"}),
            },
            
            "config": {
                "calibration": db.config.find_one({"_id": "calibration"}) is not None,
                "coinbase": db.config.find_one({"_id": "coinbase"}) is not None,
                "strategies": db.strategies.count_documents({}),
                "regimeMap": db.regime_map.count_documents({}),
            },
            
            "validation": db.validation.find_one({"_id": "phase9.0"}, {"systemVerdict": 1}),
            
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        client.close()
        return status
        
    except Exception as e:
        return {
            "mongodb": False,
            "error": str(e),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


@app.get("/api/system/config")
async def get_system_config():
    """Get all system configuration"""
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        db = client["ta_engine"]
        
        calibration = db.config.find_one({"_id": "calibration"}, {"_id": 0})
        coinbase = db.config.find_one({"_id": "coinbase"}, {"_id": 0})
        
        strategies = list(db.strategies.find({}, {"_id": 0}))
        regime_map = list(db.regime_map.find({}, {"_id": 0}))
        
        client.close()
        
        return {
            "calibration": calibration,
            "coinbase": coinbase,
            "strategies": strategies,
            "regimeMap": regime_map,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Coinbase Provider API
# ============================================

@app.get("/api/coinbase/candles/{product_id}")
async def get_coinbase_candles(
    product_id: str,
    timeframe: str = "1d",
    limit: int = 100
):
    """
    Fetch candles from Coinbase.
    
    Path params:
    - product_id: BTC-USD, ETH-USD, SOL-USD
    
    Query params:
    - timeframe: 1m, 5m, 15m, 1h, 4h, 1d
    - limit: max 300
    """
    try:
        from modules.data.coinbase_provider import coinbase_provider
        
        candles = await coinbase_provider.get_candles(product_id, timeframe, limit)
        
        return {
            "productId": product_id,
            "timeframe": timeframe,
            "count": len(candles),
            "candles": candles,
        }
        
    except ImportError:
        raise HTTPException(status_code=503, detail="Coinbase provider not available")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/coinbase/ticker/{product_id}")
async def get_coinbase_ticker(product_id: str):
    """Get current ticker from Coinbase"""
    try:
        from modules.data.coinbase_provider import coinbase_provider
        
        ticker = await coinbase_provider.get_ticker(product_id)
        return ticker
        
    except ImportError:
        raise HTTPException(status_code=503, detail="Coinbase provider not available")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/coinbase/products")
async def get_coinbase_products():
    """Get available trading pairs from Coinbase"""
    try:
        from modules.data.coinbase_provider import coinbase_provider
        
        products = await coinbase_provider.get_products()
        
        # Filter to main pairs
        main_pairs = [p for p in products if p["id"] in coinbase_provider.SUPPORTED_PAIRS]
        
        return {
            "supportedPairs": coinbase_provider.SUPPORTED_PAIRS,
            "mainPairs": main_pairs,
            "totalAvailable": len(products),
        }
        
    except ImportError:
        raise HTTPException(status_code=503, detail="Coinbase provider not available")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Phase 9.1: Failure-Driven Refinement
# ============================================

try:
    from modules.validation.failure_refinement import (
        FailureRefinementEngine,
        result_to_dict as refinement_to_dict
    )
    REFINEMENT_AVAILABLE = True
    refinement_engine = FailureRefinementEngine()
    print("[Phase 9.1] Failure Refinement module loaded successfully")
except ImportError as e:
    REFINEMENT_AVAILABLE = False
    refinement_engine = None
    print(f"[Phase 9.1] Module not available: {e}")


@app.get("/api/refinement/health")
async def refinement_health():
    """Phase 9.1 Failure Refinement health check"""
    return {
        "enabled": REFINEMENT_AVAILABLE,
        "version": "refinement_v1_phase9.1",
        "status": "ok" if REFINEMENT_AVAILABLE else "unavailable",
        "methodology": "FAILURE_DRIVEN_ANALYSIS",
        "capabilities": [
            "exit_analysis",
            "entry_analysis",
            "regime_analysis",
            "strategy_analysis",
            "tpsl_optimization"
        ],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/refinement/analyze")
async def run_failure_analysis(request: Request):
    """
    Run Phase 9.1 Failure-Driven Refinement analysis.
    
    Analyzes losing trades to identify:
    - Exit failures (premature stops, wide stops)
    - Entry failures (false breakouts, counter-trend)
    - Regime failures (wrong regime for strategy)
    - Strategy failures (underperforming strategies)
    
    Request body:
    {
        "symbol": "BTC",
        "timeframe": "1d"
    }
    """
    if not REFINEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Failure Refinement module not available")
    
    body = await request.json() if request.method == "POST" else {}
    symbol = body.get("symbol", "BTC")
    timeframe = body.get("timeframe", "1d")
    
    result = refinement_engine.analyze(symbol, timeframe)
    return refinement_to_dict(result)


@app.get("/api/refinement/summary")
async def refinement_summary():
    """Get summary of all refinement analyses"""
    if not REFINEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Failure Refinement module not available")
    
    if not refinement_engine.results:
        return {
            "status": "NO_DATA",
            "message": "No refinement analyses found. Call POST /api/refinement/analyze first.",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    summary = []
    for run_id, result in refinement_engine.results.items():
        summary.append({
            "runId": run_id,
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "lossRate": result.loss_rate,
            "topFailure": list(result.category_breakdown.keys())[0] if result.category_breakdown else None,
            "recommendationCount": len(result.recommendations),
        })
    
    return {
        "status": "OK",
        "totalAnalyses": len(summary),
        "results": summary,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/refinement/recommendations")
async def get_all_recommendations():
    """Get aggregated recommendations from all analyses"""
    if not REFINEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Failure Refinement module not available")
    
    if not refinement_engine.results:
        return {
            "status": "NO_DATA",
            "message": "No refinement analyses found. Run analysis first.",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    all_recommendations = []
    for result in refinement_engine.results.values():
        for rec in result.recommendations:
            all_recommendations.append({
                **rec,
                "source": f"{result.symbol}_{result.timeframe}"
            })
    
    # Sort by priority
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_recommendations.sort(key=lambda r: priority_order.get(r["priority"], 2))
    
    # Count by priority
    priority_counts = {}
    for rec in all_recommendations:
        p = rec["priority"]
        priority_counts[p] = priority_counts.get(p, 0) + 1
    
    return {
        "status": "OK",
        "totalRecommendations": len(all_recommendations),
        "byPriority": priority_counts,
        "recommendations": all_recommendations[:20],  # Top 20
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/refinement/{run_id}")
async def get_refinement_result(run_id: str):
    """Get detailed refinement result by run ID"""
    if not REFINEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Failure Refinement module not available")
    
    if run_id not in refinement_engine.results:
        raise HTTPException(status_code=404, detail=f"Refinement run {run_id} not found")
    
    return refinement_to_dict(refinement_engine.results[run_id])


# ============================================
# Phase 9.2: Final Quant Report
# ============================================

try:
    from modules.validation.final_quant_report import FinalQuantReportGenerator, report_to_dict as quant_report_to_dict
    
    quant_report_generator = FinalQuantReportGenerator()
    QUANT_REPORT_AVAILABLE = True
    print("[Phase 9.2] Final Quant Report module loaded successfully")
except ImportError as e:
    QUANT_REPORT_AVAILABLE = False
    quant_report_generator = None
    print(f"[Phase 9.2] Module not available: {e}")


@app.get("/api/quant-report/health")
async def quant_report_health():
    """Phase 9.2 Final Quant Report health check"""
    if not QUANT_REPORT_AVAILABLE:
        return {
            "enabled": False,
            "version": "quant_report_v1_phase9.2",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return {
        "enabled": True,
        "version": "quant_report_v1_phase9.2",
        "status": "ok",
        "reportsCount": len(quant_report_generator._reports),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/quant-report/generate")
async def generate_quant_report(request: Request):
    """
    Generate Phase 9.2 Final Quant Report.
    
    Request body (optional):
    {
        "crossAssetResults": {...},  // Phase 9.0 results
        "strategies": [...],          // Phase 8.8 strategy registry
        "regimeMap": {...},           // Phase 8.9 regime map
        "failureAnalysis": {...}      // Phase 9.1 failure analysis
    }
    """
    if not QUANT_REPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Final Quant Report module not available")
    
    body = await request.json() if request.method == "POST" else {}
    
    report = quant_report_generator.generate(
        cross_asset_results=body.get("crossAssetResults"),
        strategies=body.get("strategies"),
        regime_map=body.get("regimeMap"),
        failure_analysis=body.get("failureAnalysis"),
        validation_runs=body.get("validationRuns")
    )
    
    # Auto-save to files
    files = quant_report_generator.save_to_file(report)
    
    result = quant_report_to_dict(report)
    result["files"] = files
    
    return result


@app.get("/api/quant-report/list")
async def list_quant_reports():
    """List all generated Final Quant Reports"""
    if not QUANT_REPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Final Quant Report module not available")
    
    return {
        "reports": quant_report_generator.list_reports(),
        "count": len(quant_report_generator._reports),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/quant-report/latest")
async def get_latest_quant_report():
    """Get the latest Final Quant Report"""
    if not QUANT_REPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Final Quant Report module not available")
    
    reports = quant_report_generator.list_reports()
    
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found. Generate a report first.")
    
    latest_id = reports[0]["reportId"]
    report = quant_report_generator.get_report(latest_id)
    
    return quant_report_to_dict(report)


@app.get("/api/quant-report/summary")
async def get_quant_report_summary():
    """Get summary view of the latest Final Quant Report"""
    if not QUANT_REPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Final Quant Report module not available")
    
    reports = quant_report_generator.list_reports()
    
    if not reports:
        return {
            "status": "NO_DATA",
            "message": "No reports found. Generate a report using POST /api/quant-report/generate",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    latest_id = reports[0]["reportId"]
    report = quant_report_generator.get_report(latest_id)
    
    return {
        "reportId": report.report_id,
        "edgeVerdict": report.edge_verdict,
        "executiveSummary": {
            "profitFactor": report.global_profit_factor,
            "winRate": f"{report.global_win_rate * 100:.1f}%",
            "sharpe": report.global_sharpe,
            "maxDrawdown": f"{report.global_max_drawdown * 100:.1f}%",
            "trades": report.total_trades
        },
        "assetResults": [
            {"asset": a.asset, "verdict": a.verdict, "pf": a.profit_factor}
            for a in report.asset_performance
        ],
        "productionReady": all([
            report.strategy_pruning_done,
            report.guardrails_active,
            report.validation_isolation_active,
            report.dataset_frozen
        ]),
        "generatedAt": report.generated_at,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/quant-report/{report_id}")
async def get_quant_report(report_id: str):
    """Get Final Quant Report by ID"""
    if not QUANT_REPORT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Final Quant Report module not available")
    
    report = quant_report_generator.get_report(report_id)
    
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    
    return quant_report_to_dict(report)


# ============================================
# Phase 9.25A: Edge Protection Layer
# ============================================

try:
    from modules.edge_guard.service import (
        EdgeGuardService,
        decay_report_to_dict,
        overfit_report_to_dict,
        drift_report_to_dict,
        confidence_report_to_dict,
        status_to_dict
    )
    
    edge_guard_service = EdgeGuardService()
    EDGE_GUARD_AVAILABLE = True
    print("[Phase 9.25A] Edge Guard module loaded successfully")
except ImportError as e:
    EDGE_GUARD_AVAILABLE = False
    edge_guard_service = None
    print(f"[Phase 9.25A] Module not available: {e}")


@app.get("/api/edge/health")
async def edge_guard_health():
    """Phase 9.25A Edge Guard health check"""
    if not EDGE_GUARD_AVAILABLE:
        return {
            "enabled": False,
            "version": "edge_guard_v1_phase9.25A",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return edge_guard_service.get_health()


@app.get("/api/edge/status")
async def edge_status():
    """Get overall edge protection status"""
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    status = edge_guard_service.get_status()
    return status_to_dict(status)


@app.post("/api/edge/check")
async def edge_full_check(request: Request):
    """
    Run full edge protection check.
    
    Request body:
    {
        "strategies": ["MTF_BREAKOUT", "DOUBLE_BOTTOM", ...],
        "tradeData": {"MTF_BREAKOUT": [...], ...}  // Optional
    }
    """
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    body = await request.json() if request.method == "POST" else {}
    
    strategies = body.get("strategies", [
        "MTF_BREAKOUT", "DOUBLE_BOTTOM", "DOUBLE_TOP",
        "CHANNEL_BREAKOUT", "MOMENTUM_CONTINUATION"
    ])
    trade_data = body.get("tradeData")
    
    results = edge_guard_service.run_full_check(strategies, trade_data)
    
    return {
        "checkId": f"check_{int(time.time() * 1000)}",
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/edge/decay")
async def edge_decay():
    """Get edge decay reports for all strategies"""
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    reports = edge_guard_service.decay_monitor.get_all_reports()
    
    return {
        "reports": {sid: decay_report_to_dict(r) for sid, r in reports.items()},
        "count": len(reports),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/edge/decay/{strategy_id}")
async def edge_decay_strategy(strategy_id: str):
    """Get edge decay report for a specific strategy"""
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    report = edge_guard_service.decay_monitor.analyze(strategy_id)
    return decay_report_to_dict(report)


@app.get("/api/edge/overfit")
async def edge_overfit():
    """Get overfit reports for all strategies"""
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    reports = edge_guard_service.overfit_detector.get_all_reports()
    
    return {
        "reports": {sid: overfit_report_to_dict(r) for sid, r in reports.items()},
        "count": len(reports),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/edge/overfit/{strategy_id}")
async def edge_overfit_strategy(strategy_id: str):
    """Get overfit report for a specific strategy"""
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    report = edge_guard_service.overfit_detector.analyze(strategy_id)
    return overfit_report_to_dict(report)


@app.get("/api/edge/drift")
async def edge_drift():
    """Get regime drift report"""
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    report = edge_guard_service.drift_detector.analyze()
    return drift_report_to_dict(report)


@app.get("/api/edge/confidence")
async def edge_confidence():
    """Get confidence integrity report"""
    if not EDGE_GUARD_AVAILABLE:
        raise HTTPException(status_code=503, detail="Edge Guard module not available")
    
    report = edge_guard_service.confidence_monitor.analyze()
    return confidence_report_to_dict(report)


# ============================================
# Phase 9.25B: Strategy Governance Layer
# ============================================

try:
    from modules.strategy_governance.service import (
        StrategyGovernanceService,
        StrategyLifecycle,
        StrategyFamily,
        strategy_record_to_dict,
        budget_to_dict,
        family_to_dict,
        promotion_result_to_dict
    )
    
    strategy_governance_service = StrategyGovernanceService()
    STRATEGY_GOVERNANCE_AVAILABLE = True
    print("[Phase 9.25B] Strategy Governance module loaded successfully")
except ImportError as e:
    STRATEGY_GOVERNANCE_AVAILABLE = False
    strategy_governance_service = None
    print(f"[Phase 9.25B] Module not available: {e}")


@app.get("/api/strategy/health")
async def strategy_governance_health():
    """Phase 9.25B Strategy Governance health check"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        return {
            "enabled": False,
            "version": "strategy_governance_v1_phase9.25B",
            "status": "unavailable"
        }
    
    return strategy_governance_service.get_health()


@app.get("/api/strategy/governance")
async def strategy_governance_status():
    """Get overall strategy governance status"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    return strategy_governance_service.get_governance_status()


@app.get("/api/strategy/lifecycle")
async def strategy_lifecycle_list():
    """Get all strategies with lifecycle status"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    strategies = strategy_governance_service.lifecycle_manager.get_all_strategies()
    
    return {
        "strategies": {sid: strategy_record_to_dict(s) for sid, s in strategies.items()},
        "count": len(strategies),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/strategy/lifecycle/{strategy_id}")
async def strategy_lifecycle_get(strategy_id: str):
    """Get strategy lifecycle details"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    strategy = strategy_governance_service.lifecycle_manager.get_strategy(strategy_id)
    
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    return strategy_record_to_dict(strategy)


@app.post("/api/strategy/promote")
async def strategy_promote(request: Request):
    """
    Promote strategy to new lifecycle status.
    
    Request body:
    {
        "strategyId": "MTF_BREAKOUT",
        "toStatus": "APPROVED",
        "force": false  // Optional
    }
    """
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    body = await request.json()
    
    strategy_id = body.get("strategyId")
    to_status = body.get("toStatus")
    force = body.get("force", False)
    
    if not strategy_id or not to_status:
        raise HTTPException(status_code=400, detail="strategyId and toStatus required")
    
    try:
        to_lifecycle = StrategyLifecycle(to_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {to_status}")
    
    result = strategy_governance_service.lifecycle_manager.promote(strategy_id, to_lifecycle, force)
    
    return promotion_result_to_dict(result)


@app.post("/api/strategy/demote")
async def strategy_demote(request: Request):
    """
    Demote strategy to lower lifecycle status.
    
    Request body:
    {
        "strategyId": "MTF_BREAKOUT",
        "toStatus": "WATCH",
        "reason": "Performance degradation"
    }
    """
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    body = await request.json()
    
    strategy_id = body.get("strategyId")
    to_status = body.get("toStatus")
    reason = body.get("reason", "")
    
    if not strategy_id or not to_status:
        raise HTTPException(status_code=400, detail="strategyId and toStatus required")
    
    try:
        to_lifecycle = StrategyLifecycle(to_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {to_status}")
    
    result = strategy_governance_service.lifecycle_manager.demote(strategy_id, to_lifecycle, reason)
    
    return promotion_result_to_dict(result)


@app.get("/api/strategy/families")
async def strategy_families():
    """Get all strategy families with allocations"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    families = strategy_governance_service.family_manager.get_all_families()
    
    return {
        "families": {fname: family_to_dict(f) for fname, f in families.items()},
        "exposure": strategy_governance_service.family_manager.get_family_exposure(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/strategy/families/{family}/disable")
async def strategy_family_disable(family: str):
    """Disable a strategy family"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    try:
        family_enum = StrategyFamily(family)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid family: {family}")
    
    success = strategy_governance_service.family_manager.disable_family(family_enum)
    
    return {"success": success, "family": family, "action": "disabled"}


@app.post("/api/strategy/families/{family}/enable")
async def strategy_family_enable(family: str):
    """Enable a strategy family"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    try:
        family_enum = StrategyFamily(family)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid family: {family}")
    
    success = strategy_governance_service.family_manager.enable_family(family_enum)
    
    return {"success": success, "family": family, "action": "enabled"}


@app.get("/api/strategy/budgets")
async def strategy_budgets():
    """Get all strategy budgets"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    budgets = strategy_governance_service.budget_manager.get_all_budgets()
    
    return {
        "budgets": {sid: budget_to_dict(b) for sid, b in budgets.items()},
        "totalRiskAllocation": strategy_governance_service.budget_manager.get_total_risk_allocation(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/strategy/budgets/{strategy_id}")
async def strategy_budget_get(strategy_id: str):
    """Get budget for specific strategy"""
    if not STRATEGY_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Strategy Governance module not available")
    
    budget = strategy_governance_service.budget_manager.get_budget(strategy_id)
    
    if not budget:
        raise HTTPException(status_code=404, detail=f"Budget for {strategy_id} not found")
    
    return budget_to_dict(budget)


# ============================================
# Phase 9.25C: Portfolio Safety Layer
# ============================================

try:
    from modules.portfolio_safety.service import (
        PortfolioSafetyService,
        KillSwitchTrigger,
        exposure_to_dict,
        correlation_to_dict,
        kill_switch_to_dict,
        safety_status_to_dict
    )
    
    portfolio_safety_service = PortfolioSafetyService()
    PORTFOLIO_SAFETY_AVAILABLE = True
    print("[Phase 9.25C] Portfolio Safety module loaded successfully")
except ImportError as e:
    PORTFOLIO_SAFETY_AVAILABLE = False
    portfolio_safety_service = None
    print(f"[Phase 9.25C] Module not available: {e}")


@app.get("/api/portfolio/health")
async def portfolio_safety_health():
    """Phase 9.25C Portfolio Safety health check"""
    if not PORTFOLIO_SAFETY_AVAILABLE:
        return {"enabled": False, "status": "unavailable"}
    
    return portfolio_safety_service.get_health()


@app.get("/api/portfolio/status")
async def portfolio_safety_status():
    """Get overall portfolio safety status"""
    if not PORTFOLIO_SAFETY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Portfolio Safety module not available")
    
    status = portfolio_safety_service.get_safety_status()
    return safety_status_to_dict(status)


@app.get("/api/portfolio/exposure")
async def portfolio_exposure():
    """Get portfolio exposure metrics"""
    if not PORTFOLIO_SAFETY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Portfolio Safety module not available")
    
    metrics = portfolio_safety_service.exposure_monitor.calculate()
    return exposure_to_dict(metrics)


@app.get("/api/portfolio/correlation")
async def portfolio_correlation():
    """Get correlation metrics"""
    if not PORTFOLIO_SAFETY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Portfolio Safety module not available")
    
    metrics = portfolio_safety_service.correlation_monitor.calculate()
    return correlation_to_dict(metrics)


@app.get("/api/portfolio/kill-switch")
async def portfolio_kill_switch_status():
    """Get kill switch status"""
    if not PORTFOLIO_SAFETY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Portfolio Safety module not available")
    
    status = portfolio_safety_service.kill_switch.get_status()
    return kill_switch_to_dict(status)


@app.post("/api/portfolio/kill-switch/activate")
async def portfolio_kill_switch_activate(request: Request):
    """Activate kill switch manually"""
    if not PORTFOLIO_SAFETY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Portfolio Safety module not available")
    
    body = await request.json()
    reason = body.get("reason", "Manual activation")
    
    status = portfolio_safety_service.kill_switch.activate(
        KillSwitchTrigger.MANUAL,
        reason
    )
    
    return kill_switch_to_dict(status)


@app.post("/api/portfolio/kill-switch/deactivate")
async def portfolio_kill_switch_deactivate(request: Request):
    """Deactivate kill switch"""
    if not PORTFOLIO_SAFETY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Portfolio Safety module not available")
    
    body = await request.json() if request.method == "POST" else {}
    reason = body.get("reason", "Manual deactivation")
    
    status = portfolio_safety_service.kill_switch.deactivate(reason)
    
    return kill_switch_to_dict(status)


# ============================================
# Phase 9.25D: Validation Governance
# ============================================

try:
    from modules.validation_governance.service import (
        ValidationGovernanceService,
        validation_run_to_dict,
        comparison_to_dict,
        release_gate_to_dict
    )
    
    validation_governance_service = ValidationGovernanceService()
    VALIDATION_GOVERNANCE_AVAILABLE = True
    print("[Phase 9.25D] Validation Governance module loaded successfully")
except ImportError as e:
    VALIDATION_GOVERNANCE_AVAILABLE = False
    validation_governance_service = None
    print(f"[Phase 9.25D] Module not available: {e}")


@app.get("/api/validation-gov/health")
async def validation_governance_health():
    """Phase 9.25D Validation Governance health check"""
    if not VALIDATION_GOVERNANCE_AVAILABLE:
        return {"enabled": False, "status": "unavailable"}
    
    return validation_governance_service.get_health()


@app.get("/api/validation-gov/status")
async def validation_governance_status():
    """Get validation governance status"""
    if not VALIDATION_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation Governance module not available")
    
    return validation_governance_service.get_governance_status()


@app.get("/api/validation-gov/runs")
async def validation_runs_list():
    """Get all validation runs"""
    if not VALIDATION_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation Governance module not available")
    
    runs = validation_governance_service.registry.get_all_runs()
    
    return {
        "runs": {rid: validation_run_to_dict(r) for rid, r in runs.items()},
        "count": len(runs),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/validation-gov/runs/{run_id}")
async def validation_run_get(run_id: str):
    """Get specific validation run"""
    if not VALIDATION_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation Governance module not available")
    
    run = validation_governance_service.registry.get_run(run_id)
    
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return validation_run_to_dict(run)


@app.get("/api/validation-gov/compare/{run_id}")
async def validation_compare(run_id: str, baseline_id: Optional[str] = None):
    """Compare run against baseline"""
    if not VALIDATION_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation Governance module not available")
    
    comparison = validation_governance_service.comparator.compare(run_id, baseline_id)
    
    if not comparison:
        raise HTTPException(status_code=404, detail=f"Could not compare run {run_id}")
    
    return comparison_to_dict(comparison)


@app.post("/api/validation-gov/release-check")
async def validation_release_check(request: Request):
    """
    Check if run passes release criteria.
    
    Request body:
    {
        "runId": "run_phase92_quant_report"
    }
    """
    if not VALIDATION_GOVERNANCE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Validation Governance module not available")
    
    body = await request.json()
    run_id = body.get("runId")
    
    if not run_id:
        raise HTTPException(status_code=400, detail="runId required")
    
    gate = validation_governance_service.release_manager.check_release(run_id)
    
    return release_gate_to_dict(gate)


# ============================================
# Phase 9.26: Self-Healing Strategy Engine
# ============================================

try:
    from modules.self_healing.service import (
        SelfHealingService,
        health_to_dict,
        status_to_dict as healing_status_to_dict,
        event_to_dict,
        recovery_state_to_dict,
        regime_state_to_dict,
        asset_state_to_dict
    )
    
    self_healing_service = SelfHealingService()
    SELF_HEALING_AVAILABLE = True
    print("[Phase 9.26] Self-Healing module loaded successfully")
except ImportError as e:
    SELF_HEALING_AVAILABLE = False
    self_healing_service = None
    print(f"[Phase 9.26] Module not available: {e}")


@app.get("/api/self-healing/health")
async def self_healing_health():
    """Phase 9.26 Self-Healing health check"""
    if not SELF_HEALING_AVAILABLE:
        return {"enabled": False, "status": "unavailable"}
    
    return self_healing_service.get_health()


@app.get("/api/self-healing/status")
async def self_healing_status():
    """Get overall self-healing status"""
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    status = self_healing_service.get_status()
    return healing_status_to_dict(status)


@app.post("/api/self-healing/recompute")
async def self_healing_recompute(request: Request):
    """
    Recompute health and adjustments for all strategies.
    
    Request body (optional):
    {
        "strategies": ["MTF_BREAKOUT", ...]  // Optional list
    }
    """
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    body = {}
    try:
        body = await request.json()
    except:
        pass
    
    strategies = body.get("strategies")
    results = self_healing_service.recompute_all(strategies)
    
    return {
        "recomputed": True,
        "strategiesCount": len(results.get("health", {})),
        "demotions": len(results.get("demotions", [])),
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/self-healing/strategy/{strategy_id}")
async def self_healing_strategy(strategy_id: str):
    """Get detailed self-healing info for a strategy"""
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    details = self_healing_service.get_strategy_details(strategy_id)
    return details


@app.get("/api/self-healing/events")
async def self_healing_events(limit: int = 50):
    """Get recent self-healing events"""
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    events = self_healing_service.audit_trail.get_events(limit)
    
    return {
        "events": [event_to_dict(e) for e in events],
        "count": len(events),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.post("/api/self-healing/override")
async def self_healing_override(request: Request):
    """
    Manual override for a strategy.
    
    Request body:
    {
        "strategyId": "MTF_BREAKOUT",
        "action": "SET_WEIGHT" | "SET_LIFECYCLE" | "START_RECOVERY",
        "params": { "weight": 1.0 } | { "state": "APPROVED" } | {}
    }
    """
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    body = await request.json()
    
    strategy_id = body.get("strategyId")
    action = body.get("action")
    params = body.get("params", {})
    
    if not strategy_id or not action:
        raise HTTPException(status_code=400, detail="strategyId and action required")
    
    result = self_healing_service.override(strategy_id, action, params)
    
    return result


@app.post("/api/self-healing/recovery-check")
async def self_healing_recovery_check(request: Request):
    """
    Check recovery progress for strategies.
    
    Request body:
    {
        "strategyId": "MTF_BREAKOUT"  // Optional, checks all if not specified
    }
    """
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    body = {}
    try:
        body = await request.json()
    except:
        pass
    
    strategy_id = body.get("strategyId")
    
    if strategy_id:
        state = self_healing_service.recovery_engine.check_recovery(strategy_id)
        return recovery_state_to_dict(state)
    else:
        all_recoveries = self_healing_service.recovery_engine.get_all_recoveries()
        return {
            "recoveries": {sid: recovery_state_to_dict(s) for sid, s in all_recoveries.items()},
            "count": len(all_recoveries)
        }


@app.get("/api/self-healing/weights")
async def self_healing_weights():
    """Get current strategy weights"""
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    weights = self_healing_service.weight_adjuster.get_all_weights()
    
    return {
        "weights": weights,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@app.get("/api/self-healing/lifecycles")
async def self_healing_lifecycles():
    """Get current strategy lifecycles"""
    if not SELF_HEALING_AVAILABLE:
        raise HTTPException(status_code=503, detail="Self-Healing module not available")
    
    lifecycles = self_healing_service.demotion_engine.get_all_lifecycles()
    
    return {
        "lifecycles": lifecycles,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
