/**
 * Phase 10 — Portfolio Management Engine
 * 
 * Portfolio tracking and management
 */

import { v4 as uuidv4 } from 'uuid';
import {
  Portfolio,
  PortfolioPosition,
  StrategyAllocation,
  AllocationPlan,
  RiskLimits,
  DEFAULT_RISK_LIMITS
} from './execution.types.js';

// ═══════════════════════════════════════════════════════════════
// PORTFOLIO OPERATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Create empty portfolio
 */
export function createPortfolio(accountSize: number): Portfolio {
  return {
    portfolioId: `PF_${uuidv4().slice(0, 8)}`,
    accountSize,
    positions: [],
    totalRisk: 0,
    totalExposure: 0,
    unrealizedPnL: 0,
    realizedPnL: 0,
    winCount: 0,
    lossCount: 0,
    updatedAt: new Date()
  };
}

/**
 * Add position to portfolio
 */
export function addPosition(
  portfolio: Portfolio,
  position: Omit<PortfolioPosition, 'positionId' | 'unrealizedR' | 'unrealizedPnL' | 'barsInTrade'>
): Portfolio {
  const newPosition: PortfolioPosition = {
    ...position,
    positionId: `POS_${uuidv4().slice(0, 8)}`,
    unrealizedR: 0,
    unrealizedPnL: 0,
    barsInTrade: 0
  };
  
  return {
    ...portfolio,
    positions: [...portfolio.positions, newPosition],
    totalRisk: portfolio.totalRisk + position.riskPct,
    totalExposure: portfolio.totalExposure + (position.positionSize * position.entryPrice / portfolio.accountSize * 100),
    updatedAt: new Date()
  };
}

/**
 * Update position prices
 */
export function updatePositionPrices(
  portfolio: Portfolio,
  prices: Record<string, number>
): Portfolio {
  const updatedPositions = portfolio.positions.map(pos => {
    const currentPrice = prices[pos.asset] || pos.currentPrice;
    const priceDiff = pos.direction === 'LONG'
      ? currentPrice - pos.entryPrice
      : pos.entryPrice - currentPrice;
    
    const riskDistance = Math.abs(pos.entryPrice - pos.stopPrice);
    const unrealizedR = riskDistance > 0 ? priceDiff / riskDistance : 0;
    const unrealizedPnL = priceDiff * pos.positionSize;
    
    return {
      ...pos,
      currentPrice,
      unrealizedR,
      unrealizedPnL
    };
  });
  
  const totalUnrealizedPnL = updatedPositions.reduce((sum, p) => sum + p.unrealizedPnL, 0);
  
  return {
    ...portfolio,
    positions: updatedPositions,
    unrealizedPnL: totalUnrealizedPnL,
    updatedAt: new Date()
  };
}

/**
 * Close position
 */
export function closePosition(
  portfolio: Portfolio,
  positionId: string,
  exitPrice: number
): Portfolio {
  const position = portfolio.positions.find(p => p.positionId === positionId);
  if (!position) return portfolio;
  
  const priceDiff = position.direction === 'LONG'
    ? exitPrice - position.entryPrice
    : position.entryPrice - exitPrice;
  
  const realizedPnL = priceDiff * position.positionSize;
  const isWin = realizedPnL > 0;
  
  const remainingPositions = portfolio.positions.filter(p => p.positionId !== positionId);
  const totalRisk = remainingPositions.reduce((sum, p) => sum + p.riskPct, 0);
  const totalExposure = remainingPositions.reduce(
    (sum, p) => sum + (p.positionSize * p.currentPrice / portfolio.accountSize * 100),
    0
  );
  
  return {
    ...portfolio,
    positions: remainingPositions,
    totalRisk,
    totalExposure,
    realizedPnL: portfolio.realizedPnL + realizedPnL,
    winCount: portfolio.winCount + (isWin ? 1 : 0),
    lossCount: portfolio.lossCount + (isWin ? 0 : 1),
    updatedAt: new Date()
  };
}

// ═══════════════════════════════════════════════════════════════
// ALLOCATION ENGINE
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate strategy allocations based on performance
 */
