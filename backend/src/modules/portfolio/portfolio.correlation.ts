/**
 * Phase 5.5 — Portfolio Correlation Service
 * ===========================================
 * Calculates correlation matrix and diversification metrics
 */

import { CorrelationMatrix, CorrelationPair } from './portfolio.types.js';
import { getPositions } from './portfolio.state.js';

// ═══════════════════════════════════════════════════════════════
// CORRELATION DATA (would come from historical price analysis)
// ═══════════════════════════════════════════════════════════════

// Pre-computed correlation matrix for major crypto assets (30d)
const CORRELATION_30D: Record<string, Record<string, number>> = {
  BTCUSDT: {
    BTCUSDT: 1.00, ETHUSDT: 0.85, SOLUSDT: 0.78, BNBUSDT: 0.72,
    ADAUSDT: 0.68, DOGEUSDT: 0.55, AVAXUSDT: 0.75, DOTUSDT: 0.70,
    LINKUSDT: 0.65, MATICUSDT: 0.72,
  },
  ETHUSDT: {
    BTCUSDT: 0.85, ETHUSDT: 1.00, SOLUSDT: 0.82, BNBUSDT: 0.75,
    ADAUSDT: 0.72, DOGEUSDT: 0.48, AVAXUSDT: 0.80, DOTUSDT: 0.74,
    LINKUSDT: 0.78, MATICUSDT: 0.80,
  },
  SOLUSDT: {
    BTCUSDT: 0.78, ETHUSDT: 0.82, SOLUSDT: 1.00, BNBUSDT: 0.68,
    ADAUSDT: 0.65, DOGEUSDT: 0.42, AVAXUSDT: 0.72, DOTUSDT: 0.68,
    LINKUSDT: 0.60, MATICUSDT: 0.65,
  },
  BNBUSDT: {
    BTCUSDT: 0.72, ETHUSDT: 0.75, SOLUSDT: 0.68, BNBUSDT: 1.00,
    ADAUSDT: 0.58, DOGEUSDT: 0.45, AVAXUSDT: 0.62, DOTUSDT: 0.55,
    LINKUSDT: 0.52, MATICUSDT: 0.58,
  },
  ADAUSDT: {
    BTCUSDT: 0.68, ETHUSDT: 0.72, SOLUSDT: 0.65, BNBUSDT: 0.58,
    ADAUSDT: 1.00, DOGEUSDT: 0.52, AVAXUSDT: 0.60, DOTUSDT: 0.75,
    LINKUSDT: 0.55, MATICUSDT: 0.62,
  },
  DOGEUSDT: {
    BTCUSDT: 0.55, ETHUSDT: 0.48, SOLUSDT: 0.42, BNBUSDT: 0.45,
    ADAUSDT: 0.52, DOGEUSDT: 1.00, AVAXUSDT: 0.38, DOTUSDT: 0.40,
    LINKUSDT: 0.35, MATICUSDT: 0.42,
  },
  AVAXUSDT: {
    BTCUSDT: 0.75, ETHUSDT: 0.80, SOLUSDT: 0.72, BNBUSDT: 0.62,
    ADAUSDT: 0.60, DOGEUSDT: 0.38, AVAXUSDT: 1.00, DOTUSDT: 0.65,
    LINKUSDT: 0.58, MATICUSDT: 0.68,
  },
  DOTUSDT: {
    BTCUSDT: 0.70, ETHUSDT: 0.74, SOLUSDT: 0.68, BNBUSDT: 0.55,
    ADAUSDT: 0.75, DOGEUSDT: 0.40, AVAXUSDT: 0.65, DOTUSDT: 1.00,
    LINKUSDT: 0.60, MATICUSDT: 0.65,
  },
  LINKUSDT: {
    BTCUSDT: 0.65, ETHUSDT: 0.78, SOLUSDT: 0.60, BNBUSDT: 0.52,
    ADAUSDT: 0.55, DOGEUSDT: 0.35, AVAXUSDT: 0.58, DOTUSDT: 0.60,
    LINKUSDT: 1.00, MATICUSDT: 0.72,
  },
  MATICUSDT: {
    BTCUSDT: 0.72, ETHUSDT: 0.80, SOLUSDT: 0.65, BNBUSDT: 0.58,
    ADAUSDT: 0.62, DOGEUSDT: 0.42, AVAXUSDT: 0.68, DOTUSDT: 0.65,
    LINKUSDT: 0.72, MATICUSDT: 1.00,
  },
};

/**
 * Get correlation between two assets
 */
