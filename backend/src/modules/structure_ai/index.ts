/**
 * Phase 7 — Market Structure AI Layer
 * 
 * Module exports
 */

export * from './structure.types.js';
export { detectAllEvents, detectLiquiditySweep, detectCompression, detectBreakout } from './structure.detector.js';
export { buildEventChain, determineStructureType, generateNarrative, getExpectedNextEvents } from './structure.chain.js';
export { createStructureAIService, getStructureAIService, type StructureAIService } from './structure.service.js';
export { registerStructureRoutes, initStructureIndexes } from './structure.routes.js';
