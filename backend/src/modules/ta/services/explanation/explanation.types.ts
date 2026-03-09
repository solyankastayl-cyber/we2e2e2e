/**
 * Explanation Types (P4.3)
 * 
 * Contracts for explanation/attribution system
 */

/**
 * Type of explanation node
 */
export type ExplanationNodeType = 
  | 'pattern'
  | 'indicator'
  | 'scenario'
  | 'stability'
  | 'prior'
  | 'ml'
  | 'regime'
  | 'geometry';

/**
 * Direction of signal
 */
export type SignalDirection = 'bullish' | 'bearish' | 'neutral';

/**
 * Single explanation node
 */
export interface ExplanationNode {
  type: ExplanationNodeType;
  name: string;
  contribution: number;      // [-1, 1] contribution to signal
  direction: SignalDirection;
  confidence: number;        // [0, 1]
  description: string;
  weight?: number;           // Weight used in composition
  rawValue?: number;         // Raw underlying value
}

/**
 * Full explanation pack
 */
export interface ExplanationPack {
  totalScore: number;
  
  // All contributing nodes
  nodes: ExplanationNode[];
  
  // Top drivers (names)
  dominantDrivers: string[];
  
  // Risk factors (bearish/warning signals)
  riskFactors: string[];
  
  // Summary text
  summary: string;
  
  // Confidence in explanation
  confidence: number;
}

/**
 * Input for building explanation
 */
export interface BuildExplanationInput {
  patterns: Array<{
    type: string;
    score: number;
    direction?: string;
    confidence?: number;
  }>;
  
  indicators?: Array<{
    name: string;
    value: number;
    signal?: string;
    strength?: number;
  }>;
  
  ml?: {
    pEntry: number;
    expectedR: number;
    contribution: number;
  };
  
  scenario?: {
    pTarget: number;
    p50: number;
    contribution: number;
  };
  
  stability?: {
    multiplier: number;
    degrading: boolean;
  };
  
  regime?: {
    type: string;
    confidence: number;
  };
  
  geometry?: {
    fitError: number;
    maturity: number;
    compression: number;
  };
  
  probabilityPack?: {
    pEntry: number;
    EV: number;
    weights: {
      ml: number;
      scenario: number;
      priors: number;
    };
  };
}

/**
 * Attribution rule
 */
export interface AttributionRule {
  type: ExplanationNodeType;
  name: string;
  condition: (input: BuildExplanationInput) => boolean;
  contribution: (input: BuildExplanationInput) => number;
  description: (input: BuildExplanationInput) => string;
  direction: (input: BuildExplanationInput) => SignalDirection;
}
