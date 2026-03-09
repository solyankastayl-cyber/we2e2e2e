/**
 * Phase 5.5 — Portfolio State Service
 * =====================================
 * Manages portfolio positions and state
 */

import { v4 as uuidv4 } from 'uuid';
import { Position, PortfolioState, PortfolioLimits } from './portfolio.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STATE (would be DB in production)
// ═══════════════════════════════════════════════════════════════

const positions: Map<string, Position> = new Map();

let portfolioValue = 100000;
let availableMargin = 100000;
let realizedPnl = 0;

// Default limits
export const PORTFOLIO_LIMITS: PortfolioLimits = {
  maxPositions: 10,
  maxLeverage: 5,
  maxDrawdown: 0.20,
  maxSingleAssetExposure: 0.30,
  maxSectorExposure: 0.50,
  maxCorrelatedExposure: 0.60,
};

// ═══════════════════════════════════════════════════════════════
// MOCK PRICES (would come from market data in production)
// ═══════════════════════════════════════════════════════════════

const currentPrices: Record<string, number> = {
  BTCUSDT: 52000,
  ETHUSDT: 2800,
  SOLUSDT: 120,
  BNBUSDT: 380,
  ADAUSDT: 0.58,
  DOGEUSDT: 0.12,
  AVAXUSDT: 38,
  DOTUSDT: 7.5,
  LINKUSDT: 15,
  MATICUSDT: 0.95,
};

function getPrice(symbol: string): number {
  return currentPrices[symbol] || 100;
}

// ═══════════════════════════════════════════════════════════════
// POSITION MANAGEMENT
// ═══════════════════════════════════════════════════════════════

/**
 * Open a new position
 */
export function openPosition(
  symbol: string,
  side: 'LONG' | 'SHORT',
  size: number,
  leverage: number,
  strategyId: string
): Position {
  const id = `pos_${uuidv4().slice(0, 8)}`;
  const entryPrice = getPrice(symbol);
  const marginUsed = (size * entryPrice) / leverage;
  
  const position: Position = {
    id,
    symbol,
    side,
    size,
    entryPrice,
    currentPrice: entryPrice,
    unrealizedPnl: 0,
    unrealizedPnlPct: 0,
    leverage,
    marginUsed,
    strategyId,
    openedAt: Date.now(),
  };
  
  positions.set(id, position);
  availableMargin -= marginUsed;
  
  return position;
}

/**
 * Close a position
 */
export function closePosition(positionId: string): { pnl: number } | null {
  const position = positions.get(positionId);
  if (!position) return null;
  
  // Calculate final PnL
  updatePositionPrice(positionId);
  const pnl = position.unrealizedPnl;
  
  // Update portfolio
  availableMargin += position.marginUsed;
  realizedPnl += pnl;
  portfolioValue += pnl;
  
  positions.delete(positionId);
  
  return { pnl };
}

/**
 * Update position with current price
 */
export function updatePositionPrice(positionId: string): void {
  const position = positions.get(positionId);
  if (!position) return;
  
  position.currentPrice = getPrice(position.symbol);
  
  const priceDiff = position.currentPrice - position.entryPrice;
  const direction = position.side === 'LONG' ? 1 : -1;
  
  position.unrealizedPnl = priceDiff * position.size * direction;
  position.unrealizedPnlPct = (priceDiff / position.entryPrice) * direction;
}

/**
 * Update all positions with current prices
 */
export function updateAllPositions(): void {
  for (const id of positions.keys()) {
    updatePositionPrice(id);
  }
}

/**
 * Get all positions
 */
export function getPositions(): Position[] {
  updateAllPositions();
  return [...positions.values()];
}

/**
 * Get position by ID
 */
export function getPosition(id: string): Position | undefined {
  updatePositionPrice(id);
  return positions.get(id);
}

/**
 * Get positions by symbol
 */
export function getPositionsBySymbol(symbol: string): Position[] {
  return getPositions().filter(p => p.symbol === symbol);
}

/**
 * Get positions by strategy
 */
export function getPositionsByStrategy(strategyId: string): Position[] {
  return getPositions().filter(p => p.strategyId === strategyId);
}

// ═══════════════════════════════════════════════════════════════
// PORTFOLIO STATE
// ═══════════════════════════════════════════════════════════════

/**
 * Get current portfolio state
 */
export function getPortfolioState(): PortfolioState {
  updateAllPositions();
  
  const positionList = [...positions.values()];
  const totalUnrealizedPnl = positionList.reduce((sum, p) => sum + p.unrealizedPnl, 0);
  const totalMarginUsed = positionList.reduce((sum, p) => sum + p.marginUsed, 0);
  
  return {
    totalValue: portfolioValue + totalUnrealizedPnl,
    availableMargin,
    usedMargin: totalMarginUsed,
    unrealizedPnl: totalUnrealizedPnl,
    realizedPnl,
    positions: positionList,
    positionCount: positionList.length,
    lastUpdated: Date.now(),
  };
}

/**
 * Set portfolio value (for simulation)
 */
export function setPortfolioValue(value: number): void {
  portfolioValue = value;
  availableMargin = value;
}

/**
 * Get portfolio limits
 */
export function getPortfolioLimits(): PortfolioLimits {
  return { ...PORTFOLIO_LIMITS };
}

/**
 * Update portfolio limits
 */
export function updatePortfolioLimits(updates: Partial<PortfolioLimits>): void {
  Object.assign(PORTFOLIO_LIMITS, updates);
}

// ═══════════════════════════════════════════════════════════════
// SEED DATA FOR TESTING
// ═══════════════════════════════════════════════════════════════

/**
 * Initialize with sample positions
 */
export function seedTestPositions(): void {
  // Clear existing
  positions.clear();
  availableMargin = portfolioValue;
  realizedPnl = 0;
  
  // Add sample positions
  openPosition('BTCUSDT', 'LONG', 0.5, 3, 'trend_breakout');
  openPosition('ETHUSDT', 'LONG', 5, 2, 'trend_breakout');
  openPosition('SOLUSDT', 'SHORT', 50, 2, 'mean_reversion');
  openPosition('BNBUSDT', 'LONG', 20, 2, 'momentum');
}

// Initialize with test data
seedTestPositions();
