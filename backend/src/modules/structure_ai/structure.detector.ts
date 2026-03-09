/**
 * Phase 7 — Market Structure AI: Event Detector
 * 
 * Detects individual market events from raw indicators
 */

import { 
  MarketEvent, 
  MarketEventType, 
  EventDirection,
  StructureInput,
  DEFAULT_STRUCTURE_CONFIG 
} from './structure.types.js';

let eventCounter = 0;

function generateEventId(): string {
  return `evt_${Date.now()}_${++eventCounter}`;
}

/**
 * Detect LIQUIDITY_SWEEP event
 */
export function detectLiquiditySweep(input: StructureInput): MarketEvent | null {
  if (!input.liquiditySweep) return null;
  
  const { direction, price } = input.liquiditySweep;
  
  // Check for volume confirmation
  const volumeConfirmed = input.volume.spike || 
    (input.volume.current > input.volume.average * 1.3);
  
  // Check for RSI divergence (common after sweep)
  const divergenceConfirmed = input.rsi.divergence !== null;
  
  // Calculate probability and strength
  let probability = 0.5;
  let strength = 0.5;
  
  if (volumeConfirmed) {
    probability += 0.15;
    strength += 0.1;
  }
  
  if (divergenceConfirmed) {
    probability += 0.15;
    strength += 0.15;
  }
  
  // Equal highs/lows swept
  if ((direction === 'UP' && input.equalHighs) || 
      (direction === 'DOWN' && input.equalLows)) {
    probability += 0.1;
    strength += 0.1;
  }
  
  return {
    id: generateEventId(),
    type: 'LIQUIDITY_SWEEP',
    direction: direction,
    probability: Math.min(probability, 0.95),
    strength: Math.min(strength, 0.95),
    confidence: (probability + strength) / 2,
    priceLevel: price,
    timestamp: Date.now(),
    triggerIndicators: ['liquidity', volumeConfirmed ? 'volume_spike' : 'volume', 
                        divergenceConfirmed ? 'rsi_divergence' : ''].filter(Boolean),
    startCandle: 0,
    notes: [
      `Liquidity sweep ${direction}`,
      volumeConfirmed ? 'Volume confirmed' : 'Low volume',
      divergenceConfirmed ? 'RSI divergence detected' : ''
    ].filter(Boolean)
  };
}

/**
 * Detect COMPRESSION event
 */
export function detectCompression(input: StructureInput): MarketEvent | null {
  if (!input.compression) return null;
  
  const candles = input.compressionCandles || 5;
  const minCandles = DEFAULT_STRUCTURE_CONFIG.thresholds.compressionCandles;
  
  if (candles < minCandles) return null;
  
  // Low volatility regime strengthens compression
  const volConfirmed = input.volRegime === 'LOW' || input.atr.percentile < 30;
  
  // RSI near 50 (balanced)
  const rsiBalanced = input.rsi.value > 40 && input.rsi.value < 60;
  
  // Calculate probability
  let probability = 0.55;
  let strength = 0.5;
  
  if (volConfirmed) {
    probability += 0.15;
    strength += 0.15;
  }
  
  if (rsiBalanced) {
    probability += 0.1;
  }
  
  // Longer compression = stronger
  if (candles >= 10) {
    strength += 0.15;
    probability += 0.1;
  }
  
  return {
    id: generateEventId(),
    type: 'COMPRESSION',
    direction: 'NEUTRAL',
    probability: Math.min(probability, 0.95),
    strength: Math.min(strength, 0.95),
    confidence: (probability + strength) / 2,
    timestamp: Date.now(),
    triggerIndicators: ['compression', volConfirmed ? 'low_vol' : '', 
                        rsiBalanced ? 'rsi_balanced' : ''].filter(Boolean),
    startCandle: -candles,
    duration: candles,
    notes: [
      `Compression for ${candles} candles`,
      volConfirmed ? 'Low volatility confirmed' : 'Normal volatility',
      rsiBalanced ? 'RSI balanced (40-60)' : 'RSI imbalanced'
    ].filter(Boolean)
  };
}

/**
 * Detect BREAKOUT event
 */
