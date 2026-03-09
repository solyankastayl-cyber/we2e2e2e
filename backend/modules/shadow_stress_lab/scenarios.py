"""
Stress Lab Scenarios
====================

Phase 9.30B - Pre-defined crisis scenarios for stress testing.
"""

from .types import StressScenario, StressAssetClass, CrisisProfile


# ============================================
# Equity Crises
# ============================================

SCENARIO_1987_CRASH = StressScenario(
    scenario_id="EQUITY_1987_CRASH",
    name="1987 Black Monday",
    description="Single-day crash of 22.6%. Extreme volatility spike, instant correlation to 1.0, no warning signals.",
    asset_class=StressAssetClass.EQUITY,
    tags=["CRASH", "VOL_SPIKE", "FLASH", "CORRELATION"],
    start_date="1987-10-01",
    end_date="1987-12-31",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.35,
        drawdown_duration_bars=5,
        recovery_duration_bars=55,
        volatility_multiplier=6.0,
        correlation_spike=0.98,
        trend_direction=-1.0,
        volatility_clustering=0.9,
        liquidity_shock=0.8,
        mean_reversion_after=True
    ),
    total_bars=60,
    affected_assets=["EQUITY", "COMMODITY"]
)

SCENARIO_2000_DOTCOM = StressScenario(
    scenario_id="EQUITY_2000_DOTCOM",
    name="2000-2002 Dotcom Bust",
    description="Slow grinding bear market over 2.5 years. Gradual erosion of trend signals, false rallies, value rotation.",
    asset_class=StressAssetClass.EQUITY,
    tags=["BEAR_MARKET", "SLOW_BLEED", "FALSE_RALLY", "SECTOR_ROTATION"],
    start_date="2000-03-01",
    end_date="2002-10-01",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.50,
        drawdown_duration_bars=40,
        recovery_duration_bars=20,
        volatility_multiplier=2.0,
        correlation_spike=0.65,
        trend_direction=-0.7,
        volatility_clustering=0.5,
        liquidity_shock=0.2,
        mean_reversion_after=False
    ),
    total_bars=60,
    affected_assets=["EQUITY"]
)

SCENARIO_2008_GFC = StressScenario(
    scenario_id="EQUITY_2008_GFC",
    name="2008-2009 Global Financial Crisis",
    description="Systemic collapse. Extreme drawdown, correlation spike, liquidity freeze, multi-asset contagion.",
    asset_class=StressAssetClass.MULTI_ASSET,
    tags=["SYSTEMIC", "CRASH", "LIQUIDITY", "CORRELATION", "CONTAGION"],
    start_date="2008-09-01",
    end_date="2009-03-31",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.55,
        drawdown_duration_bars=25,
        recovery_duration_bars=35,
        volatility_multiplier=5.0,
        correlation_spike=0.95,
        trend_direction=-1.0,
        volatility_clustering=0.85,
        liquidity_shock=0.7,
        mean_reversion_after=True
    ),
    total_bars=60,
    affected_assets=["EQUITY", "CRYPTO", "FX", "COMMODITY"]
)

SCENARIO_2020_COVID = StressScenario(
    scenario_id="EQUITY_2020_COVID",
    name="2020 COVID Crash",
    description="Fastest 30% drop in history. V-shaped recovery. Extreme vol spike then rapid mean reversion.",
    asset_class=StressAssetClass.MULTI_ASSET,
    tags=["CRASH", "VOL_SPIKE", "V_RECOVERY", "PANDEMIC"],
    start_date="2020-02-19",
    end_date="2020-06-01",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.35,
        drawdown_duration_bars=8,
        recovery_duration_bars=30,
        volatility_multiplier=5.5,
        correlation_spike=0.92,
        trend_direction=-1.0,
        volatility_clustering=0.8,
        liquidity_shock=0.6,
        mean_reversion_after=True
    ),
    total_bars=45,
    affected_assets=["EQUITY", "CRYPTO", "FX", "COMMODITY"]
)

