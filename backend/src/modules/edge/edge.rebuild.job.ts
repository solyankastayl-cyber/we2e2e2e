/**
 * Edge Rebuild Job (P5.0.7)
 * 
 * Batch process to recalculate all edge statistics
 */

import { Db } from 'mongodb';
import type { 
  EdgeRebuildRequest, 
  EdgeRebuildResult,
  EdgeDimension,
  GlobalBaseline,
} from './domain/types.js';
import { EdgeDatasource, getEdgeDatasource } from './edge.datasource.js';
import { EdgeStorage, getEdgeStorage } from './edge.storage.js';
import { calcGlobalBaseline } from './edge.metrics.js';
import { aggregateAllDimensions } from './edge.aggregator.js';

/**
 * Edge Rebuild Job
 */
export class EdgeRebuildJob {
  private datasource: EdgeDatasource;
  private storage: EdgeStorage;

  constructor(db: Db) {
    this.datasource = getEdgeDatasource(db);
    this.storage = getEdgeStorage(db);
  }

  /**
   * Run the rebuild job
   */
  async run(params: EdgeRebuildRequest = {}): Promise<EdgeRebuildResult> {
    const startTime = Date.now();
    const errors: string[] = [];
    
    console.log('[EdgeRebuild] Starting rebuild job...');
    console.log('[EdgeRebuild] Params:', JSON.stringify(params));
    
    // Create run record
    const run = await this.storage.createRun(params);
    console.log(`[EdgeRebuild] Created run: ${run.runId}`);
    
    try {
      // Ensure indexes
      await this.storage.ensureIndexes();
      
      // Load all edge rows
      console.log('[EdgeRebuild] Loading edge rows...');
      const rows = await this.datasource.loadEdgeRows({
        from: params.from,
        to: params.to,
        assets: params.assets,
        timeframes: params.timeframes,
        limit: 100000, // Max rows to process
      });
      
      console.log(`[EdgeRebuild] Loaded ${rows.length} rows`);
      
      if (rows.length === 0) {
        await this.storage.completeRun(run.runId, {
          status: 'SUCCESS',
          rowsProcessed: 0,
          aggregatesCreated: 0,
        });
        
        return {
          edgeRunId: run.runId,
          status: 'SUCCESS',
          rowsProcessed: 0,
          aggregatesCreated: 0,
          duration: Date.now() - startTime,
        };
      }
      
      // Calculate global baseline
      console.log('[EdgeRebuild] Calculating global baseline...');
      const globalBaseline = calcGlobalBaseline(rows);
      console.log('[EdgeRebuild] Global baseline:', JSON.stringify(globalBaseline));
      
      // Save global baseline
      await this.storage.saveGlobalBaseline(run.runId, globalBaseline);
      
      // Aggregate by all dimensions
      console.log('[EdgeRebuild] Aggregating by dimensions...');
      const allAggregates = aggregateAllDimensions(rows, globalBaseline);
      
      // Save aggregates
      let totalAggregates = 0;
      const dimensions: EdgeDimension[] = [
        'pattern', 'family', 'regime', 'geometry',
        'ml_bucket', 'stability_bucket', 'timeframe', 'asset'
      ];
      
      for (const dimension of dimensions) {
        const aggregates = allAggregates.get(dimension) || [];
        console.log(`[EdgeRebuild] ${dimension}: ${aggregates.length} aggregates`);
        
        if (aggregates.length > 0) {
          const saved = await this.storage.saveAggregates(run.runId, aggregates);
          totalAggregates += saved;
        }
      }
      
      console.log(`[EdgeRebuild] Total aggregates saved: ${totalAggregates}`);
      
      // Complete run
      await this.storage.completeRun(run.runId, {
        status: 'SUCCESS',
        rowsProcessed: rows.length,
        aggregatesCreated: totalAggregates,
        globalBaseline,
      });
      
      const duration = Date.now() - startTime;
      console.log(`[EdgeRebuild] Completed in ${duration}ms`);
      
      return {
        edgeRunId: run.runId,
        status: 'SUCCESS',
        rowsProcessed: rows.length,
        aggregatesCreated: totalAggregates,
        duration,
      };
      
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      console.error('[EdgeRebuild] Error:', errorMsg);
      errors.push(errorMsg);
      
      // Mark run as failed
      await this.storage.completeRun(run.runId, {
        status: 'FAILED',
        rowsProcessed: 0,
        aggregatesCreated: 0,
        errors,
      });
      
      return {
        edgeRunId: run.runId,
        status: 'FAILED',
        rowsProcessed: 0,
        aggregatesCreated: 0,
        duration: Date.now() - startTime,
        errors,
      };
    }
  }

  /**
   * Get job status
   */
  async getStatus(): Promise<{
    lastRun: any | null;
    isRunning: boolean;
    latestGlobalBaseline: GlobalBaseline | null;
  }> {
    const latestRun = await this.storage.getLatestRun();
    const runningRun = await this.storage.getRun(''); // Check for running
    
    // Check if any run is in progress
    const runs = await this.storage.listRuns(1);
    const isRunning = runs.length > 0 && runs[0].status === 'RUNNING';
    
    const baseline = await this.storage.getLatestGlobalBaseline();
    
    return {
      lastRun: latestRun,
      isRunning,
      latestGlobalBaseline: baseline,
    };
  }
}

// Singleton
let jobInstance: EdgeRebuildJob | null = null;

export function getEdgeRebuildJob(db: Db): EdgeRebuildJob {
  if (!jobInstance) {
    jobInstance = new EdgeRebuildJob(db);
  }
  return jobInstance;
}
