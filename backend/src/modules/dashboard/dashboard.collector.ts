/**
 * System Dashboard — Data Collector
 * 
 * Collects data from all engines for dashboard visualization
 */

import {
  DashboardData,
  MetaBrainStatus,
  ModuleHealth,
  RegimeInfo,
  TreeVisualization,
  MemoryStatus,
  StrategyPanel,
  SystemMetrics,
  TreeBranchNode,
  DashboardAlert
} from './dashboard.types.js';
import { ALL_MODULES, AnalysisModule } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { ALL_REGIMES } from '../metabrain_regime/regime.learning.types.js';

// ═══════════════════════════════════════════════════════════════
// DATA FETCHERS
// ═══════════════════════════════════════════════════════════════

async function fetchMetaBrainStatus(asset: string, tf: string): Promise<MetaBrainStatus> {
  try {
    const resp = await fetch(`http://localhost:8001/api/ta/metabrain/v3/state?asset=${asset}&tf=${tf}`);
    const data = await resp.json() as { data?: any };
    
    const ctx = data.data?.context ?? {};
    const dec = data.data?.decision ?? {};
    
    return {
      analysisMode: dec.analysisMode ?? 'CLASSIC_TA',
      riskMode: dec.riskMode ?? 'NORMAL',
      safeMode: dec.safeMode ?? false,
      safeModeReason: dec.safeMode ? dec.reasons?.join(', ') : undefined,
      
      edgeHealth: ctx.edgeHealth ?? 0.5,
      drawdownPct: ctx.drawdownPct ?? 0,
      portfolioRiskPct: ctx.portfolioRiskPct ?? 0,
      
      memoryConfidence: ctx.memoryConfidence ?? 0,
      memoryMatches: ctx.memoryMatches ?? 0,
      memoryBias: ctx.memoryBias ?? 'NEUTRAL',
      
      treeUncertainty: ctx.treeUncertainty ?? 0.5,
      treeRisk: ctx.treeRisk ?? 0.3,
      treeDominance: 1 - (ctx.treeUncertainty ?? 0.5),
      
      riskMultiplier: dec.executionPolicy?.riskMultiplier ?? 1.0,
      maxRiskPerTrade: dec.executionPolicy?.maxRiskPerTrade ?? 0.01,
      confidenceThreshold: dec.confidencePolicy?.minSignalConfidence ?? 0.55,
      
      lastUpdated: new Date(data.data?.createdAt ?? Date.now())
    };
  } catch {
    return getDefaultMetaBrainStatus();
  }
}

async function fetchModuleHealth(): Promise<ModuleHealth[]> {
  try {
    const resp = await fetch('http://localhost:8001/api/ta/metabrain/learning/gates');
    const data = await resp.json() as { data?: any };
    
    const gates = data.data?.gates ?? [];
    
    return ALL_MODULES.map(module => {
      const gate = gates.find((g: any) => g.module === module);
      return {
        module,
        status: gate?.status ?? 'ACTIVE',
        weight: gate?.weight ?? 1.0,
        regimeWeight: 1.0,
        confidence: gate?.confidence ?? 0,
        lastContribution: gate?.avgOutcomeImpact ?? 0,
        gatedReason: gate?.status !== 'ACTIVE' ? gate?.reason : undefined
      };
    });
  } catch {
    return ALL_MODULES.map(module => ({
      module,
      status: 'ACTIVE' as const,
      weight: 1.0,
      regimeWeight: 1.0,
      confidence: 0,
      lastContribution: 0
    }));
  }
}