export function calculateAllocations(
  strategies: Array<{
    strategyId: string;
    strategyScore: number;
    profitFactor: number;
    trades: number;
    activePositions?: number;
  }>,
  totalCapital: number,
  maxSingleStrategy: number = 30
): AllocationPlan {
  if (strategies.length === 0) {
    return {
      totalCapital,
      allocations: [],
      reserveCash: 10,
      maxSingleStrategy
    };
  }
  
  // Filter strategies with minimum criteria
  const validStrategies = strategies.filter(s => 
    s.trades >= 30 && 
    s.profitFactor >= 1.1 && 
    s.strategyScore > 0
  );
  
  if (validStrategies.length === 0) {
    return {
      totalCapital,
      allocations: [],
      reserveCash: 10,
      maxSingleStrategy
    };
  }
  
  // Calculate total score
  const totalScore = validStrategies.reduce((sum, s) => sum + s.strategyScore, 0);
  
  // Allocate proportionally to score
  const allocations: StrategyAllocation[] = validStrategies.map(s => {
    let allocationPct = (s.strategyScore / totalScore) * (100 - 10);  // 10% reserve
    
    // Cap at max single strategy
    allocationPct = Math.min(allocationPct, maxSingleStrategy);
    
    return {
      strategyId: s.strategyId,
      allocationPct: Math.round(allocationPct * 100) / 100,
      strategyScore: s.strategyScore,
      profitFactor: s.profitFactor,
      trades: s.trades,
      activePositions: s.activePositions || 0,
      currentExposure: 0
    };
  });
  
  // Normalize if total exceeds 90% (after reserve)
  const totalAllocated = allocations.reduce((sum, a) => sum + a.allocationPct, 0);
  if (totalAllocated > 90) {
    const scaleFactor = 90 / totalAllocated;
    for (const a of allocations) {
      a.allocationPct = Math.round(a.allocationPct * scaleFactor * 100) / 100;
    }
  }
  
  return {
    totalCapital,
    allocations,
    reserveCash: 10,
    maxSingleStrategy
  };
}

/**
 * Get available allocation for strategy
 */
export function getAvailableAllocation(
  allocationPlan: AllocationPlan,
  strategyId: string,
  currentExposure: number
): number {
  const allocation = allocationPlan.allocations.find(a => a.strategyId === strategyId);
  if (!allocation) return 0;
  
  return Math.max(0, allocation.allocationPct - currentExposure);
}

// ═══════════════════════════════════════════════════════════════
// PORTFOLIO STATISTICS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate portfolio statistics
 */
export function calculatePortfolioStats(portfolio: Portfolio): {
  totalTrades: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  currentEquity: number;
  openPositions: number;
  longExposure: number;
  shortExposure: number;
} {
  const totalTrades = portfolio.winCount + portfolio.lossCount;
  const winRate = totalTrades > 0 ? portfolio.winCount / totalTrades : 0;
  
  // Calculate exposure by direction
  let longExposure = 0;
  let shortExposure = 0;
  
  for (const pos of portfolio.positions) {
    const exposure = (pos.positionSize * pos.currentPrice / portfolio.accountSize) * 100;
    if (pos.direction === 'LONG') {
      longExposure += exposure;
    } else {
      shortExposure += exposure;
    }
  }
  
  return {
    totalTrades,
    winRate: Math.round(winRate * 100) / 100,
    avgWin: 0,  // Would need trade history
    avgLoss: 0,
    profitFactor: 0,  // Would need trade history
    currentEquity: portfolio.accountSize + portfolio.realizedPnL + portfolio.unrealizedPnL,
    openPositions: portfolio.positions.length,
    longExposure: Math.round(longExposure * 100) / 100,
    shortExposure: Math.round(shortExposure * 100) / 100
  };
}

/**
 * Get positions by strategy
 */
export function getPositionsByStrategy(
  portfolio: Portfolio
): Record<string, PortfolioPosition[]> {
  const grouped: Record<string, PortfolioPosition[]> = {};
  
  for (const pos of portfolio.positions) {
    if (!grouped[pos.strategyId]) {
      grouped[pos.strategyId] = [];
    }
    grouped[pos.strategyId].push(pos);
  }
  
  return grouped;
}
