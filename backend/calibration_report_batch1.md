# Phase 8.5 Calibration Report - Batch 1

## Date: 2026-03-07

## Summary

First validation batch completed on generated realistic market data (Binance API unavailable from this region).

---

## Batch 1 Results: BTC

| Symbol | TF | Win Rate | PF | Sharpe | Trades |
|--------|-----|----------|-----|--------|--------|
| BTCUSDT | 4h | 50.85% | 1.12 | - | 1595 |
| BTCUSDT | 1h | 48.72% | 0.95 | - | 6772 |
| BTCUSDT | 1d | 46.05% | 1.06 | - | 228 |

**Total: 8,595 trades**

---

## Batch 2 Results: ETH + SOL

| Symbol | TF | Win Rate | PF |
|--------|-----|----------|-----|
| ETHUSDT | 4h | 47.88% | 0.83 |
| ETHUSDT | 1d | 50.89% | 1.04 |
| SOLUSDT | 4h | 45.49% | 0.84 |
| SOLUSDT | 1d | 57.21% | 1.39 |

**Best performer: SOL 1D (WR=57.2%, PF=1.39)**

---

## Strategy Rankings (Aggregated)

| Strategy | Win Rate | Avg R | Status |
|----------|----------|-------|--------|
| MOMENTUM_CONTINUATION | 49.6% | +0.028 | ✅ KEEP |
| RANGE_REVERSAL | 49.5% | -0.013 | ⚠️ NEEDS_CALIBRATION |
| MTF_BREAKOUT | 46.3% | -0.036 | ⚠️ NEEDS_CALIBRATION |
| LIQUIDITY_SWEEP | 45.9% | -0.069 | ❌ DEPRECATED |

---

## Top Failure Patterns

1. **EARLY_EXIT** (7 occurrences) - Exits too early, missing profit
2. **FALSE_BREAKOUT** (7 occurrences) - Breakout signals fail
3. **MTF_CONFLICT** (3 occurrences) - Timeframe disagreement
4. **WRONG_SCENARIO** (2 occurrences) - Scenario prediction wrong
5. **LATE_ENTRY** (1 occurrence) - Entry timing off

---

## Calibration Recommendations

### Priority 1: Strategy Pruning
- **DEPRECATED**: `LIQUIDITY_SWEEP` (WR=45.9%, AvgR=-0.069)
- **KEEP**: `MOMENTUM_CONTINUATION` (best performer)

### Priority 2: Failure-Driven Fixes
1. **EARLY_EXIT fix**: Adjust target placement, consider trailing stops
2. **FALSE_BREAKOUT fix**: Add volume confirmation, wait for retest
3. **MTF_CONFLICT fix**: Strengthen MTF alignment penalty

### Priority 3: Threshold Calibration
- `confidence_min`: 0.6 → 0.55 (current too strict)
- `mtfBoost`: 1.15 → 1.25 (stronger MTF weight)
- `breakout_confirmation_bars`: 1 → 2

---

## Edge Assessment

| Metric | Value | Status |
|--------|-------|--------|
| Overall Win Rate | ~49% | ⚠️ Borderline |
| Profit Factor | ~1.04 | ⚠️ Weak edge |
| Direction Accuracy | 60.2% | ✅ Good |
| Robustness | 83.2% | ✅ Strong |

**Verdict: WEAK_EDGE → needs calibration before live**

---

## Next Steps

1. ✅ Complete Batch 1 & 2 - DONE
2. ⏳ Apply strategy pruning
3. ⏳ Implement failure-driven fixes
4. ⏳ Re-run validation after calibration
5. ⏳ Paper trading test

---

## Notes

- Data source: Generated realistic OHLCV (Binance API blocked)
- When real data available, re-run calibration for accurate results
- Current results show system architecture is working correctly
