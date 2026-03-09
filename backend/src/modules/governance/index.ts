/**
 * Governance Engine
 * 
 * Prevents adaptive overfitting by controlling:
 * - Rate of weight changes
 * - Minimum evidence requirements
 * - Shadow mode testing
 * - Freeze mode during instability
 * - Rollback capabilities
 * 
 * This is the "stability guard" that keeps the system from
 * optimizing itself into oblivion.
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db, Collection } from 'mongodb';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface GovernanceConfig {
  // Rate limits
  maxWeightChangePerDay: number;    // Max % change per day (default: 5%)
  maxWeightChangePerWeek: number;   // Max % change per week (default: 15%)
  
  // Evidence requirements
  minSampleSizeForChange: number;   // Minimum trades before allowing change (default: 200)
  minConfidenceForChange: number;   // Minimum confidence level (default: 0.7)
  
  // Memory blending
  shortTermWeight: number;          // Weight for recent performance (default: 0.2)
  longTermWeight: number;           // Weight for historical performance (default: 0.8)
  shortTermWindow: number;          // Days for short-term (default: 30)
  longTermWindow: number;           // Days for long-term (default: 365)
  
  // Shadow mode
  shadowTestDays: number;           // Days to test in shadow before live (default: 14)
  shadowMinImprovement: number;     // Min improvement required (default: 0.05)
  
  // Freeze triggers
  freezeOnConsecutiveFailures: number;  // Freeze after N failed updates (default: 3)
  freezeOnDrawdownIncrease: number;     // Freeze if DD increases by % (default: 0.1)
  freezeOnVolatilitySpike: number;      // Freeze on vol spike % (default: 2)
  
  // Auto-unfreeze
  autoUnfreezeAfterDays: number;    // Auto-unfreeze after N stable days (default: 7)
}

export const DEFAULT_GOVERNANCE_CONFIG: GovernanceConfig = {
  maxWeightChangePerDay: 0.05,
  maxWeightChangePerWeek: 0.15,
  
  minSampleSizeForChange: 200,
  minConfidenceForChange: 0.7,
  
  shortTermWeight: 0.2,
  longTermWeight: 0.8,
  shortTermWindow: 30,
  longTermWindow: 365,
  
  shadowTestDays: 14,
  shadowMinImprovement: 0.05,
  
  freezeOnConsecutiveFailures: 3,
  freezeOnDrawdownIncrease: 0.1,
  freezeOnVolatilitySpike: 2,
  
  autoUnfreezeAfterDays: 7,
};

export interface UpdateRequest {
  id: string;
  type: 'PATTERN_WEIGHT' | 'EDGE_MULTIPLIER' | 'CALIBRATION' | 'AUTOPILOT';
  targetId: string;
  
  // Change details
  currentValue: number;
  proposedValue: number;
  changePercent: number;
  
  // Evidence
  sampleSize: number;
  confidence: number;
  shortTermPF: number;
  longTermPF: number;
  
  // Timing
  requestedAt: Date;
  
  // Status
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'SHADOW' | 'APPLIED';
  rejectionReason?: string;
}

export interface GovernanceState {
  frozen: boolean;
  frozenAt?: Date;
  freezeReason?: string;
  
  consecutiveFailures: number;
  lastSuccessfulUpdate?: Date;
  
  // Metrics
  totalRequests: number;
  approvedRequests: number;
  rejectedRequests: number;
  shadowRequests: number;
  
  // Recent changes tracking
  recentChanges: Array<{
    timestamp: Date;
    type: string;
    changePercent: number;
  }>;
}

// ═══════════════════════════════════════════════════════════════
// Governance Engine
// ═══════════════════════════════════════════════════════════════

export class GovernanceEngine {
  private db: Db;
  private config: GovernanceConfig;
  private state: GovernanceState;
  private updatesCollection: Collection;
  private stateCollection: Collection;

  constructor(db: Db, config?: Partial<GovernanceConfig>) {
    this.db = db;
    this.config = { ...DEFAULT_GOVERNANCE_CONFIG, ...config };
    this.updatesCollection = db.collection('ta_governance_updates');
    this.stateCollection = db.collection('ta_governance_state');
    
    this.state = {
      frozen: false,
      consecutiveFailures: 0,
      totalRequests: 0,
      approvedRequests: 0,
      rejectedRequests: 0,
      shadowRequests: 0,
      recentChanges: [],
    };
  }

  async initialize(): Promise<void> {
    await this.updatesCollection.createIndex({ id: 1 }, { unique: true });
    await this.updatesCollection.createIndex({ status: 1 });
    await this.updatesCollection.createIndex({ requestedAt: -1 });
    
    // Load state
    const savedState = await this.stateCollection.findOne({ _id: 'governance_state' });
    if (savedState) {
      const { _id, ...rest } = savedState;
      this.state = { ...this.state, ...rest };
    }
  }

  private async saveState(): Promise<void> {
    await this.stateCollection.updateOne(
      { _id: 'governance_state' },
      { $set: this.state },
      { upsert: true }
    );
  }

  // ═══════════════════════════════════════════════════════════════
  // Request Validation
  // ═══════════════════════════════════════════════════════════════

  /**
   * Submit an update request for governance review
   */
  async submitRequest(request: Omit<UpdateRequest, 'status' | 'id'>): Promise<UpdateRequest> {
    const fullRequest: UpdateRequest = {
      ...request,
      id: `gov_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      status: 'PENDING',
      requestedAt: new Date(),
    };
    
    this.state.totalRequests++;
    
    // Validate the request
    const validation = this.validateRequest(fullRequest);
    
    if (!validation.valid) {
      fullRequest.status = 'REJECTED';
      fullRequest.rejectionReason = validation.reason;
      this.state.rejectedRequests++;
      this.state.consecutiveFailures++;
    } else if (validation.shadow) {
      fullRequest.status = 'SHADOW';
      this.state.shadowRequests++;
    } else {
      fullRequest.status = 'APPROVED';
      this.state.approvedRequests++;
      this.state.consecutiveFailures = 0;
      this.state.lastSuccessfulUpdate = new Date();
    }
    
    // Check for freeze trigger
    if (this.state.consecutiveFailures >= this.config.freezeOnConsecutiveFailures) {
      this.freeze('Too many consecutive failed updates');
    }
    
    // Save request
    await this.updatesCollection.insertOne(fullRequest);
    await this.saveState();
    
    return fullRequest;
  }

  /**
   * Validate an update request against governance rules
   */
  private validateRequest(request: UpdateRequest): { valid: boolean; shadow: boolean; reason?: string } {
    // Rule 1: Check if system is frozen
    if (this.state.frozen) {
      return { valid: false, shadow: false, reason: 'System is frozen' };
    }
    
    // Rule 2: Check sample size
    if (request.sampleSize < this.config.minSampleSizeForChange) {
      return { 
        valid: false, 
        shadow: false, 
        reason: `Insufficient sample size: ${request.sampleSize} < ${this.config.minSampleSizeForChange}` 
      };
    }
    
    // Rule 3: Check confidence
    if (request.confidence < this.config.minConfidenceForChange) {
      return { 
        valid: false, 
        shadow: false, 
        reason: `Low confidence: ${request.confidence} < ${this.config.minConfidenceForChange}` 
      };
    }
    
    // Rule 4: Check rate limits
    const dailyChange = this.getRecentChangePercent(1);
    if (dailyChange + Math.abs(request.changePercent) > this.config.maxWeightChangePerDay) {
      return { 
        valid: false, 
        shadow: false, 
        reason: `Exceeds daily change limit: ${dailyChange + Math.abs(request.changePercent)} > ${this.config.maxWeightChangePerDay}` 
      };
    }
    
    const weeklyChange = this.getRecentChangePercent(7);
    if (weeklyChange + Math.abs(request.changePercent) > this.config.maxWeightChangePerWeek) {
      return { 
        valid: false, 
        shadow: false, 
        reason: `Exceeds weekly change limit` 
      };
    }
    
    // Rule 5: Blend short-term and long-term performance
    const blendedPF = 
      request.shortTermPF * this.config.shortTermWeight +
      request.longTermPF * this.config.longTermWeight;
    
    // If blended PF shows no improvement, reject
    if (blendedPF < 1.0 && request.changePercent > 0) {
      return { 
        valid: false, 
        shadow: false, 
        reason: `Blended PF not favorable: ${blendedPF.toFixed(2)}` 
      };
    }
    
    // Rule 6: Large changes go to shadow first
    if (Math.abs(request.changePercent) > 0.1) {
      return { valid: true, shadow: true };
    }
    
    return { valid: true, shadow: false };
  }

  /**
   * Get total change percent in last N days
   */
  private getRecentChangePercent(days: number): number {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    
    return this.state.recentChanges
      .filter(c => c.timestamp > cutoff)
      .reduce((sum, c) => sum + Math.abs(c.changePercent), 0);
  }

  // ═══════════════════════════════════════════════════════════════
  // Freeze Control
  // ═══════════════════════════════════════════════════════════════

  freeze(reason: string): void {
    this.state.frozen = true;
    this.state.frozenAt = new Date();
    this.state.freezeReason = reason;
    console.log(`[Governance] FROZEN: ${reason}`);
  }

  unfreeze(): void {
    this.state.frozen = false;
    this.state.frozenAt = undefined;
    this.state.freezeReason = undefined;
    this.state.consecutiveFailures = 0;
    console.log('[Governance] UNFROZEN');
  }

  isFrozen(): boolean {
    return this.state.frozen;
  }

  // ═══════════════════════════════════════════════════════════════
  // Shadow Mode
  // ═══════════════════════════════════════════════════════════════

  /**
   * Promote shadow update to live after successful testing
   */
  async promoteShadowUpdate(requestId: string): Promise<boolean> {
    const request = await this.updatesCollection.findOne({ id: requestId, status: 'SHADOW' });
    if (!request) return false;
    
    await this.updatesCollection.updateOne(
      { id: requestId },
      { $set: { status: 'APPLIED' } }
    );
    
    // Track the change
    this.state.recentChanges.push({
      timestamp: new Date(),
      type: request.type,
      changePercent: request.changePercent,
    });
    
    // Keep only last 30 days of changes
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 30);
    this.state.recentChanges = this.state.recentChanges.filter(c => c.timestamp > cutoff);
    
    await this.saveState();
    return true;
  }

  // ═══════════════════════════════════════════════════════════════
  // Status & Reporting
  // ═══════════════════════════════════════════════════════════════

  getState(): GovernanceState {
    return { ...this.state };
  }

  getConfig(): GovernanceConfig {
    return { ...this.config };
  }

  async getRecentUpdates(limit: number = 20): Promise<UpdateRequest[]> {
    const docs = await this.updatesCollection
      .find({})
      .sort({ requestedAt: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(d => {
      const { _id, ...update } = d as any;
      return update;
    });
  }

  async getPendingShadowUpdates(): Promise<UpdateRequest[]> {
    const docs = await this.updatesCollection
      .find({ status: 'SHADOW' })
      .sort({ requestedAt: 1 })
      .toArray();
    
    return docs.map(d => {
      const { _id, ...update } = d as any;
      return update;
    });
  }
}

// ═══════════════════════════════════════════════════════════════
// Routes
// ═══════════════════════════════════════════════════════════════

export async function registerGovernanceRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const engine = new GovernanceEngine(db);
  await engine.initialize();
  
  // Store on app for other modules
  (app as any).governanceEngine = engine;

  /**
   * GET /status - Get governance status
   */
  app.get('/status', async () => {
    return {
      ok: true,
      state: engine.getState(),
      config: engine.getConfig(),
    };
  });

  /**
   * POST /freeze - Manually freeze system
   */
  app.post('/freeze', async (
    request: FastifyRequest<{ Body: { reason?: string } }>
  ) => {
    const reason = request.body?.reason || 'Manual freeze';
    engine.freeze(reason);
    return { ok: true, frozen: true, reason };
  });

  /**
   * POST /unfreeze - Manually unfreeze system
   */
  app.post('/unfreeze', async () => {
    engine.unfreeze();
    return { ok: true, frozen: false };
  });

  /**
   * GET /updates - Get recent update requests
   */
  app.get('/updates', async (
    request: FastifyRequest<{ Querystring: { limit?: string } }>
  ) => {
    const limit = parseInt(request.query.limit || '20', 10);
    const updates = await engine.getRecentUpdates(limit);
    return {
      ok: true,
      count: updates.length,
      updates,
    };
  });

  /**
   * GET /shadow - Get pending shadow updates
   */
  app.get('/shadow', async () => {
    const updates = await engine.getPendingShadowUpdates();
    return {
      ok: true,
      count: updates.length,
      updates,
    };
  });

  /**
   * POST /shadow/:id/promote - Promote shadow update to live
   */
  app.post('/shadow/:id/promote', async (
    request: FastifyRequest<{ Params: { id: string } }>
  ) => {
    const success = await engine.promoteShadowUpdate(request.params.id);
    return { ok: success };
  });

  /**
   * POST /validate - Test if an update would be approved
   */
  app.post('/validate', async (
    request: FastifyRequest<{
      Body: {
        type?: string;
        currentValue?: number;
        proposedValue?: number;
        sampleSize?: number;
        confidence?: number;
        shortTermPF?: number;
        longTermPF?: number;
      };
    }>
  ) => {
    const body = request.body || {};
    
    const mockRequest = await engine.submitRequest({
      type: (body.type || 'PATTERN_WEIGHT') as any,
      targetId: 'test',
      currentValue: body.currentValue ?? 1.0,
      proposedValue: body.proposedValue ?? 1.1,
      changePercent: body.proposedValue && body.currentValue 
        ? (body.proposedValue - body.currentValue) / body.currentValue 
        : 0.1,
      sampleSize: body.sampleSize ?? 100,
      confidence: body.confidence ?? 0.5,
      shortTermPF: body.shortTermPF ?? 1.0,
      longTermPF: body.longTermPF ?? 1.0,
    });
    
    return {
      ok: true,
      status: mockRequest.status,
      rejectionReason: mockRequest.rejectionReason,
    };
  });

  console.log('[Governance] Routes: /status, /freeze, /unfreeze, /updates, /shadow, /validate');
}

export async function registerGovernanceModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Governance] Registering Governance Engine...');
  
  await app.register(async (instance) => {
    await registerGovernanceRoutes(instance, { db });
  }, { prefix: '/governance' });
  
  console.log('[Governance] ✅ Governance Engine registered at /api/ta/governance/*');
}
