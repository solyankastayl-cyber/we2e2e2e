"""
Phase 9.27: Meta-Strategy API Routes
====================================

API endpoints for Meta-Strategy Layer.

Endpoints:
- GET  /api/meta-strategy/health      - Health check
- GET  /api/meta-strategy/status      - Full status
- GET  /api/meta-strategy/weights     - Strategy weights
- GET  /api/meta-strategy/strategy/{id} - Strategy details
- GET  /api/meta-strategy/families    - Family allocations
- GET  /api/meta-strategy/tiers       - Tier allocations
- GET  /api/meta-strategy/crowding    - Crowding analysis
- GET  /api/meta-strategy/admission   - Recent admissions
- POST /api/meta-strategy/recompute   - Recompute all
- POST /api/meta-strategy/admit       - Check signal admission
- POST /api/meta-strategy/load        - Load strategy data
"""

import time
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

# Import service
try:
    from modules.meta_strategy.service import (
        MetaStrategyService,
        strategy_score_to_dict,
        meta_state_to_dict,
        DEFAULT_META_STRATEGY_CONFIG
    )
    
    meta_strategy_service = MetaStrategyService()
    META_STRATEGY_AVAILABLE = True
    print("[Phase 9.27] Meta-Strategy module loaded successfully")
except ImportError as e:
    META_STRATEGY_AVAILABLE = False
    meta_strategy_service = None
    print(f"[Phase 9.27] Module not available: {e}")


router = APIRouter(prefix="/api/meta-strategy", tags=["Meta-Strategy"])


# ============================================
# Health & Status
# ============================================

@router.get("/health")
async def meta_strategy_health():
    """Meta-Strategy health check"""
    if not META_STRATEGY_AVAILABLE:
        return {
            "enabled": False,
            "version": "phase9.27",
            "status": "unavailable",
            "error": "Module not loaded"
        }
    
    return meta_strategy_service.get_health()


@router.get("/status")
async def meta_strategy_status():
    """Get full meta-strategy status"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    state = meta_strategy_service.get_status()
    return meta_state_to_dict(state)


# ============================================
# Strategy Weights
# ============================================

@router.get("/weights")
async def meta_strategy_weights():
    """Get current strategy weights"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    weights = meta_strategy_service.get_weights()
    
    return {
        "weights": weights,
        "count": len(weights),
        "totalWeight": sum(weights.values()),
        "timestamp": int(time.time() * 1000)
    }


@router.get("/strategy/{strategy_id}")
async def meta_strategy_details(strategy_id: str):
    """Get detailed meta-strategy info for a strategy"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    state = meta_strategy_service.get_status()
    
    if strategy_id not in state.strategy_scores:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    
    score = state.strategy_scores[strategy_id]
    return strategy_score_to_dict(score)


# ============================================
# Family Allocations
# ============================================

@router.get("/families")
async def meta_strategy_families():
    """Get family allocation status"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    families = meta_strategy_service.get_families()
    
    return {
        "families": families,
        "count": len(families),
        "totalAllocated": sum(f["currentWeight"] for f in families.values()),
        "timestamp": int(time.time() * 1000)
    }


@router.get("/families/{family}")
async def meta_strategy_family_details(family: str):
    """Get details for a specific family"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    families = meta_strategy_service.get_families()
    
    if family not in families:
        raise HTTPException(status_code=404, detail=f"Family {family} not found")
    
    # Get strategies in this family
    state = meta_strategy_service.get_status()
    family_strategies = [
        strategy_score_to_dict(s)
        for s in state.strategy_scores.values()
        if s.family == family
    ]
    
    return {
        "family": family,
        "allocation": families[family],
        "strategies": family_strategies,
        "strategyCount": len(family_strategies)
    }


# ============================================
# Tier Allocations
# ============================================

@router.get("/tiers")
async def meta_strategy_tiers():
    """Get tier allocation status"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    tiers = meta_strategy_service.get_tiers()
    
    return {
        "tiers": tiers,
        "count": len(tiers),
        "totalBudget": sum(t["budget"] for t in tiers.values()),
        "totalUsed": sum(t["current"] for t in tiers.values()),
        "timestamp": int(time.time() * 1000)
    }


@router.get("/tiers/{tier}")
async def meta_strategy_tier_details(tier: str):
    """Get details for a specific tier"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    tiers = meta_strategy_service.get_tiers()
    
    if tier not in tiers:
        raise HTTPException(status_code=404, detail=f"Tier {tier} not found")
    
    # Get strategies in this tier
    state = meta_strategy_service.get_status()
    tier_strategies = [
        strategy_score_to_dict(s)
        for s in state.strategy_scores.values()
        if s.tier == tier
    ]
    
    return {
        "tier": tier,
        "allocation": tiers[tier],
        "strategies": tier_strategies,
        "strategyCount": len(tier_strategies)
    }


# ============================================
# Crowding Analysis
# ============================================

@router.get("/crowding")
async def meta_strategy_crowding():
    """Get crowding analysis"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    return meta_strategy_service.get_crowding()


