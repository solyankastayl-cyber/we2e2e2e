/**
 * Phase 6 — Open Interest / Positioning Service
 * ===============================================
 * OI analysis and sentiment detection
 */

import { OpenInterestData, PositioningState, LiquidationLevel } from './indicators.types.js';

// ═══════════════════════════════════════════════════════════════
// MOCK OI DATA (would come from exchange APIs in production)
// ═══════════════════════════════════════════════════════════════

interface MockOIData {
  oi: number;
  oiChange24h: number;
  longRatio: number;
  fundingRate: number;
}

const mockOIBySymbol: Record<string, MockOIData> = {
  BTCUSDT: { oi: 15000000000, oiChange24h: 0.05, longRatio: 0.52, fundingRate: 0.0001 },
  ETHUSDT: { oi: 5000000000, oiChange24h: 0.03, longRatio: 0.55, fundingRate: 0.00015 },
  SOLUSDT: { oi: 800000000, oiChange24h: -0.02, longRatio: 0.48, fundingRate: 0.00008 },
  BNBUSDT: { oi: 400000000, oiChange24h: 0.01, longRatio: 0.51, fundingRate: 0.0001 },
};

// ═══════════════════════════════════════════════════════════════
// OI ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Get Open Interest data for a symbol
 */
export function getOpenInterestData(symbol: string, currentPrice: number): OpenInterestData {
  const mock = mockOIBySymbol[symbol] || {
    oi: 100000000,
    oiChange24h: 0,
    longRatio: 0.5,
    fundingRate: 0,
  };
  
  // Add some randomness for realistic simulation
  const oiVariation = 1 + (Math.random() - 0.5) * 0.1;
  const oi = mock.oi * oiVariation;
  const change24h = mock.oiChange24h + (Math.random() - 0.5) * 0.02;
  const longRatio = Math.max(0.3, Math.min(0.7, mock.longRatio + (Math.random() - 0.5) * 0.1));
  const fundingRate = mock.fundingRate + (Math.random() - 0.5) * 0.0001;
  
  // Determine funding trend
  let fundingTrend: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
  if (fundingRate > 0.0001) fundingTrend = 'POSITIVE';
  else if (fundingRate < -0.0001) fundingTrend = 'NEGATIVE';
  else fundingTrend = 'NEUTRAL';
  
  // Generate liquidation levels
  const liquidationLevels = generateLiquidationLevels(currentPrice, longRatio);
  
  return {
    current: Math.round(oi),
    change24h: Math.round(oi * change24h),
    changePct24h: Math.round(change24h * 10000) / 10000,
    longRatio: Math.round(longRatio * 100) / 100,
    shortRatio: Math.round((1 - longRatio) * 100) / 100,
    fundingRate: Math.round(fundingRate * 10000) / 10000,
    fundingTrend,
    liquidationLevels,
  };
}

/**
 * Generate estimated liquidation levels
 */
function generateLiquidationLevels(currentPrice: number, longRatio: number): LiquidationLevel[] {
  const levels: LiquidationLevel[] = [];
  
  // Long liquidations (below current price)
  const leverages = [5, 10, 20, 50, 100];
  for (const lev of leverages) {
    const liqPrice = currentPrice * (1 - 1/lev);
    const volume = (1000000 / lev) * longRatio * (0.8 + Math.random() * 0.4);
    
    levels.push({
      price: Math.round(liqPrice * 100) / 100,
      side: 'LONG',
      volume: Math.round(volume),
      leverage: lev,
    });
  }
  
  // Short liquidations (above current price)
  for (const lev of leverages) {
    const liqPrice = currentPrice * (1 + 1/lev);
    const volume = (1000000 / lev) * (1 - longRatio) * (0.8 + Math.random() * 0.4);
    
    levels.push({
      price: Math.round(liqPrice * 100) / 100,
      side: 'SHORT',
      volume: Math.round(volume),
      leverage: lev,
    });
  }
  
  // Sort by distance from current price
  levels.sort((a, b) => Math.abs(a.price - currentPrice) - Math.abs(b.price - currentPrice));
  
  return levels;
}

