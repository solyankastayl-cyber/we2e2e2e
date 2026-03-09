/**
 * Phase 7.5 — Incremental Engine: Graph Builder
 * 
 * Builds and manages the dependency graph
 */

import {
  NodeId,
  NodeStatus,
  DependencyNode,
  DependencyGraph,
  DEPENDENCY_MAP,
  NODE_COSTS
} from './incremental.types.js';

/**
 * Build initial dependency graph
 */
export function buildDependencyGraph(): DependencyGraph {
  const nodes = new Map<NodeId, DependencyNode>();
  
  // Create all nodes
  for (const [nodeId, deps] of Object.entries(DEPENDENCY_MAP)) {
    nodes.set(nodeId as NodeId, {
      id: nodeId as NodeId,
      dependsOn: deps as NodeId[],
      dependents: [],
      status: 'CLEAN',
      lastComputed: 0,
      computeDuration: NODE_COSTS[nodeId as NodeId] || 50,
      version: 0
    });
  }
  
  // Build reverse dependencies (dependents)
  for (const [nodeId, deps] of Object.entries(DEPENDENCY_MAP)) {
    for (const dep of deps as NodeId[]) {
      const depNode = nodes.get(dep);
      if (depNode && !depNode.dependents.includes(nodeId as NodeId)) {
        depNode.dependents.push(nodeId as NodeId);
      }
    }
  }
  
  // Build topological order
  const computationOrder = topologicalSort(nodes);
  
  return {
    nodes,
    computationOrder,
    lastFullCompute: 0,
    incrementalSaves: 0
  };
}

/**
 * Topological sort for computation order
 */
function topologicalSort(nodes: Map<NodeId, DependencyNode>): NodeId[] {
  const visited = new Set<NodeId>();
  const result: NodeId[] = [];
  
  function visit(nodeId: NodeId) {
    if (visited.has(nodeId)) return;
    visited.add(nodeId);
    
    const node = nodes.get(nodeId);
    if (node) {
      for (const dep of node.dependsOn) {
        visit(dep);
      }
    }
    
    result.push(nodeId);
  }
  
  for (const nodeId of nodes.keys()) {
    visit(nodeId);
  }
  
  return result;
}

/**
 * Mark node as dirty (needs recomputation)
 */
export function markDirty(graph: DependencyGraph, nodeId: NodeId): NodeId[] {
  const dirtyNodes: NodeId[] = [];
  const queue: NodeId[] = [nodeId];
  const seen = new Set<NodeId>();
  
  while (queue.length > 0) {
    const current = queue.shift()!;
    if (seen.has(current)) continue;
    seen.add(current);
    
    const node = graph.nodes.get(current);
    if (!node) continue;
    
    // Mark as dirty
    node.status = 'DIRTY';
    dirtyNodes.push(current);
    
    // Propagate to dependents
    for (const dependent of node.dependents) {
      if (!seen.has(dependent)) {
        queue.push(dependent);
      }
    }
  }
  
  return dirtyNodes;
}

/**
 * Mark node as clean after computation
 */
export function markClean(
  graph: DependencyGraph,
  nodeId: NodeId,
  result?: any,
  duration?: number
): void {
  const node = graph.nodes.get(nodeId);
  if (!node) return;
  
  node.status = 'CLEAN';
  node.lastComputed = Date.now();
  node.version++;
  
  if (result !== undefined) {
    node.cachedResult = result;
  }
  
  if (duration !== undefined) {
    node.computeDuration = duration;
  }
}

/**
 * Get nodes that need computation (dirty nodes in topological order)
 */
export function getNodesToCompute(graph: DependencyGraph): NodeId[] {
  return graph.computationOrder.filter(nodeId => {
    const node = graph.nodes.get(nodeId);
    return node && node.status === 'DIRTY';
  });
}

/**
 * Get nodes that can be skipped (clean nodes)
 */
export function getCleanNodes(graph: DependencyGraph): NodeId[] {
  return graph.computationOrder.filter(nodeId => {
    const node = graph.nodes.get(nodeId);
    return node && node.status === 'CLEAN';
  });
}

/**
 * Check if all dependencies are computed
 */
export function canCompute(graph: DependencyGraph, nodeId: NodeId): boolean {
  const node = graph.nodes.get(nodeId);
  if (!node) return false;
  
  for (const dep of node.dependsOn) {
    const depNode = graph.nodes.get(dep);
    if (!depNode || depNode.status !== 'CLEAN') {
      return false;
    }
  }
  
  return true;
}

/**
 * Estimate time saved by incremental computation
 */
export function estimateTimeSaved(
  graph: DependencyGraph,
  computedNodes: NodeId[],
  skippedNodes: NodeId[]
): number {
  let savedTime = 0;
  
  for (const nodeId of skippedNodes) {
    const cost = NODE_COSTS[nodeId] || 50;
    savedTime += cost;
  }
  
  return savedTime;
}

/**
 * Get graph statistics
 */
export function getGraphStats(graph: DependencyGraph): {
  nodeCount: number;
  edgeCount: number;
  cleanNodes: number;
  dirtyNodes: number;
  avgComputeTime: number;
} {
  let edgeCount = 0;
  let cleanNodes = 0;
  let dirtyNodes = 0;
  let totalComputeTime = 0;
  
  for (const node of graph.nodes.values()) {
    edgeCount += node.dependsOn.length;
    
    if (node.status === 'CLEAN') cleanNodes++;
    else if (node.status === 'DIRTY') dirtyNodes++;
    
    totalComputeTime += node.computeDuration;
  }
  
  return {
    nodeCount: graph.nodes.size,
    edgeCount,
    cleanNodes,
    dirtyNodes,
    avgComputeTime: totalComputeTime / graph.nodes.size
  };
}

/**
 * Visualize graph as adjacency list (for debugging)
 */
export function visualizeGraph(graph: DependencyGraph): string {
  const lines: string[] = ['Dependency Graph:'];
  
  for (const nodeId of graph.computationOrder) {
    const node = graph.nodes.get(nodeId);
    if (!node) continue;
    
    const deps = node.dependsOn.length > 0 
      ? ` ← [${node.dependsOn.join(', ')}]` 
      : ' (root)';
    
    const status = `[${node.status}]`;
    
    lines.push(`  ${nodeId}${deps} ${status}`);
  }
  
  return lines.join('\n');
}