SCENARIO_2022_INFLATION = StressScenario(
    scenario_id="EQUITY_2022_INFLATION",
    name="2022 Inflation / Tightening",
    description="Sustained bear driven by rate hikes. Bond-equity correlation flip, growth rotation to value.",
    asset_class=StressAssetClass.EQUITY,
    tags=["BEAR_MARKET", "RATE_SHOCK", "INFLATION", "CORRELATION_FLIP"],
    start_date="2022-01-01",
    end_date="2022-10-01",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.28,
        drawdown_duration_bars=35,
        recovery_duration_bars=25,
        volatility_multiplier=2.5,
        correlation_spike=0.70,
        trend_direction=-0.6,
        volatility_clustering=0.6,
        liquidity_shock=0.3,
        mean_reversion_after=False
    ),
    total_bars=60,
    affected_assets=["EQUITY", "CRYPTO"]
)


# ============================================
# Crypto Crises
# ============================================

SCENARIO_2018_CRYPTO_WINTER = StressScenario(
    scenario_id="CRYPTO_2018_WINTER",
    name="2018 Crypto Winter",
    description="Post-ICO bubble collapse. 85% drawdown over 12 months. Persistent downtrend with dead cat bounces.",
    asset_class=StressAssetClass.CRYPTO,
    tags=["BEAR_MARKET", "BUBBLE_POP", "SLOW_BLEED", "DEAD_CAT"],
    start_date="2018-01-01",
    end_date="2018-12-31",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.75,
        drawdown_duration_bars=45,
        recovery_duration_bars=15,
        volatility_multiplier=3.0,
        correlation_spike=0.80,
        trend_direction=-0.9,
        volatility_clustering=0.6,
        liquidity_shock=0.4,
        mean_reversion_after=False
    ),
    total_bars=60,
    affected_assets=["CRYPTO"]
)

SCENARIO_2020_CRYPTO_CRASH = StressScenario(
    scenario_id="CRYPTO_2020_MARCH",
    name="March 2020 Crypto Crash",
    description="BTC drops 50% in 2 days. Extreme liquidation cascade, exchange outages, correlation with equities.",
    asset_class=StressAssetClass.CRYPTO,
    tags=["CRASH", "LIQUIDATION", "VOL_SPIKE", "FLASH"],
    start_date="2020-03-08",
    end_date="2020-04-15",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.50,
        drawdown_duration_bars=3,
        recovery_duration_bars=30,
        volatility_multiplier=7.0,
        correlation_spike=0.95,
        trend_direction=-1.0,
        volatility_clustering=0.9,
        liquidity_shock=0.85,
        mean_reversion_after=True
    ),
    total_bars=40,
    affected_assets=["CRYPTO"]
)

SCENARIO_2022_CRYPTO_DELEVERAGE = StressScenario(
    scenario_id="CRYPTO_2022_DELEVERAGE",
    name="2022 Crypto Deleveraging (LUNA/FTX)",
    description="Cascading failures: LUNA collapse, 3AC, FTX. Trust crisis, contagion, -70% over 8 months.",
    asset_class=StressAssetClass.CRYPTO,
    tags=["SYSTEMIC", "CONTAGION", "TRUST_CRISIS", "DELEVERAGE"],
    start_date="2022-05-01",
    end_date="2022-12-31",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.70,
        drawdown_duration_bars=35,
        recovery_duration_bars=25,
        volatility_multiplier=4.0,
        correlation_spike=0.88,
        trend_direction=-0.85,
        volatility_clustering=0.75,
        liquidity_shock=0.6,
        mean_reversion_after=False
    ),
    total_bars=60,
    affected_assets=["CRYPTO"]
)


# ============================================
# Macro / FX Crises
# ============================================