async function fetchRegimeInfo(asset: string, tf: string): Promise<RegimeInfo> {
  try {
    // Get current regime from MetaBrain
    const resp = await fetch(`http://localhost:8001/api/ta/metabrain/v3/state?asset=${asset}&tf=${tf}`);
    const data = await resp.json() as { data?: any };
    
    const regime = data.data?.context?.regime ?? 'COMPRESSION';
    
    // Build probability map (simplified)
    const probabilities: Record<MarketRegime, number> = {} as Record<MarketRegime, number>;
    for (const r of ALL_REGIMES) {
      probabilities[r] = r === regime ? 0.7 : 0.3 / (ALL_REGIMES.length - 1);
    }
    
    return {
      current: regime,
      confidence: 0.7,
      probabilities
    };
  } catch {
    const probabilities: Record<MarketRegime, number> = {} as Record<MarketRegime, number>;
    for (const r of ALL_REGIMES) {
      probabilities[r] = 1 / ALL_REGIMES.length;
    }
    return {
      current: 'COMPRESSION',
      confidence: 0.5,
      probabilities
    };
  }
}

async function fetchTreeVisualization(asset: string, tf: string): Promise<TreeVisualization> {
  try {
    const resp = await fetch(`http://localhost:8001/api/ta/twin/tree/scoring?asset=${asset}&tf=${tf}`);
    const data = await resp.json() as { data?: any };
    
    const stats = data.data?.treeStats ?? {};
    
    // Build simple tree structure
    const branches: TreeBranchNode[] = [
      {
        id: 'root',
        name: 'CURRENT',
        probability: 1.0,
        depth: 0,
        children: ['main', 'alt1']
      },
      {
        id: 'main',
        name: 'MAIN_BRANCH',
        probability: stats.mainBranchProbability ?? 0.6,
        depth: 1,
        parentId: 'root',
        children: [],
        outcome: 'BULLISH'
      },
      {
        id: 'alt1',
        name: 'ALTERNATIVE',
        probability: 1 - (stats.mainBranchProbability ?? 0.6),
        depth: 1,
        parentId: 'root',
        children: [],
        outcome: 'BEARISH'
      }
    ];
    
    return {
      mainBranch: 'MAIN_BRANCH',
      branches,
      stats: {
        totalBranches: stats.totalBranches ?? 3,
        maxDepth: stats.maxDepthReached ?? 2,
        dominanceScore: stats.dominanceScore ?? 0.5,
        uncertaintyScore: stats.uncertaintyScore ?? 0.5
      }
    };
  } catch {
    return {
      mainBranch: 'CONTINUATION',
      branches: [],
      stats: {
        totalBranches: 1,
        maxDepth: 0,
        dominanceScore: 0.5,
        uncertaintyScore: 0.5
      }
    };
  }
}

async function fetchMemoryStatus(asset: string, tf: string): Promise<MemoryStatus> {
  try {
    const resp = await fetch(`http://localhost:8001/api/ta/memory/status`);
    const data = await resp.json() as { data?: any };
    
    return {
      totalSnapshots: data.data?.totalSnapshots ?? 0,
      recentMatches: data.data?.recentSearches ?? 0,
      avgConfidence: 0.5,
      dominantBias: 'NEUTRAL',
      biasStrength: 0,
      topPatterns: []
    };
  } catch {
    return {
      totalSnapshots: 0,
      recentMatches: 0,
      avgConfidence: 0,
      dominantBias: 'NEUTRAL',
      biasStrength: 0,
      topPatterns: []
    };
  }
}

async function fetchStrategyPanel(asset: string, tf: string): Promise<StrategyPanel> {
  try {
    const resp = await fetch(`http://localhost:8001/api/ta/metabrain/v3/decision?asset=${asset}&tf=${tf}`);
    const data = await resp.json() as { data?: any };
    
    const dec = data.data ?? {};
    const enabled = dec.strategyPolicy?.enabledStrategies ?? [];
    const disabled = dec.strategyPolicy?.disabledStrategies ?? [];
    const multiplier = dec.strategyPolicy?.strategyMultiplier ?? 1.0;
    
    return {
      enabled: enabled.map((s: string) => ({
        strategy: s,
        active: true,
        multiplier
      })),
      disabled,
      regime: 'COMPRESSION'
    };
  } catch {
    return {
      enabled: [],
      disabled: [],
      regime: 'COMPRESSION'
    };
  }
}

