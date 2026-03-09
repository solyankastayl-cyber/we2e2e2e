/**
 * Phase 5.5 — Portfolio Exposure Service
 * ========================================
 * Calculates net/gross exposure by asset and sector
 */

import { AssetExposure, SectorExposure, ExposureState } from './portfolio.types.js';
import { getPositions, getPortfolioState } from './portfolio.state.js';

// ═══════════════════════════════════════════════════════════════
// SECTOR MAPPING
// ═══════════════════════════════════════════════════════════════

const SECTOR_MAP: Record<string, string> = {
  // Major
  BTCUSDT: 'MAJOR',
  ETHUSDT: 'MAJOR',
  
  // L1s
  SOLUSDT: 'L1',
  AVAXUSDT: 'L1',
  DOTUSDT: 'L1',
  ADAUSDT: 'L1',
  NEARUSDT: 'L1',
  ATOMUSDT: 'L1',
  
  // DeFi
  UNIUSDT: 'DEFI',
  AAVEUSDT: 'DEFI',
  LINKUSDT: 'DEFI',
  MKRUSDT: 'DEFI',
  CRVUSDT: 'DEFI',
  
  // L2
  MATICUSDT: 'L2',
  OPUSDT: 'L2',
  ARBUSDT: 'L2',
  
  // Exchange
  BNBUSDT: 'EXCHANGE',
  FTMUSDT: 'EXCHANGE',
  
  // Meme
  DOGEUSDT: 'MEME',
  SHIBUSDT: 'MEME',
  PEPEUSDT: 'MEME',
};

function getSector(symbol: string): string {
  return SECTOR_MAP[symbol] || 'OTHER';
}

// ═══════════════════════════════════════════════════════════════
// EXPOSURE CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate exposure by asset
 */
export function calculateAssetExposure(): AssetExposure[] {
  const positions = getPositions();
  const state = getPortfolioState();
  
  // Group by symbol
  const bySymbol: Map<string, { net: number; gross: number; count: number }> = new Map();
  
  for (const pos of positions) {
    const current = bySymbol.get(pos.symbol) || { net: 0, gross: 0, count: 0 };
    
    const exposure = pos.size * pos.currentPrice;
    const direction = pos.side === 'LONG' ? 1 : -1;
    
    current.net += exposure * direction;
    current.gross += exposure;
    current.count += 1;
    
    bySymbol.set(pos.symbol, current);
  }
  
  // Convert to array
  const exposures: AssetExposure[] = [];
  
  for (const [symbol, data] of bySymbol) {
    exposures.push({
      symbol,
      netExposure: Math.round(data.net * 100) / 100,
      grossExposure: Math.round(data.gross * 100) / 100,
      weight: state.totalValue > 0 
        ? Math.round((data.gross / state.totalValue) * 10000) / 10000
        : 0,
      positions: data.count,
    });
  }
  
  // Sort by gross exposure
  exposures.sort((a, b) => b.grossExposure - a.grossExposure);
  
  return exposures;
}

/**
 * Calculate exposure by sector
 */
export function calculateSectorExposure(): SectorExposure[] {
  const assetExposures = calculateAssetExposure();
  const state = getPortfolioState();
  
  // Group by sector
  const bySector: Map<string, { net: number; assets: string[] }> = new Map();
  
  for (const asset of assetExposures) {
    const sector = getSector(asset.symbol);
    const current = bySector.get(sector) || { net: 0, assets: [] };
    
    current.net += asset.netExposure;
    current.assets.push(asset.symbol);
    
    bySector.set(sector, current);
  }
  
  // Convert to array
  const exposures: SectorExposure[] = [];
  
  for (const [sector, data] of bySector) {
    exposures.push({
      sector,
      netExposure: Math.round(data.net * 100) / 100,
      weight: state.totalValue > 0
        ? Math.round((Math.abs(data.net) / state.totalValue) * 10000) / 10000
        : 0,
      assets: data.assets,
    });
  }
  
  // Sort by absolute exposure
  exposures.sort((a, b) => Math.abs(b.netExposure) - Math.abs(a.netExposure));
  
  return exposures;
}

/**
 * Get full exposure state
 */
export function getExposureState(): ExposureState {
  const positions = getPositions();
  const state = getPortfolioState();
  
  let totalGross = 0;
  let totalNet = 0;
  
  for (const pos of positions) {
    const exposure = pos.size * pos.currentPrice;
    const direction = pos.side === 'LONG' ? 1 : -1;
    
    totalGross += exposure;
    totalNet += exposure * direction;
  }
  
  const leverageRatio = state.totalValue > 0 ? totalGross / state.totalValue : 0;
  
  let direction: 'LONG_BIASED' | 'SHORT_BIASED' | 'NEUTRAL';
  if (totalNet > totalGross * 0.1) {
    direction = 'LONG_BIASED';
  } else if (totalNet < -totalGross * 0.1) {
    direction = 'SHORT_BIASED';
  } else {
    direction = 'NEUTRAL';
  }
  
  return {
    totalGrossExposure: Math.round(totalGross * 100) / 100,
    totalNetExposure: Math.round(totalNet * 100) / 100,
    leverageRatio: Math.round(leverageRatio * 100) / 100,
    byAsset: calculateAssetExposure(),
    bySector: calculateSectorExposure(),
    direction,
    lastUpdated: Date.now(),
  };
}

/**
 * Check if adding position would exceed exposure limits
 */
export function checkExposureLimit(
  symbol: string,
  size: number,
  side: 'LONG' | 'SHORT',
  price: number,
  maxSingleAsset: number = 0.30
): { allowed: boolean; currentWeight: number; newWeight: number } {
  const state = getPortfolioState();
  const assetExposures = calculateAssetExposure();
  
  const existing = assetExposures.find(a => a.symbol === symbol);
  const currentExposure = existing?.grossExposure || 0;
  const newExposure = size * price;
  const totalExposure = currentExposure + newExposure;
  
  const currentWeight = existing?.weight || 0;
  const newWeight = state.totalValue > 0 ? totalExposure / state.totalValue : 0;
  
  return {
    allowed: newWeight <= maxSingleAsset,
    currentWeight: Math.round(currentWeight * 10000) / 10000,
    newWeight: Math.round(newWeight * 10000) / 10000,
  };
}
