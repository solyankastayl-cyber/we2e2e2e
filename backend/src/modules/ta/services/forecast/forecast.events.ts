/**
 * Forecast Events (P4.4)
 * 
 * Event detection along forecast path
 */

import type { 
  ForecastEvent, 
  ForecastPoint, 
  ForecastBandsPoint,
  ForecastComputeInput,
  ForecastEventKind
} from './forecast.types.js';

/**
 * Detect breakout event
 */
function detectBreakout(
  path: ForecastPoint[],
  breakoutLevel: number,
  bias: string
): ForecastEvent | null {
  for (let i = 1; i < path.length; i++) {
    const prev = path[i - 1].price;
    const curr = path[i].price;
    
    // Crossed breakout level
    if (bias === 'LONG' && prev < breakoutLevel && curr >= breakoutLevel) {
      return {
        kind: 'BREAKOUT',
        t: path[i].t,
        price: breakoutLevel,
        confidence: 0.7,
        barOffset: i
      };
    }
    
    if (bias === 'SHORT' && prev > breakoutLevel && curr <= breakoutLevel) {
      return {
        kind: 'BREAKOUT',
        t: path[i].t,
        price: breakoutLevel,
        confidence: 0.7,
        barOffset: i
      };
    }
  }
  
  return null;
}

/**
 * Detect target hit
 */
function detectTargetHit(
  path: ForecastPoint[],
  target: number,
  bias: string
): ForecastEvent | null {
  for (let i = 1; i < path.length; i++) {
    const curr = path[i].price;
    
    if (bias === 'LONG' && curr >= target) {
      return {
        kind: 'TARGET_HIT',
        t: path[i].t,
        price: target,
        confidence: 0.6,
        barOffset: i
      };
    }
    
    if (bias === 'SHORT' && curr <= target) {
      return {
        kind: 'TARGET_HIT',
        t: path[i].t,
        price: target,
        confidence: 0.6,
        barOffset: i
      };
    }
  }
  
  return null;
}

/**
 * Detect stop hit
 */
function detectStopHit(
  path: ForecastPoint[],
  stop: number,
  bias: string
): ForecastEvent | null {
  for (let i = 1; i < path.length; i++) {
    const curr = path[i].price;
    
    if (bias === 'LONG' && curr <= stop) {
      return {
        kind: 'STOP_HIT',
        t: path[i].t,
        price: stop,
        confidence: 0.5,
        barOffset: i
      };
    }
    
    if (bias === 'SHORT' && curr >= stop) {
      return {
        kind: 'STOP_HIT',
        t: path[i].t,
        price: stop,
        confidence: 0.5,
        barOffset: i
      };
    }
  }
  
  return null;
}

/**
 * Detect retest after breakout
 */
function detectRetest(
  path: ForecastPoint[],
  breakoutEvent: ForecastEvent | null,
  breakoutLevel: number
): ForecastEvent | null {
  if (!breakoutEvent) return null;
  
  const tolerance = breakoutLevel * 0.005; // 0.5% tolerance
  
  for (let i = breakoutEvent.barOffset + 1; i < path.length; i++) {
    const curr = path[i].price;
    
    // Price returned to breakout zone
    if (Math.abs(curr - breakoutLevel) <= tolerance) {
      return {
        kind: 'RETEST',
        t: path[i].t,
        price: curr,
        confidence: 0.65,
        barOffset: i
      };
    }
  }
  
  return null;
}

/**
 * Detect level touches
 */
function detectLevelTouches(
  bands: ForecastBandsPoint[],
  levels: number[]
): ForecastEvent[] {
  const events: ForecastEvent[] = [];
  
  for (const level of levels) {
    for (let i = 0; i < bands.length; i++) {
      const { p10, p90 } = bands[i];
      
      // Level is within bands range
      if (level >= p10 && level <= p90) {
        events.push({
          kind: 'LEVEL_TOUCH',
          t: bands[i].t,
          price: level,
          confidence: 0.5,
          barOffset: i,
          meta: { level }
        });
        break; // Only first touch per level
      }
    }
  }
  
  return events;
}

/**
 * Extract all events from forecast
 */
export function extractEvents(
  path: ForecastPoint[],
  bands: ForecastBandsPoint[],
  input: ForecastComputeInput,
  levels: number[] = []
): ForecastEvent[] {
  const events: ForecastEvent[] = [];
  const bias = input.bias || 'WAIT';
  
  // Breakout
  if (input.breakoutLevel) {
    const breakout = detectBreakout(path, input.breakoutLevel, bias);
    if (breakout) {
      events.push(breakout);
      
      // Retest after breakout
      const retest = detectRetest(path, breakout, input.breakoutLevel);
      if (retest) events.push(retest);
    }
  }
  
  // Target
  if (input.target) {
    const targetHit = detectTargetHit(path, input.target, bias);
    if (targetHit) events.push(targetHit);
  }
  
  // Stop
  if (input.stop) {
    const stopHit = detectStopHit(path, input.stop, bias);
    if (stopHit) events.push(stopHit);
  }
  
  // Level touches
  if (levels.length > 0) {
    const levelEvents = detectLevelTouches(bands, levels);
    events.push(...levelEvents);
  }
  
  // Sort by bar offset
  events.sort((a, b) => a.barOffset - b.barOffset);
  
  return events;
}