export function detectBreakout(input: StructureInput): MarketEvent | null {
  if (!input.breakout) return null;
  
  const { direction, confirmed } = input.breakout;
  
  // Volume spike essential for breakout
  const volumeConfirmed = input.volume.spike;
  
  // MACD crossover supports direction
  const macdConfirmed = 
    (direction === 'UP' && input.macd.crossover === 'BULL') ||
    (direction === 'DOWN' && input.macd.crossover === 'BEAR');
  
  // Momentum supports
  const momentumSupports = 
    (direction === 'UP' && input.rsi.value > 50) ||
    (direction === 'DOWN' && input.rsi.value < 50);
  
  let probability = confirmed ? 0.6 : 0.4;
  let strength = 0.5;
  
  if (volumeConfirmed) {
    probability += 0.2;
    strength += 0.2;
  }
  
  if (macdConfirmed) {
    probability += 0.1;
    strength += 0.1;
  }
  
  if (momentumSupports) {
    probability += 0.05;
  }
  
  return {
    id: generateEventId(),
    type: 'BREAKOUT',
    direction: direction,
    probability: Math.min(probability, 0.95),
    strength: Math.min(strength, 0.95),
    confidence: (probability + strength) / 2,
    timestamp: Date.now(),
    triggerIndicators: ['breakout', 
                        volumeConfirmed ? 'volume_spike' : '',
                        macdConfirmed ? 'macd_crossover' : '',
                        momentumSupports ? 'rsi' : ''].filter(Boolean),
    startCandle: 0,
    notes: [
      `Breakout ${direction}`,
      confirmed ? 'Confirmed' : 'Unconfirmed',
      volumeConfirmed ? 'Strong volume' : 'Weak volume',
      macdConfirmed ? 'MACD confirms' : ''
    ].filter(Boolean)
  };
}

/**
 * Detect EXPANSION event
 */
export function detectExpansion(input: StructureInput): MarketEvent | null {
  // Expansion = high volatility + trending
  const isExpansion = 
    (input.volRegime === 'HIGH' || input.volRegime === 'EXTREME') &&
    (input.regime === 'TREND_UP' || input.regime === 'TREND_DOWN');
  
  if (!isExpansion) return null;
  
  // Strong volume
  const strongVolume = input.volume.current > input.volume.average * 1.5;
  
  // Momentum alignment
  const momentumStrong = 
    (input.regime === 'TREND_UP' && input.rsi.value > 60) ||
    (input.regime === 'TREND_DOWN' && input.rsi.value < 40);
  
  const direction: EventDirection = input.regime === 'TREND_UP' ? 'UP' : 'DOWN';
  
  let probability = 0.6;
  let strength = 0.6;
  
  if (strongVolume) {
    probability += 0.15;
    strength += 0.15;
  }
  
  if (momentumStrong) {
    probability += 0.1;
    strength += 0.1;
  }
  
  return {
    id: generateEventId(),
    type: 'EXPANSION',
    direction,
    probability: Math.min(probability, 0.95),
    strength: Math.min(strength, 0.95),
    confidence: (probability + strength) / 2,
    timestamp: Date.now(),
    triggerIndicators: ['high_vol', strongVolume ? 'volume_spike' : '', 
                        momentumStrong ? 'strong_momentum' : ''].filter(Boolean),
    startCandle: 0,
    notes: [
      `Expansion ${direction}`,
      input.volRegime === 'EXTREME' ? 'Extreme volatility' : 'High volatility',
      strongVolume ? 'Strong volume' : '',
      momentumStrong ? 'Strong momentum' : ''
    ].filter(Boolean)
  };
}

/**
 * Detect EXHAUSTION event
 */
export function detectExhaustion(input: StructureInput): MarketEvent | null {
  const threshold = DEFAULT_STRUCTURE_CONFIG.thresholds.exhaustionRsiThreshold;
  
  // Exhaustion = extreme RSI + potential divergence
  const rsiExhausted = input.rsi.value > threshold || input.rsi.value < (100 - threshold);
  
  if (!rsiExhausted) return null;
  
  const direction: EventDirection = input.rsi.value > 50 ? 'UP' : 'DOWN';
  
  // Divergence strengthens exhaustion signal
  const hasDivergence = input.rsi.divergence !== null;
  
  // Volume diminishing
  const volumeWeak = input.volume.current < input.volume.average * 0.8;
  
  let probability = 0.5;
  let strength = 0.5;
  
  if (hasDivergence) {
    probability += 0.25;
    strength += 0.2;
  }
  
  if (volumeWeak) {
    probability += 0.1;
  }
  
  // Extreme RSI
  if (input.rsi.value > 80 || input.rsi.value < 20) {
    probability += 0.1;
    strength += 0.1;
  }
  
  return {
    id: generateEventId(),
    type: 'EXHAUSTION',
    direction,
    probability: Math.min(probability, 0.95),
    strength: Math.min(strength, 0.95),
    confidence: (probability + strength) / 2,
    timestamp: Date.now(),
    triggerIndicators: ['rsi_extreme', 
                        hasDivergence ? 'divergence' : '',
                        volumeWeak ? 'weak_volume' : ''].filter(Boolean),
    startCandle: 0,
    notes: [
      `Exhaustion ${direction}`,
      `RSI at ${input.rsi.value.toFixed(1)}`,
      hasDivergence ? 'Divergence detected' : '',
      volumeWeak ? 'Weak volume' : ''
    ].filter(Boolean)
  };
}

/**
 * Detect ACCUMULATION event
 */