// ═══════════════════════════════════════════════════════════════
// POSITIONING STATE
// ═══════════════════════════════════════════════════════════════

/**
 * Analyze positioning state
 */
export function analyzePositioning(symbol: string, currentPrice: number): PositioningState {
  const oi = getOpenInterestData(symbol, currentPrice);
  
  // Determine sentiment from long/short ratio and funding
  let sentiment: PositioningState['sentiment'];
  const netLong = oi.longRatio - 0.5;  // Deviation from neutral
  
  if (netLong > 0.15) sentiment = 'EXTREMELY_BULLISH';
  else if (netLong > 0.05) sentiment = 'BULLISH';
  else if (netLong < -0.15) sentiment = 'EXTREMELY_BEARISH';
  else if (netLong < -0.05) sentiment = 'BEARISH';
  else sentiment = 'NEUTRAL';
  
  // Determine crowded side
  let crowdedSide: 'LONG' | 'SHORT' | 'BALANCED';
  if (oi.longRatio > 0.58) crowdedSide = 'LONG';
  else if (oi.longRatio < 0.42) crowdedSide = 'SHORT';
  else crowdedSide = 'BALANCED';
  
  // Contrarian signal when one side is very crowded
  const contrarian = oi.longRatio > 0.65 || oi.longRatio < 0.35;
  
  // Find next major liquidation zone
  const longLiqs = oi.liquidationLevels.filter(l => l.side === 'LONG' && l.volume > 100000);
  const shortLiqs = oi.liquidationLevels.filter(l => l.side === 'SHORT' && l.volume > 100000);
  
  let nextLiquidationZone: PositioningState['nextLiquidationZone'] = null;
  
  // Find closest significant liquidation
  const closestLong = longLiqs[0];
  const closestShort = shortLiqs[0];
  
  if (closestLong && closestShort) {
    const distToLong = Math.abs(currentPrice - closestLong.price);
    const distToShort = Math.abs(currentPrice - closestShort.price);
    
    const closest = distToLong < distToShort ? closestLong : closestShort;
    nextLiquidationZone = {
      price: closest.price,
      side: closest.side,
      distance: Math.round(Math.abs(currentPrice - closest.price) / currentPrice * 10000) / 10000,
    };
  }
  
  return {
    oi,
    sentiment,
    crowdedSide,
    contrarian,
    nextLiquidationZone,
  };
}

/**
 * Calculate positioning boost for decision engine
 */
export function getPositioningBoost(positioning: PositioningState, side: 'LONG' | 'SHORT'): number {
  let boost = 1.0;
  
  // Contrarian adjustment
  if (positioning.contrarian) {
    // If crowd is long and we're going short, boost
    if (positioning.crowdedSide === 'LONG' && side === 'SHORT') {
      boost *= 1.15;
    }
    // If crowd is short and we're going long, boost
    else if (positioning.crowdedSide === 'SHORT' && side === 'LONG') {
      boost *= 1.15;
    }
    // Going with the crowd when very crowded = risky
    else {
      boost *= 0.85;
    }
  }
  
  // Funding rate adjustment
  if (positioning.oi.fundingTrend === 'POSITIVE' && side === 'SHORT') {
    boost *= 1.05; // Shorts getting paid
  } else if (positioning.oi.fundingTrend === 'NEGATIVE' && side === 'LONG') {
    boost *= 1.05; // Longs getting paid
  }
  
  // Liquidation proximity boost
  if (positioning.nextLiquidationZone && positioning.nextLiquidationZone.distance < 0.05) {
    // Close to liquidation zone
    if (positioning.nextLiquidationZone.side !== side) {
      // We're positioned to benefit from liquidations
      boost *= 1.1;
    }
  }
  
  return Math.round(Math.max(0.7, Math.min(1.3, boost)) * 100) / 100;
}
