# Phase 8.5 Calibration Report - Coinbase Real Data

## Date: 2026-03-07

## Data Source: Coinbase Exchange API (REAL DATA)

---

## CRITICAL FINDINGS

### BTC 1D shows REAL EDGE 🎯

| TF | Win Rate | PF | Trades | Status |
|----|----------|-----|--------|--------|
| **1D** | **45.4%** | **1.54** | 130 | ✅ **PROFITABLE** |
| 4H | 38.1% | 0.54 | 879 | ❌ LOSING |
| 1H | 35.6% | 0.55 | 3208 | ❌ LOSING |

### Strategy Performance (All TFs)

| Strategy | Win Rate | Avg R | Status |
|----------|----------|-------|--------|
| MOMENTUM_CONTINUATION | 32.5% | -0.17 | ❌ |
| MTF_BREAKOUT | 36.6% | -0.27 | ❌ |
| LIQUIDITY_SWEEP | 33.0% | -0.32 | ❌ |
| RANGE_REVERSAL | 38.4% | -0.47 | ❌ |

### Top Failures (Real Data)

1. EARLY_EXIT (3)
2. FALSE_BREAKOUT (3)
3. REGIME_MISMATCH (2)
4. WRONG_SCENARIO (2)

---

## ANALYSIS

### Why 1D Works

1. **Lower noise** - daily candles filter out intraday noise
2. **Stronger signals** - breakouts/reversals more significant
3. **Less overtrading** - 130 trades vs 3200+ on 1H

### Why 4H/1H Fail

1. **Too much noise** - false signals
2. **RANGE_REVERSAL overfits** - 2618 trades on bad strategy
3. **Entry timing** - too late on lower TFs

---

## CALIBRATION DECISIONS

### Strategy Pruning

| Strategy | Decision | Reason |
|----------|----------|--------|
| RANGE_REVERSAL | ❌ **DEPRECATED** | Negative edge, overtrading |
| LIQUIDITY_SWEEP | ❌ **DEPRECATED** | No edge without orderbook |
| MTF_BREAKOUT | ⚠️ **TESTING** | Only for 1D TF |
| MOMENTUM_CONTINUATION | ⚠️ **TESTING** | Only for 1D TF |

### Timeframe Focus

**Primary:** 1D (edge confirmed)
**Secondary:** 4H (needs calibration)
**Skip:** 1H (too noisy)

### Entry Filters Needed

1. **Volatility filter** - skip low vol days
2. **Volume confirmation** - breakout + 1.4x volume
3. **Regime filter** - trend-following only in trends

---

## NEXT STEPS

1. ✅ Coinbase provider working
2. ✅ Real data validation complete
3. ⏳ Remove RANGE_REVERSAL, LIQUIDITY_SWEEP
4. ⏳ Focus strategies on 1D timeframe
5. ⏳ Add volatility + volume filters
6. ⏳ Re-run validation

---

## CODE CHANGES NEEDED

### 1. Strategy Registry Update

```python
# In strategy_registry.py
DEPRECATED_STRATEGIES = ["RANGE_REVERSAL", "LIQUIDITY_SWEEP"]
TESTING_STRATEGIES = ["MTF_BREAKOUT", "MOMENTUM_CONTINUATION"]
```

### 2. Timeframe Filter

```python
# In simulation.py
ALLOWED_TIMEFRAMES = ["1d", "4h"]  # Skip 1h for now
```

### 3. Volume Confirmation

```python
# In breakout detector
def is_valid_breakout(candle, volume_ma):
    return (
        candle['volume'] > volume_ma * 1.4 and
        candle['body_ratio'] > 0.55
    )
```

---

## VERDICT

**Edge exists on 1D timeframe (PF=1.54)**

System needs calibration:
- Remove losing strategies
- Focus on 1D
- Add entry filters

After calibration, expect:
- PF > 1.5 on 1D
- WR > 50%
- Positive edge on 4H