SCENARIO_1970_INFLATION = StressScenario(
    scenario_id="MACRO_1970_INFLATION",
    name="1970s Inflation Regime",
    description="Sustained high inflation, commodity super-cycle, equity stagnation, bond rout.",
    asset_class=StressAssetClass.MULTI_ASSET,
    tags=["INFLATION", "COMMODITY_BOOM", "STAGFLATION"],
    start_date="1973-01-01",
    end_date="1974-12-31",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.45,
        drawdown_duration_bars=40,
        recovery_duration_bars=20,
        volatility_multiplier=2.5,
        correlation_spike=0.60,
        trend_direction=-0.5,
        volatility_clustering=0.5,
        liquidity_shock=0.2,
        mean_reversion_after=False
    ),
    total_bars=60,
    affected_assets=["EQUITY", "FX", "COMMODITY"]
)

SCENARIO_1980_RATE_SHOCK = StressScenario(
    scenario_id="MACRO_1980_RATE_SHOCK",
    name="1980 Volcker Rate Shock",
    description="Fed funds to 20%. Massive USD rally, EM collapse, commodity crash, equity correction.",
    asset_class=StressAssetClass.FX,
    tags=["RATE_SHOCK", "USD_RALLY", "LIQUIDITY"],
    start_date="1980-01-01",
    end_date="1980-12-31",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.25,
        drawdown_duration_bars=20,
        recovery_duration_bars=40,
        volatility_multiplier=3.5,
        correlation_spike=0.75,
        trend_direction=-0.6,
        volatility_clustering=0.65,
        liquidity_shock=0.5,
        mean_reversion_after=True
    ),
    total_bars=60,
    affected_assets=["FX", "EQUITY", "COMMODITY"]
)

SCENARIO_2022_DXY_SPIKE = StressScenario(
    scenario_id="MACRO_2022_DXY_SPIKE",
    name="2022 Dollar Spike",
    description="DXY to 114. Multi-decade high. Crushed EM, crypto, commodities. USD wrecking ball.",
    asset_class=StressAssetClass.FX,
    tags=["USD_RALLY", "RATE_HIKE", "EM_STRESS"],
    start_date="2022-01-01",
    end_date="2022-09-30",
    crisis_profile=CrisisProfile(
        peak_drawdown=0.20,
        drawdown_duration_bars=30,
        recovery_duration_bars=30,
        volatility_multiplier=2.0,
        correlation_spike=0.70,
        trend_direction=-0.4,
        volatility_clustering=0.5,
        liquidity_shock=0.3,
        mean_reversion_after=True
    ),
    total_bars=60,
    affected_assets=["FX", "CRYPTO", "COMMODITY"]
)


# ============================================
# Scenario Registry
# ============================================

ALL_SCENARIOS: dict[str, StressScenario] = {
    s.scenario_id: s for s in [
        SCENARIO_1987_CRASH,
        SCENARIO_2000_DOTCOM,
        SCENARIO_2008_GFC,
        SCENARIO_2020_COVID,
        SCENARIO_2022_INFLATION,
        SCENARIO_2018_CRYPTO_WINTER,
        SCENARIO_2020_CRYPTO_CRASH,
        SCENARIO_2022_CRYPTO_DELEVERAGE,
        SCENARIO_1970_INFLATION,
        SCENARIO_1980_RATE_SHOCK,
        SCENARIO_2022_DXY_SPIKE,
    ]
}

EQUITY_SCENARIOS = [s for s in ALL_SCENARIOS.values() if s.asset_class in (StressAssetClass.EQUITY, StressAssetClass.MULTI_ASSET)]
CRYPTO_SCENARIOS = [s for s in ALL_SCENARIOS.values() if s.asset_class == StressAssetClass.CRYPTO]
MACRO_SCENARIOS = [s for s in ALL_SCENARIOS.values() if s.asset_class in (StressAssetClass.FX, StressAssetClass.COMMODITY)]