function getSystemMetrics(): SystemMetrics {
  return {
    uptime: process.uptime(),
    apiRequests: {
      lastMinute: 0,
      lastHour: 0,
      avgLatencyMs: 50
    },
    wsConnections: 0,
    dbOperations: {
      lastMinute: 0,
      avgLatencyMs: 5
    },
    errors: {
      lastHour: 0,
      lastDay: 0
    }
  };
}

// ═══════════════════════════════════════════════════════════════
// DEFAULTS
// ═══════════════════════════════════════════════════════════════

function getDefaultMetaBrainStatus(): MetaBrainStatus {
  return {
    analysisMode: 'CLASSIC_TA',
    riskMode: 'NORMAL',
    safeMode: false,
    edgeHealth: 0.5,
    drawdownPct: 0,
    portfolioRiskPct: 0,
    memoryConfidence: 0,
    memoryMatches: 0,
    memoryBias: 'NEUTRAL',
    treeUncertainty: 0.5,
    treeRisk: 0.3,
    treeDominance: 0.5,
    riskMultiplier: 1.0,
    maxRiskPerTrade: 0.01,
    confidenceThreshold: 0.55,
    lastUpdated: new Date()
  };
}

// ═══════════════════════════════════════════════════════════════
// MAIN COLLECTOR
// ═══════════════════════════════════════════════════════════════

export async function collectDashboardData(
  asset: string = 'BTCUSDT',
  timeframe: string = '1d'
): Promise<DashboardData> {
  const [metabrain, modules, regime, tree, memory, strategies] = await Promise.all([
    fetchMetaBrainStatus(asset, timeframe),
    fetchModuleHealth(),
    fetchRegimeInfo(asset, timeframe),
    fetchTreeVisualization(asset, timeframe),
    fetchMemoryStatus(asset, timeframe),
    fetchStrategyPanel(asset, timeframe)
  ]);

  return {
    metabrain,
    modules,
    regime,
    tree,
    memory,
    strategies,
    system: getSystemMetrics(),
    asset,
    timeframe,
    generatedAt: new Date()
  };
}

// ═══════════════════════════════════════════════════════════════
// ALERTS GENERATOR
// ═══════════════════════════════════════════════════════════════

export function generateAlerts(data: DashboardData): DashboardAlert[] {
  const alerts: DashboardAlert[] = [];
  const now = new Date();

  // Safe mode alert
  if (data.metabrain.safeMode) {
    alerts.push({
      id: `alert_safemode_${now.getTime()}`,
      type: 'CRITICAL',
      category: 'METABRAIN',
      message: 'Safe Mode Active',
      details: data.metabrain.safeModeReason,
      timestamp: now,
      acknowledged: false
    });
  }

  // Low edge health
  if (data.metabrain.edgeHealth < 0.3) {
    alerts.push({
      id: `alert_edge_${now.getTime()}`,
      type: 'WARNING',
      category: 'SYSTEM',
      message: 'Low Edge Health',
      details: `Edge health at ${(data.metabrain.edgeHealth * 100).toFixed(0)}%`,
      timestamp: now,
      acknowledged: false
    });
  }

  // High tree uncertainty
  if (data.metabrain.treeUncertainty > 0.6) {
    alerts.push({
      id: `alert_tree_${now.getTime()}`,
      type: 'WARNING',
      category: 'TREE',
      message: 'High Market Uncertainty',
      details: `Tree uncertainty at ${(data.metabrain.treeUncertainty * 100).toFixed(0)}%`,
      timestamp: now,
      acknowledged: false
    });
  }

  // Gated modules
  const gatedCount = data.modules.filter(m => m.status !== 'ACTIVE').length;
  if (gatedCount > 2) {
    alerts.push({
      id: `alert_modules_${now.getTime()}`,
      type: 'WARNING',
      category: 'MODULE',
      message: 'Multiple Modules Gated',
      details: `${gatedCount} modules are currently gated`,
      timestamp: now,
      acknowledged: false
    });
  }

  return alerts;
}
