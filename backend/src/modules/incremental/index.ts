/**
 * Phase 7.5 — Incremental Engine
 * 
 * Module exports
 */

export * from './incremental.types.js';
export { buildDependencyGraph, markDirty, markClean, getNodesToCompute, getCleanNodes } from './incremental.graph.js';
export { IncrementalEngine, getIncrementalEngine } from './incremental.engine.js';
export { registerIncrementalRoutes, initIncrementalIndexes } from './incremental.routes.js';
