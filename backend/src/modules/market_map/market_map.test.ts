/**
 * Phase 2.5 — Market Map Tests
 * ==============================
 * Unit tests for Market Map Layer
 */

import { describe, it, expect } from 'vitest';
import { getMarketMap, detectCurrentState } from './market_map.service.js';
import { buildMarketTree, getMainPath, calculateTreeEntropy } from './market_map.tree.js';
import { getHeatmap } from './market_map.heatmap.js';
import { getTimeline } from './market_map.timeline.js';

describe('Market Map Service', () => {
  describe('getMarketMap', () => {
    it('should return valid market map structure', async () => {
      const result = await getMarketMap('BTCUSDT', '1d');
      
      expect(result).toBeDefined();
      expect(result.symbol).toBe('BTCUSDT');
      expect(result.timeframe).toBe('1d');
      expect(result.currentState).toBeDefined();
      expect(result.currentPrice).toBeGreaterThan(0);
      expect(result.branches).toBeInstanceOf(Array);
      expect(result.branches.length).toBeGreaterThan(0);
      expect(result.stats).toBeDefined();
    });

    it('should have valid branches', async () => {
      const result = await getMarketMap('BTCUSDT');
      
      for (const branch of result.branches) {
        expect(branch.scenario).toBeDefined();
        expect(branch.probability).toBeGreaterThanOrEqual(0);
        expect(branch.probability).toBeLessThanOrEqual(1);
        expect(branch.direction).toMatch(/^(BULL|BEAR|NEUTRAL)$/);
        expect(branch.path).toBeInstanceOf(Array);
        expect(branch.events).toBeInstanceOf(Array);
      }
    });

    it('should have valid stats', async () => {
      const result = await getMarketMap('ETHUSDT');
      
      expect(result.stats.dominantScenario).toBeDefined();
      expect(result.stats.dominantProbability).toBeGreaterThan(0);
      expect(result.stats.uncertainty).toBeGreaterThanOrEqual(0);
      expect(result.stats.uncertainty).toBeLessThanOrEqual(1);
      expect(result.stats.totalBranches).toBeGreaterThan(0);
    });
  });

  describe('detectCurrentState', () => {
    it('should return valid market state', () => {
      const state = detectCurrentState('BTCUSDT');
      const validStates = [
        'COMPRESSION', 'BREAKOUT', 'EXPANSION', 'RANGE',
        'EXHAUSTION', 'REVERSAL', 'CONTINUATION', 'LIQUIDITY_SWEEP', 'RETEST'
      ];
      expect(validStates).toContain(state);
    });
  });
});

describe('Market Map Tree', () => {
  describe('buildMarketTree', () => {
    it('should build valid tree structure', () => {
      const tree = buildMarketTree('BTCUSDT', '1d', 'COMPRESSION', 3);
      
      expect(tree).toBeDefined();
      expect(tree.symbol).toBe('BTCUSDT');
      expect(tree.root).toBe('COMPRESSION');
      expect(tree.branches).toBeInstanceOf(Array);
      expect(tree.stats).toBeDefined();
    });

    it('should have valid tree nodes', () => {
      const tree = buildMarketTree('BTCUSDT', '1d', 'BREAKOUT', 2);
      
      for (const node of tree.branches) {
        expect(node.id).toBeDefined();
        expect(node.state).toBeDefined();
        expect(node.probability).toBeGreaterThan(0);
        expect(node.expectedMove).toBeGreaterThanOrEqual(0);
      }
    });

    it('should respect max depth', () => {
      const tree = buildMarketTree('BTCUSDT', '1d', 'RANGE', 2);
      expect(tree.stats.maxDepth).toBeLessThanOrEqual(2);
    });
  });

  describe('getMainPath', () => {
    it('should return dominant path', () => {
      const tree = buildMarketTree('BTCUSDT', '1d', 'COMPRESSION', 3);
      const mainPath = getMainPath(tree.branches);
      
      expect(mainPath).toBeInstanceOf(Array);
      expect(mainPath.length).toBeGreaterThan(0);
    });
  });

  describe('calculateTreeEntropy', () => {
    it('should return valid entropy value', () => {
      const tree = buildMarketTree('BTCUSDT', '1d', 'EXPANSION', 2);
      const entropy = calculateTreeEntropy(tree.branches);
      
      expect(entropy).toBeGreaterThanOrEqual(0);
    });
  });
});

describe('Market Map Heatmap', () => {
  describe('getHeatmap', () => {
    it('should return valid heatmap structure', async () => {
      const result = await getHeatmap('BTCUSDT', '1d', 10, 0.15);
      
      expect(result).toBeDefined();
      expect(result.symbol).toBe('BTCUSDT');
      expect(result.levels).toBeInstanceOf(Array);
      expect(result.levels.length).toBe(10);
      expect(result.priceRange).toBeDefined();
    });

    it('should have valid levels', async () => {
      const result = await getHeatmap('BTCUSDT');
      
      for (const level of result.levels) {
        expect(level.price).toBeGreaterThan(0);
        expect(level.probability).toBeGreaterThanOrEqual(0);
        expect(level.probability).toBeLessThanOrEqual(1);
        expect(['support', 'resistance', 'magnet', 'neutral']).toContain(level.type);
      }
    });

    it('should have probabilities that sum close to 1', async () => {
      const result = await getHeatmap('BTCUSDT', '1d', 10);
      const totalProb = result.levels.reduce((sum, l) => sum + l.probability, 0);
      
      expect(totalProb).toBeGreaterThan(0.9);
      expect(totalProb).toBeLessThan(1.1);
    });
  });
});

describe('Market Map Timeline', () => {
  describe('getTimeline', () => {
    it('should return valid timeline structure', async () => {
      const result = await getTimeline('BTCUSDT', '1d', 5);
      
      expect(result).toBeDefined();
      expect(result.symbol).toBe('BTCUSDT');
      expect(result.events).toBeInstanceOf(Array);
      expect(result.sequence).toBeInstanceOf(Array);
    });

    it('should have valid events', async () => {
      const result = await getTimeline('BTCUSDT');
      
      for (const event of result.events) {
        expect(event.event).toBeDefined();
        expect(event.probability).toBeGreaterThan(0);
        expect(event.probability).toBeLessThanOrEqual(1);
        expect(['HIGH', 'MEDIUM', 'LOW']).toContain(event.impact);
      }
    });

    it('should respect maxEvents limit', async () => {
      const result = await getTimeline('BTCUSDT', '1d', 3);
      expect(result.events.length).toBeLessThanOrEqual(3);
    });
  });
});