@router.get("/crowding/pairs")
async def meta_strategy_crowding_pairs(min_overlap: float = 0.2):
    """Get crowding pairs above threshold"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    crowding = meta_strategy_service.get_crowding()
    
    filtered_pairs = [
        p for p in crowding["pairs"]
        if p["totalOverlap"] >= min_overlap
    ]
    
    return {
        "pairs": filtered_pairs,
        "count": len(filtered_pairs),
        "minOverlap": min_overlap
    }


@router.get("/crowding/clusters")
async def meta_strategy_crowding_clusters():
    """Get crowding clusters"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    crowding = meta_strategy_service.get_crowding()
    
    return {
        "clusters": crowding["clusters"],
        "count": len(crowding["clusters"])
    }


# ============================================
# Admission
# ============================================

@router.get("/admission")
async def meta_strategy_admissions(limit: int = 50):
    """Get recent admission decisions"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    admissions = meta_strategy_service.get_admissions(limit)
    
    admitted_count = sum(1 for a in admissions if a["admitted"])
    
    return {
        "admissions": admissions,
        "count": len(admissions),
        "admittedCount": admitted_count,
        "blockedCount": len(admissions) - admitted_count
    }


@router.post("/admit")
async def meta_strategy_admit(request: Request):
    """
    Check admission for a strategy signal.
    
    Request body:
    {
        "strategyId": "MTF_BREAKOUT",
        "signalId": "sig_123456"
    }
    """
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    body = await request.json()
    
    strategy_id = body.get("strategyId")
    signal_id = body.get("signalId", f"sig_{int(time.time() * 1000)}")
    
    if not strategy_id:
        raise HTTPException(status_code=400, detail="strategyId is required")
    
    decision = meta_strategy_service.admit_signal(strategy_id, signal_id)
    
    return {
        "strategyId": decision.strategy_id,
        "signalId": decision.signal_id,
        "admitted": decision.admitted,
        "status": decision.status,
        "finalWeight": decision.final_weight,
        "checks": decision.checks,
        "reason": decision.reason,
        "timestamp": decision.timestamp
    }


# ============================================
# Recompute
# ============================================

@router.post("/recompute")
async def meta_strategy_recompute(request: Request):
    """
    Recompute all strategy weights and allocations.
    
    Request body:
    {
        "regime": "TREND_UP",  // Optional, default RANGE
        "portfolioState": {...}  // Optional
    }
    """
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    body = {}
    try:
        body = await request.json()
    except:
        pass
    
    regime = body.get("regime", "RANGE")
    portfolio_state = body.get("portfolioState")
    
    result = meta_strategy_service.recompute(regime, portfolio_state)
    
    return result


@router.post("/load")
async def meta_strategy_load(request: Request):
    """
    Load strategy data for scoring.
    
    Request body:
    {
        "strategies": {
            "MTF_BREAKOUT": {
                "family": "breakout_family",
                "tier": "CORE",
                "health_verdict": "HEALTHY",
                "health_score": 0.85,
                "lifecycle": "APPROVED",
                "rolling_pf": 1.6,
                "rolling_wr": 0.58,
                "activation_map": {"TREND_UP": "ON", "RANGE": "LIMITED"},
                "features": ["breakout", "volume", "mtf"]
            },
            ...
        }
    }
    """
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    body = await request.json()
    strategies = body.get("strategies", {})
    
    if not strategies:
        raise HTTPException(status_code=400, detail="strategies data is required")
    
    meta_strategy_service.load_strategies(strategies)
    
    return {
        "success": True,
        "strategiesLoaded": len(strategies),
        "message": f"Loaded {len(strategies)} strategies",
        "timestamp": int(time.time() * 1000)
    }


# ============================================
# Configuration
# ============================================

@router.get("/config")
async def meta_strategy_config():
    """Get current configuration"""
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    return {
        "config": meta_strategy_service.config,
        "version": "phase9.27"
    }


@router.post("/config")
async def meta_strategy_update_config(request: Request):
    """
    Update configuration.
    
    Request body:
    {
        "tierBudgets": {...},
        "familyBudgets": {...},
        "crowding": {...},
        "admission": {...}
    }
    """
    if not META_STRATEGY_AVAILABLE:
        raise HTTPException(status_code=503, detail="Meta-Strategy module not available")
    
    body = await request.json()
    
    # Deep merge with existing config
    config = meta_strategy_service.config.copy()
    
    if "tierBudgets" in body:
        config["tier_budgets"].update(body["tierBudgets"])
    if "familyBudgets" in body:
        config["family_budgets"].update(body["familyBudgets"])
    if "crowding" in body:
        config["crowding"].update(body["crowding"])
    if "admission" in body:
        config["admission"].update(body["admission"])
    
    # Reinitialize service with new config
    meta_strategy_service.config = config
    meta_strategy_service.scoring_engine.config = config
    meta_strategy_service.crowding_detector.config = config.get("crowding", {})
    meta_strategy_service.family_manager.config = config.get("family_budgets", {})
    meta_strategy_service.tier_allocator.config = config.get("tier_budgets", {})
    meta_strategy_service.admission_engine.config = config.get("admission", {})
    
    return {
        "success": True,
        "message": "Configuration updated",
        "timestamp": int(time.time() * 1000)
    }