export function detectAccumulation(input: StructureInput): MarketEvent | null {
  // Accumulation = range + low volatility + volume patterns
  const isRange = input.regime === 'RANGE';
  const lowVol = input.volRegime === 'LOW' || input.volRegime === 'NORMAL';
  
  // Structure shows higher lows (bullish accumulation)
  const bullishStructure = input.higherLow && !input.lowerHigh;
  
  if (!isRange || !lowVol || !bullishStructure) return null;
  
  let probability = 0.55;
  let strength = 0.5;
  
  if (input.compressionCandles && input.compressionCandles > 8) {
    probability += 0.1;
  }
  
  if (input.rsi.value < 50 && input.rsi.value > 30) {
    probability += 0.1;
    strength += 0.1;
  }
  
  return {
    id: generateEventId(),
    type: 'ACCUMULATION',
    direction: 'UP',
    probability: Math.min(probability, 0.9),
    strength: Math.min(strength, 0.9),
    confidence: (probability + strength) / 2,
    timestamp: Date.now(),
    triggerIndicators: ['range', 'higher_lows', 'low_vol'].filter(Boolean),
    startCandle: -(input.compressionCandles || 0),
    notes: [
      'Accumulation pattern',
      'Higher lows forming',
      'Range bound with low volatility'
    ]
  };
}

/**
 * Detect DISTRIBUTION event
 */
export function detectDistribution(input: StructureInput): MarketEvent | null {
  // Distribution = range + low volatility + lower highs
  const isRange = input.regime === 'RANGE';
  const lowVol = input.volRegime === 'LOW' || input.volRegime === 'NORMAL';
  
  // Structure shows lower highs (bearish distribution)
  const bearishStructure = input.lowerHigh && !input.higherLow;
  
  if (!isRange || !lowVol || !bearishStructure) return null;
  
  let probability = 0.55;
  let strength = 0.5;
  
  if (input.compressionCandles && input.compressionCandles > 8) {
    probability += 0.1;
  }
  
  if (input.rsi.value > 50 && input.rsi.value < 70) {
    probability += 0.1;
    strength += 0.1;
  }
  
  return {
    id: generateEventId(),
    type: 'DISTRIBUTION',
    direction: 'DOWN',
    probability: Math.min(probability, 0.9),
    strength: Math.min(strength, 0.9),
    confidence: (probability + strength) / 2,
    timestamp: Date.now(),
    triggerIndicators: ['range', 'lower_highs', 'low_vol'].filter(Boolean),
    startCandle: -(input.compressionCandles || 0),
    notes: [
      'Distribution pattern',
      'Lower highs forming',
      'Range bound with low volatility'
    ]
  };
}

/**
 * Detect REVERSAL event
 */
export function detectReversal(input: StructureInput): MarketEvent | null {
  // Reversal needs: trend + exhaustion + structure change
  const isTrend = input.regime === 'TREND_UP' || input.regime === 'TREND_DOWN';
  if (!isTrend) return null;
  
  // Structure reversal
  const structureReversal = 
    (input.regime === 'TREND_UP' && input.lowerHigh && input.lowerLow) ||
    (input.regime === 'TREND_DOWN' && input.higherLow && input.higherHigh);
  
  // RSI divergence
  const hasDivergence = input.rsi.divergence !== null;
  
  if (!structureReversal && !hasDivergence) return null;
  
  const direction: EventDirection = input.regime === 'TREND_UP' ? 'DOWN' : 'UP';
  
  let probability = 0.4;
  let strength = 0.45;
  
  if (structureReversal) {
    probability += 0.2;
    strength += 0.2;
  }
  
  if (hasDivergence) {
    probability += 0.15;
    strength += 0.15;
  }
  
  if (input.volume.spike) {
    probability += 0.1;
    strength += 0.1;
  }
  
  return {
    id: generateEventId(),
    type: 'REVERSAL',
    direction,
    probability: Math.min(probability, 0.9),
    strength: Math.min(strength, 0.9),
    confidence: (probability + strength) / 2,
    timestamp: Date.now(),
    triggerIndicators: [
      structureReversal ? 'structure_reversal' : '',
      hasDivergence ? 'divergence' : '',
      input.volume.spike ? 'volume_spike' : ''
    ].filter(Boolean),
    startCandle: 0,
    notes: [
      `Reversal ${direction}`,
      structureReversal ? 'Structure confirms' : '',
      hasDivergence ? 'Divergence confirms' : ''
    ].filter(Boolean)
  };
}

/**
 * Detect all events from input
 */
export function detectAllEvents(input: StructureInput): MarketEvent[] {
  const events: MarketEvent[] = [];
  
  // Try all detectors
  const detectors = [
    detectLiquiditySweep,
    detectCompression,
    detectBreakout,
    detectExpansion,
    detectExhaustion,
    detectAccumulation,
    detectDistribution,
    detectReversal
  ];
  
  for (const detector of detectors) {
    const event = detector(input);
    if (event && event.probability >= DEFAULT_STRUCTURE_CONFIG.minEventProbability) {
      events.push(event);
    }
  }
  
  // Sort by confidence
  events.sort((a, b) => b.confidence - a.confidence);
  
  return events;
}
