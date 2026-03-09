/**
 * Phase 8.5 — Lock Service
 * 
 * Distributed lock using MongoDB for job coordination
 * Prevents multiple instances from running the same job
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';

const COLLECTION_NAME = 'ta_job_locks';

export interface LockService {
  acquire(lockKey: string, ttlMs: number): Promise<boolean>;
  release(lockKey: string): Promise<boolean>;
  extend(lockKey: string, ttlMs: number): Promise<boolean>;
  isLocked(lockKey: string): Promise<boolean>;
  getActiveLocks(): Promise<{ lockKey: string; ownerId: string; expiresAt: Date }[]>;
}

export function createLockService(db: Db, ownerId?: string): LockService {
  const collection: Collection = db.collection(COLLECTION_NAME);
  const instanceId = ownerId || uuidv4();

  return {
    /**
     * Acquire lock with TTL
     * Returns true if lock acquired, false if already held
     */
    async acquire(lockKey: string, ttlMs: number): Promise<boolean> {
      const now = new Date();
      const expiresAt = new Date(now.getTime() + ttlMs);

      try {
        // Try to insert new lock or update expired one
        const result = await collection.findOneAndUpdate(
          {
            _id: lockKey,
            $or: [
              { expiresAt: { $lt: now } },  // expired
              { ownerId: instanceId },       // already owns
            ],
          },
          {
            $set: {
              ownerId: instanceId,
              expiresAt,
              updatedAt: now,
            },
            $setOnInsert: {
              _id: lockKey,
            },
          },
          { 
            upsert: true, 
            returnDocument: 'after' 
          }
        );

        // Check if we own the lock
        return result?.ownerId === instanceId;
      } catch (err: any) {
        // Duplicate key = someone else got the lock
        if (err.code === 11000) {
          return false;
        }
        throw err;
      }
    },

    /**
     * Release lock
     */
    async release(lockKey: string): Promise<boolean> {
      const result = await collection.deleteOne({
        _id: lockKey,
        ownerId: instanceId,
      });
      return result.deletedCount > 0;
    },

    /**
     * Extend lock TTL
     */
    async extend(lockKey: string, ttlMs: number): Promise<boolean> {
      const now = new Date();
      const expiresAt = new Date(now.getTime() + ttlMs);

      const result = await collection.updateOne(
        {
          _id: lockKey,
          ownerId: instanceId,
        },
        {
          $set: {
            expiresAt,
            updatedAt: now,
          },
        }
      );

      return result.modifiedCount > 0;
    },

    /**
     * Check if lock is held (by anyone)
     */
    async isLocked(lockKey: string): Promise<boolean> {
      const now = new Date();
      const lock = await collection.findOne({
        _id: lockKey,
        expiresAt: { $gt: now },
      });
      return lock !== null;
    },

    /**
     * Get all active (non-expired) locks
     */
    async getActiveLocks(): Promise<{ lockKey: string; ownerId: string; expiresAt: Date }[]> {
      const now = new Date();
      const locks = await collection
        .find({ expiresAt: { $gt: now } })
        .toArray();

      return locks.map(l => ({
        lockKey: l._id as string,
        ownerId: l.ownerId,
        expiresAt: l.expiresAt,
      }));
    },
  };
}

/**
 * Create TTL index for automatic lock cleanup
 */
export async function createLockIndexes(db: Db): Promise<void> {
  const collection = db.collection(COLLECTION_NAME);
  
  // TTL index - MongoDB will automatically delete expired locks
  await collection.createIndex(
    { expiresAt: 1 },
    { expireAfterSeconds: 0 }  // delete immediately after expiry
  );

  console.log('[LockService] Indexes created');
}
