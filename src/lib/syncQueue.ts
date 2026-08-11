/**
 * Offline pick queue with ordered flush, delete-only-acknowledged entries, and safe retry.
 *
 * Behavior:
 * - Every swipe appends to the outbox synchronously (before any network call).
 * - Flush is idempotent and safe to retry.
 * - Only acknowledged picks are deleted from the queue.
 * - Flush happens on: reconnect, next-block request, sign-out.
 */

import { postPicks, RateLimitedError } from './api';

const STORAGE_KEY = 'babyname-swipe-v3';

export interface OutboxEntry {
  slot: number;
  name: string;
  verdict: 'keep' | 'no';
  decidedAt: string;  // ISO 8601
}

/**
 * Append a pick to the outbox synchronously.
 */
export function appendToOutbox(pick: OutboxEntry): void {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (!cached) return;

    const data = JSON.parse(cached);
    if (!data.outbox) {
      data.outbox = [];
    }

    data.outbox.push(pick);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (error) {
    console.error('Failed to append to outbox:', error);
  }
}

/**
 * Flush the outbox to the backend.
 * Returns { success: boolean, retryAfter?: number }.
 */
export async function flushOutbox(): Promise<{ success: boolean; retryAfter?: number }> {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (!cached) {
      return { success: true };
    }

    const data = JSON.parse(cached);
    const outbox: OutboxEntry[] = data.outbox || [];

    if (outbox.length === 0) {
      return { success: true };
    }

    // Batch picks (cap at 500 per request as per contract)
    const batchSize = 500;
    const batch = outbox.slice(0, batchSize);

    try {
      const response = await postPicks(batch);

      // Success — delete acknowledged picks from the outbox
      data.outbox = outbox.slice(response.accepted);

      // Update swiper positions from the response
      if (response.swipers && data.swipers) {
        response.swipers.forEach((serverSwiper) => {
          const localSwiper = data.swipers.find((s: any) => s.slot === serverSwiper.slot);
          if (localSwiper) {
            localSwiper.position = serverSwiper.position;
          }
        });
      }

      // Update syncedAt
      data.syncedAt = new Date().toISOString();

      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));

      return { success: true };
    } catch (error) {
      if (error instanceof RateLimitedError) {
        // Return retryAfter hint (client will show waiting state)
        return { success: false, retryAfter: error.retryAfter };
      }
      // Other errors — keep outbox intact, will retry later
      return { success: false };
    }
  } catch (error) {
    console.error('Failed to flush outbox:', error);
    return { success: false };
  }
}

/**
 * Get the current outbox size (for UI display).
 */
export function getOutboxSize(): number {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (!cached) return 0;

    const data = JSON.parse(cached);
    return (data.outbox || []).length;
  } catch {
    return 0;
  }
}

/**
 * Clear the outbox (used on sign-out after flush attempt).
 */
export function clearOutbox(): void {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (!cached) return;

    const data = JSON.parse(cached);
    data.outbox = [];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch (error) {
    console.error('Failed to clear outbox:', error);
  }
}
