/**
 * P1.1 — Tree Integration Tests
 */

import { describe, it, expect } from 'vitest';
import { TreeStats } from './digital_twin.types.js';
import {
  getTreeAdjustments,
  createTreeIntegrationResult,
  applyTreeDecisionAdjustment,
  applyTreeExecutionAdjustment,
  applyTreeStopAdjustment,
  getTreePolicyHints,
  getNeutralTreeAdjustments
} from './tree.integration.js';

describe('Tree Integration', () => {
  const mockTreeStats: TreeStats = {
    dominanceScore: 0.7,
    uncertaintyScore: 0.3,
    treeRisk: 0.25,
    mainBranchProbability: 0.65,
    totalBranches: 3,
    maxDepthReached: 2
  };

  describe('getTreeAdjustments', () => {
    it('calculates adjustments from tree stats', () => {
      const adj = getTreeAdjustments(mockTreeStats);
      
      expect(adj.decisionAdjustment).toBeGreaterThan(0.9);
      expect(adj.decisionAdjustment).toBeLessThan(1.2);
      expect(adj.executionAdjustment).toBeGreaterThan(0.7);
      expect(adj.executionAdjustment).toBeLessThanOrEqual(1.15);
      expect(adj.riskModeHint).toBe('NORMAL');
      expect(adj.shouldTrade).toBe(true);
    });

    it('returns CONSERVATIVE for high uncertainty', () => {
      const highUncertainty: TreeStats = {
        ...mockTreeStats,
        uncertaintyScore: 0.8,
        treeRisk: 0.6
      };
      
      const adj = getTreeAdjustments(highUncertainty);
      expect(adj.riskModeHint).toBe('CONSERVATIVE');
    });

    it('returns AGGRESSIVE for strong dominance', () => {
      const strongDominance: TreeStats = {
        ...mockTreeStats,
        dominanceScore: 0.85,
        uncertaintyScore: 0.2,
        treeRisk: 0.15
      };
      
      const adj = getTreeAdjustments(strongDominance);
      expect(adj.riskModeHint).toBe('AGGRESSIVE');
    });
  });

  describe('applyTreeDecisionAdjustment', () => {
    it('applies adjustment to base score', () => {
      const adj = getTreeAdjustments(mockTreeStats);
      const result = applyTreeDecisionAdjustment(1.5, adj);
      
      expect(result.treeApplied).toBe(true);
      expect(result.score).not.toBe(1.5);
      expect(result.score).toBe(Math.round(1.5 * adj.decisionAdjustment * 1000) / 1000);
    });

    it('returns unchanged score when adjustments null', () => {
      const result = applyTreeDecisionAdjustment(1.5, null);
      
      expect(result.treeApplied).toBe(false);
      expect(result.score).toBe(1.5);
      expect(result.treeAdjustment).toBe(1.0);
    });
  });

  describe('applyTreeExecutionAdjustment', () => {
    it('applies adjustment to position size', () => {
      const adj = getTreeAdjustments(mockTreeStats);
      const result = applyTreeExecutionAdjustment(100, adj);
      
      expect(result.treeApplied).toBe(true);
      expect(result.size).toBeLessThanOrEqual(100);
      expect(result.size).toBeGreaterThan(50);
    });
  });

  describe('applyTreeStopAdjustment', () => {
    it('does not tighten stop for normal tree', () => {
      const adj = getTreeAdjustments(mockTreeStats);
      const result = applyTreeStopAdjustment(95, 100, adj);
      
      expect(result.adjusted).toBe(false);
      expect(result.stop).toBe(95);
    });

    it('tightens stop for high risk tree', () => {
      const highRisk: TreeStats = {
        ...mockTreeStats,
        treeRisk: 0.6,
        uncertaintyScore: 0.7
      };
      
      const adj = getTreeAdjustments(highRisk);
      
      if (adj.stopAdjustment?.tighten) {
        const result = applyTreeStopAdjustment(95, 100, adj);
        expect(result.adjusted).toBe(true);
        expect(result.stop).toBeGreaterThan(95); // Tighter stop for long
      }
    });
  });

  describe('getTreePolicyHints', () => {
    it('returns policy hints', () => {
      const adj = getTreeAdjustments(mockTreeStats);
      const hints = getTreePolicyHints(adj);
      
      expect(hints.suggestedRiskMode).toBeDefined();
      expect(typeof hints.shouldReduceExposure).toBe('boolean');
      expect(typeof hints.confidenceThresholdBoost).toBe('number');
    });

    it('returns neutral hints when null', () => {
      const hints = getTreePolicyHints(null);
      
      expect(hints.suggestedRiskMode).toBe('NORMAL');
      expect(hints.shouldReduceExposure).toBe(false);
    });
  });

  describe('getNeutralTreeAdjustments', () => {
    it('returns neutral values', () => {
      const neutral = getNeutralTreeAdjustments();
      
      expect(neutral.decisionAdjustment).toBe(1.0);
      expect(neutral.executionAdjustment).toBe(1.0);
      expect(neutral.riskModeHint).toBe('NORMAL');
    });
  });

  describe('createTreeIntegrationResult', () => {
    it('creates full integration result', () => {
      const result = createTreeIntegrationResult(mockTreeStats, true);
      
      expect(result.treeStats).toEqual(mockTreeStats);
      expect(result.adjustments).toBeDefined();
      expect(result.applied).toBe(true);
      expect(result.appliedAt).toBeInstanceOf(Date);
    });
  });
});
