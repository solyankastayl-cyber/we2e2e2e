/**
 * Phase 6.5 — MTF Tests
 * 
 * Tests for Multi-Timeframe Confirmation Layer
 */

import { describe, it, expect } from 'vitest';
import { calculateMTFBoost, computeMTFState } from './mtf.alignment.js';
import { createMockMTFContext } from './mtf.context.js';
import { MTFAlignmentInput, DEFAULT_MTF_CONFIG } from './mtf.types.js';

describe('MTF Alignment Engine', () => {
  describe('calculateMTFBoost', () => {
    it('should return boost > 1 when all aligned', () => {
      const input: MTFAlignmentInput = {
        anchorDirection: 'LONG',
        higherBiasAligned: true,
        regimeAligned: true,
        structureAligned: true,
        scenarioAligned: true,
        lowerMomentumAligned: true,
        higherConflict: false
      };
      
      const boost = calculateMTFBoost(input);
      
      expect(boost).toBeGreaterThan(1.0);
      expect(boost).toBeLessThanOrEqual(1.15);
    });
    
    it('should return boost < 1 when higher TF conflicts', () => {
      const input: MTFAlignmentInput = {
        anchorDirection: 'LONG',
        higherBiasAligned: false,
        regimeAligned: false,
        structureAligned: false,
        scenarioAligned: false,
        lowerMomentumAligned: false,
        higherConflict: true
      };
      
      const boost = calculateMTFBoost(input);
      
      expect(boost).toBeLessThan(1.0);
      expect(boost).toBeGreaterThanOrEqual(0.88);
    });
    
    it('should clamp to max 1.15', () => {
      const input: MTFAlignmentInput = {
        anchorDirection: 'LONG',
        higherBiasAligned: true,
        regimeAligned: true,
        structureAligned: true,
        scenarioAligned: true,
        lowerMomentumAligned: true,
        higherConflict: false
      };
      
      const boost = calculateMTFBoost(input);
      
      expect(boost).toBeLessThanOrEqual(DEFAULT_MTF_CONFIG.boostMax);
    });
    
    it('should clamp to min 0.88', () => {
      const input: MTFAlignmentInput = {
        anchorDirection: 'LONG',
        higherBiasAligned: false,
        regimeAligned: false,
        structureAligned: false,
        scenarioAligned: false,
        lowerMomentumAligned: false,
        higherConflict: true
      };
      
      const boost = calculateMTFBoost(input);
      
      expect(boost).toBeGreaterThanOrEqual(DEFAULT_MTF_CONFIG.boostMin);
    });
  });
  
  describe('computeMTFState', () => {
    it('should compute aligned state for bullish setup', () => {
      const ctx = createMockMTFContext('BTCUSDT', '4h', {
        higherBias: 'BULL',
        higherRegime: 'TREND_UP',
        lowerMomentum: 'BULL',
        anchorDirection: 'LONG'
      });
      
      const state = computeMTFState(ctx);
      
      expect(state.regimeAligned).toBe(true);
      expect(state.momentumAligned).toBe(true);
      expect(state.higherConflict).toBe(false);
      expect(state.mtfBoost).toBeGreaterThan(1.0);
    });
    
    it('should detect conflict when higher TF opposes', () => {
      const ctx = createMockMTFContext('BTCUSDT', '4h', {
        higherBias: 'BEAR',  // Opposing
        higherRegime: 'TREND_DOWN',
        lowerMomentum: 'BULL',
        anchorDirection: 'LONG'  // Trying to go long
      });
      
      const state = computeMTFState(ctx);
      
      expect(state.higherConflict).toBe(true);
      expect(state.mtfBoost).toBeLessThan(1.0);
      expect(state.mtfExecutionAdjustment).toBe(DEFAULT_MTF_CONFIG.executionConflict);
    });
    
    it('should return neutral boost for WAIT direction', () => {
      const ctx = createMockMTFContext('BTCUSDT', '4h', {
        anchorDirection: 'WAIT'
      });
      
      const state = computeMTFState(ctx);
      
      expect(state.mtfBoost).toBe(1.0);
      expect(state.notes).toContain('No active direction - MTF check skipped');
    });
    
    it('should include correct timeframes', () => {
      const ctx = createMockMTFContext('BTCUSDT', '4h');
      const state = computeMTFState(ctx);
      
      expect(state.anchorTf).toBe('4h');
      expect(state.higherTf).toBe('1d');
      expect(state.lowerTf).toBe('1h');
    });
  });
});
