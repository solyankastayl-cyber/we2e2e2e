/**
 * System Dashboard — Types
 * 
 * Observability dashboard for AI Market Intelligence Platform
 */

import { AnalysisMode, MetaBrainRiskMode } from '../metabrain_v3/metabrain_v3.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { AnalysisModule } from '../metabrain_learning/module_attribution.types.js';

// ═══════════════════════════════════════════════════════════════
// DASHBOARD DATA TYPES
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainStatus {
  analysisMode: AnalysisMode;
  riskMode: MetaBrainRiskMode;
  safeMode: boolean;
  safeModeReason?: string;
  
  // Risk metrics
  edgeHealth: number;
  drawdownPct: number;
  portfolioRiskPct: number;
  
  // Memory metrics
  memoryConfidence: number;
  memoryMatches: number;
  memoryBias: 'BULL' | 'BEAR' | 'NEUTRAL';
  
  // Tree metrics
  treeUncertainty: number;
  treeRisk: number;
  treeDominance: number;
  
  // Execution
  riskMultiplier: number;
  maxRiskPerTrade: number;
  confidenceThreshold: number;
  
  lastUpdated: Date;
}

export interface ModuleHealth {
  module: AnalysisModule;
  status: 'ACTIVE' | 'SOFT_GATED' | 'HARD_GATED';
  weight: number;
  regimeWeight: number;
  confidence: number;
  lastContribution: number;
  gatedReason?: string;
}

export interface RegimeInfo {
  current: MarketRegime;
  confidence: number;
  probabilities: Record<MarketRegime, number>;
  transitionFrom?: MarketRegime;
  transitionAt?: Date;
}

export interface TreeVisualization {
  mainBranch: string;
  branches: TreeBranchNode[];
  stats: {
    totalBranches: number;
    maxDepth: number;
    dominanceScore: number;
    uncertaintyScore: number;
  };
}

export interface TreeBranchNode {
  id: string;
  name: string;
  probability: number;
  depth: number;
  parentId?: string;
  children: string[];
  outcome?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
}

export interface MemoryStatus {
  totalSnapshots: number;
  recentMatches: number;
  avgConfidence: number;
  dominantBias: 'BULL' | 'BEAR' | 'NEUTRAL';
  biasStrength: number;
  topPatterns: { pattern: string; frequency: number }[];
}

export interface StrategyPanel {
  enabled: {
    strategy: string;
    active: boolean;
    multiplier: number;
  }[];
  disabled: string[];
  regime: MarketRegime;
}

export interface SystemMetrics {
  uptime: number;
  apiRequests: {
    lastMinute: number;
    lastHour: number;
    avgLatencyMs: number;
  };
  wsConnections: number;
  dbOperations: {
    lastMinute: number;
    avgLatencyMs: number;
  };
  errors: {
    lastHour: number;
    lastDay: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// FULL DASHBOARD
// ═══════════════════════════════════════════════════════════════

export interface DashboardData {
  metabrain: MetaBrainStatus;
  modules: ModuleHealth[];
  regime: RegimeInfo;
  tree: TreeVisualization;
  memory: MemoryStatus;
  strategies: StrategyPanel;
  system: SystemMetrics;
  
  asset: string;
  timeframe: string;
  generatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// ALERTS
// ═══════════════════════════════════════════════════════════════

export interface DashboardAlert {
  id: string;
  type: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';
  category: 'METABRAIN' | 'MODULE' | 'MEMORY' | 'TREE' | 'SYSTEM';
  message: string;
  details?: string;
  timestamp: Date;
  acknowledged: boolean;
}

// ═══════════════════════════════════════════════════════════════
// HISTORICAL
// ═══════════════════════════════════════════════════════════════

export interface DashboardHistoryPoint {
  timestamp: Date;
  metabrainRiskMode: MetaBrainRiskMode;
  analysisMode: AnalysisMode;
  edgeHealth: number;
  memoryConfidence: number;
  treeUncertainty: number;
  gatedModulesCount: number;
}