export function getCorrelation(asset1: string, asset2: string): number {
  if (asset1 === asset2) return 1.0;
  
  const row = CORRELATION_30D[asset1];
  if (row && row[asset2] !== undefined) {
    return row[asset2];
  }
  
  // Check reverse
  const reverseRow = CORRELATION_30D[asset2];
  if (reverseRow && reverseRow[asset1] !== undefined) {
    return reverseRow[asset1];
  }
  
  // Default to moderate correlation for unknown pairs
  return 0.5;
}

/**
 * Build correlation matrix for portfolio assets
 */
export function buildCorrelationMatrix(period: string = '30d'): CorrelationMatrix {
  const positions = getPositions();
  
  // Get unique symbols
  const symbols = [...new Set(positions.map(p => p.symbol))];
  
  if (symbols.length === 0) {
    return {
      assets: [],
      matrix: [],
      period,
      highCorrelations: [],
      negativeCorrelations: [],
      portfolioCorrelation: 0,
      diversificationScore: 1,
      lastUpdated: Date.now(),
    };
  }
  
  // Build NxN matrix
  const matrix: number[][] = [];
  const pairs: CorrelationPair[] = [];
  
  for (let i = 0; i < symbols.length; i++) {
    matrix[i] = [];
    for (let j = 0; j < symbols.length; j++) {
      const corr = getCorrelation(symbols[i], symbols[j]);
      matrix[i][j] = Math.round(corr * 100) / 100;
      
      // Track pairs (avoid duplicates)
      if (i < j) {
        pairs.push({
          asset1: symbols[i],
          asset2: symbols[j],
          correlation: corr,
          period,
        });
      }
    }
  }
  
  // Find high correlations (> 0.7)
  const highCorrelations = pairs
    .filter(p => p.correlation > 0.7)
    .sort((a, b) => b.correlation - a.correlation);
  
  // Find negative correlations (< -0.3)
  const negativeCorrelations = pairs
    .filter(p => p.correlation < -0.3)
    .sort((a, b) => a.correlation - b.correlation);
  
  // Calculate average correlation
  const avgCorr = pairs.length > 0
    ? pairs.reduce((sum, p) => sum + p.correlation, 0) / pairs.length
    : 0;
  
  // Diversification score: lower correlation = higher diversification
  // 0 = perfectly correlated, 1 = perfectly uncorrelated
  const diversificationScore = Math.max(0, 1 - avgCorr);
  
  return {
    assets: symbols,
    matrix,
    period,
    highCorrelations,
    negativeCorrelations,
    portfolioCorrelation: Math.round(avgCorr * 100) / 100,
    diversificationScore: Math.round(diversificationScore * 100) / 100,
    lastUpdated: Date.now(),
  };
}

/**
 * Check if portfolio is over-concentrated in correlated assets
 */
export function checkCorrelationRisk(maxCorrelatedExposure: number = 0.6): {
  atRisk: boolean;
  correlatedPairs: { pair: CorrelationPair; combinedWeight: number }[];
} {
  const positions = getPositions();
  const totalValue = positions.reduce((sum, p) => sum + p.size * p.currentPrice, 0);
  
  if (totalValue === 0) {
    return { atRisk: false, correlatedPairs: [] };
  }
  
  // Calculate exposure by symbol
  const exposures: Record<string, number> = {};
  for (const pos of positions) {
    const exposure = pos.size * pos.currentPrice;
    exposures[pos.symbol] = (exposures[pos.symbol] || 0) + exposure;
  }
  
  // Find highly correlated pairs with significant exposure
  const correlatedPairs: { pair: CorrelationPair; combinedWeight: number }[] = [];
  const symbols = Object.keys(exposures);
  
  for (let i = 0; i < symbols.length; i++) {
    for (let j = i + 1; j < symbols.length; j++) {
      const corr = getCorrelation(symbols[i], symbols[j]);
      
      if (corr > 0.7) {
        const weight1 = exposures[symbols[i]] / totalValue;
        const weight2 = exposures[symbols[j]] / totalValue;
        const combinedWeight = weight1 + weight2;
        
        if (combinedWeight > maxCorrelatedExposure) {
          correlatedPairs.push({
            pair: {
              asset1: symbols[i],
              asset2: symbols[j],
              correlation: corr,
              period: '30d',
            },
            combinedWeight: Math.round(combinedWeight * 100) / 100,
          });
        }
      }
    }
  }
  
  return {
    atRisk: correlatedPairs.length > 0,
    correlatedPairs,
  };
}
