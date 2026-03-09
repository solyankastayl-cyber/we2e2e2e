/**
 * P1.2 — Module Gating Tests
 */

import { describe, it, expect } from 'vitest';
import { AnalysisModule, ALL_MODULES } from './module_attribution.types.js';
import {
  ModuleGate,
  ModuleGateStatus,
  ModuleGatingInput,
  DEFAULT_GATING_RULES
} from './learning.gating.types.js';
import {
  calculateGatingScore,
  determineGateStatus,
  computeModuleGates,
  applyModuleGate,
  calculateGatingSummary,
  isGatingChangeAllowed,
  getDefaultGates,
  isModuleGated,
  getModuleGateStatus
} from './learning.gating.js';

describe('Module Gating', () => {
  describe('calculateGatingScore', () => {
    it('returns 0 for perfect module', () => {
      const input: ModuleGatingInput = {
        module: 'PATTERN',
        weight: 1.2,
        sampleSize: 500,
        avgOutcomeImpact: 0.1,
        degradationStreak: 0
      };
      
      const score = calculateGatingScore(input);
      expect(score).toBeLessThan(0.1);
    });

    it('returns high score for poor module', () => {
      const input: ModuleGatingInput = {
        module: 'FRACTAL',
        weight: 0.7,
        sampleSize: 500,
        avgOutcomeImpact: -0.15,
        degradationStreak: 5
      };
      
      const score = calculateGatingScore(input);
      expect(score).toBeGreaterThan(0.2);  // Score increases with negative factors
    });
  });

  describe('determineGateStatus', () => {
    it('returns ACTIVE for insufficient samples', () => {
      const input: ModuleGatingInput = {
        module: 'PATTERN',
        weight: 0.5,
        sampleSize: 50,  // Below minimum
        avgOutcomeImpact: -0.2,
        degradationStreak: 5
      };
      
      const decision = determineGateStatus(input);
      expect(decision.status).toBe('ACTIVE');
      expect(decision.reason).toContain('Insufficient');
    });

    it('returns SOFT_GATED for weak module', () => {
      const input: ModuleGatingInput = {
        module: 'FRACTAL',
        weight: 0.85,
        sampleSize: 300,
        avgOutcomeImpact: -0.02,
        degradationStreak: 1
      };
      
      const decision = determineGateStatus(input);
      expect(decision.status).toBe('SOFT_GATED');
    });

    it('returns HARD_GATED for persistent negative contribution', () => {
      const input: ModuleGatingInput = {
        module: 'PHYSICS',
        weight: 0.75,
        sampleSize: 600,
        avgOutcomeImpact: -0.1,
        degradationStreak: 4
      };
      
      const decision = determineGateStatus(input);
      expect(decision.status).toBe('HARD_GATED');
      expect(decision.reason).toContain('Persistent');
    });

    it('returns ACTIVE for good module', () => {
      const input: ModuleGatingInput = {
        module: 'PATTERN',
        weight: 1.1,
        sampleSize: 500,
        avgOutcomeImpact: 0.05,
        degradationStreak: 0
      };
      
      const decision = determineGateStatus(input);
      expect(decision.status).toBe('ACTIVE');
    });
  });

  describe('applyModuleGate', () => {
    it('applies no change for ACTIVE', () => {
      const gate: ModuleGate = {
        module: 'PATTERN',
        status: 'ACTIVE',
        reason: 'Good',
        score: 0,
        sampleSize: 500,
        avgOutcomeImpact: 0.1,
        weight: 1.0,
        updatedAt: Date.now(),
        createdAt: Date.now()
      };
      
      const result = applyModuleGate('PATTERN', 1.5, 1.1, gate);
      expect(result.gateApplied).toBe(false);
      expect(result.gatedBoost).toBe(1.65); // 1.5 * 1.1
    });

    it('reduces boost by 30% for SOFT_GATED', () => {
      const gate: ModuleGate = {
        module: 'FRACTAL',
        status: 'SOFT_GATED',
        reason: 'Weak',
        score: 0.3,
        sampleSize: 300,
        avgOutcomeImpact: -0.02,
        weight: 0.9,
        updatedAt: Date.now(),
        createdAt: Date.now()
      };
      
      const result = applyModuleGate('FRACTAL', 1.5, 0.9, gate);
      expect(result.gateApplied).toBe(true);
      expect(result.gatedBoost).toBe(0.945); // 1.5 * 0.9 * 0.7
      expect(result.multiplier).toBe(0.63); // 0.9 * 0.7
    });

    it('returns 1.0 for HARD_GATED', () => {
      const gate: ModuleGate = {
        module: 'PHYSICS',
        status: 'HARD_GATED',
        reason: 'Bad',
        score: 0.7,
        sampleSize: 600,
        avgOutcomeImpact: -0.1,
        weight: 0.7,
        updatedAt: Date.now(),
        createdAt: Date.now()
      };
      
      const result = applyModuleGate('PHYSICS', 1.5, 0.7, gate);
      expect(result.gateApplied).toBe(true);
      expect(result.gatedBoost).toBe(1.0);
      expect(result.gateStatus).toBe('HARD_GATED');
    });
  });

  describe('calculateGatingSummary', () => {
    it('calculates correct summary', () => {
      const gates: ModuleGate[] = [
        { module: 'PATTERN', status: 'ACTIVE', reason: '', score: 0, sampleSize: 0, avgOutcomeImpact: 0, weight: 1, updatedAt: Date.now(), createdAt: Date.now() },
        { module: 'GRAPH', status: 'ACTIVE', reason: '', score: 0, sampleSize: 0, avgOutcomeImpact: 0, weight: 1, updatedAt: Date.now(), createdAt: Date.now() },
        { module: 'FRACTAL', status: 'SOFT_GATED', reason: '', score: 0, sampleSize: 0, avgOutcomeImpact: 0, weight: 1, updatedAt: Date.now(), createdAt: Date.now() },
        { module: 'PHYSICS', status: 'HARD_GATED', reason: '', score: 0, sampleSize: 0, avgOutcomeImpact: 0, weight: 1, updatedAt: Date.now(), createdAt: Date.now() }
      ];
      
      const summary = calculateGatingSummary(gates);
      
      expect(summary.totalModules).toBe(4);
      expect(summary.activeModules).toBe(2);
      expect(summary.softGatedModules).toBe(1);
      expect(summary.hardGatedModules).toBe(1);
      expect(summary.gatedModulesList).toContain('FRACTAL');
      expect(summary.gatedModulesList).toContain('PHYSICS');
      expect(summary.gatePressure).toBeGreaterThan(0);
    });
  });

  describe('isGatingChangeAllowed', () => {
    it('allows change when under limits', () => {
      const currentGates: ModuleGate[] = [];
      const proposedGate: ModuleGate = {
        module: 'PATTERN',
        status: 'SOFT_GATED',
        reason: 'Test',
        score: 0.3,
        sampleSize: 200,
        avgOutcomeImpact: -0.02,
        weight: 0.9,
        updatedAt: Date.now(),
        createdAt: Date.now()
      };
      
      const result = isGatingChangeAllowed(currentGates, proposedGate, 0);
      expect(result.allowed).toBe(true);
    });

    it('blocks when max hard gated reached', () => {
      const currentGates: ModuleGate[] = [
        { module: 'PATTERN', status: 'HARD_GATED', reason: '', score: 0, sampleSize: 0, avgOutcomeImpact: 0, weight: 1, updatedAt: Date.now(), createdAt: Date.now() },
        { module: 'GRAPH', status: 'HARD_GATED', reason: '', score: 0, sampleSize: 0, avgOutcomeImpact: 0, weight: 1, updatedAt: Date.now(), createdAt: Date.now() },
        { module: 'FRACTAL', status: 'HARD_GATED', reason: '', score: 0, sampleSize: 0, avgOutcomeImpact: 0, weight: 1, updatedAt: Date.now(), createdAt: Date.now() }
      ];
      
      const proposedGate: ModuleGate = {
        module: 'PHYSICS',
        status: 'HARD_GATED',
        reason: 'Test',
        score: 0.7,
        sampleSize: 600,
        avgOutcomeImpact: -0.1,
        weight: 0.7,
        updatedAt: Date.now(),
        createdAt: Date.now()
      };
      
      const result = isGatingChangeAllowed(currentGates, proposedGate, 0);
      expect(result.allowed).toBe(false);
      expect(result.reason).toContain('hard-gated');
    });
  });

  describe('getDefaultGates', () => {
    it('returns all modules as ACTIVE', () => {
      const gates = getDefaultGates();
      
      expect(gates.length).toBe(ALL_MODULES.length);
      gates.forEach(gate => {
        expect(gate.status).toBe('ACTIVE');
      });
    });
  });

  describe('isModuleGated', () => {
    it('returns false for ACTIVE module', () => {
      const gates = new Map<string, ModuleGate>();
      gates.set('PATTERN', {
        module: 'PATTERN',
        status: 'ACTIVE',
        reason: '',
        score: 0,
        sampleSize: 0,
        avgOutcomeImpact: 0,
        weight: 1,
        updatedAt: Date.now(),
        createdAt: Date.now()
      });
      
      expect(isModuleGated('PATTERN', gates)).toBe(false);
    });

    it('returns true for gated module', () => {
      const gates = new Map<string, ModuleGate>();
      gates.set('FRACTAL', {
        module: 'FRACTAL',
        status: 'SOFT_GATED',
        reason: '',
        score: 0.3,
        sampleSize: 0,
        avgOutcomeImpact: 0,
        weight: 1,
        updatedAt: Date.now(),
        createdAt: Date.now()
      });
      
      expect(isModuleGated('FRACTAL', gates)).toBe(true);
    });
  });
});
