import { supabase } from './auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Get authorization header with current session token
 */
async function getAuthHeaders(): Promise<HeadersInit> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  if (!token) {
    throw new Error('No active session');
  }

  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  };
}

/**
 * Account state types
 */
export interface AccountState {
  account: {
    lastName: string;
    genderFilter: string;
    onboarded: boolean;
  };
  swipers: Array<{
    slot: number;
    label: string;
    position: number;
  }>;
  picks: Array<{
    slot: number;
    name: string;
    verdict: string;
    decidedAt: string;  // ISO 8601, millisecond precision — same form we send back
  }>;
}

export interface SettingsData {
  lastName: string;
  genderFilter: string;
  onboarded: boolean;
  swiper0Label: string;
  swiper1Label: string;
}

/**
 * GET /v1/state - Fetch account state
 */
export async function getState(): Promise<AccountState> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/v1/state`, { headers });

  if (!response.ok) {
    throw new Error(`Failed to fetch state: ${response.statusText}`);
  }

  return response.json();
}

/**
 * PUT /v1/settings - Update account settings
 *
 * Returns the updated state, same shape as GET /v1/state.
 */
export async function putSettings(settings: SettingsData): Promise<AccountState> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/v1/settings`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(settings),
  });

  if (!response.ok) {
    throw new Error(`Failed to update settings: ${response.statusText}`);
  }

  return response.json();
}

/**
 * POST /v1/reset - Reset account data
 *
 * Returns the post-reset state, in the same shape as GET /v1/state, so callers
 * rehydrate the cache from the response instead of guessing what survived.
 */
export async function postReset(
  scope: 'everything' | 'swiper',
  slot?: number
): Promise<AccountState> {
  const headers = await getAuthHeaders();
  const body = scope === 'swiper' && slot !== undefined
    ? { scope, slot }
    : { scope };

  const response = await fetch(`${API_BASE_URL}/v1/reset`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Failed to reset: ${response.statusText}`);
  }

  return response.json();
}

/**
 * GET /health - Warm up the backend (fire and forget)
 */
export async function warmupBackend(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/health`, { method: 'GET' });
  } catch {
    // Silently ignore warmup failures per FR-030
  }
}

/**
 * Deck card shape
 */
export interface DeckCard {
  position: number;
  name: string;
  gender: string;
}

export interface DeckBlock {
  block: DeckCard[];
  exhausted: boolean;
}

/**
 * POST /v1/deck/next - Request the next block of names
 */
export async function requestNextBlock(slot: number, count: number): Promise<DeckBlock> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/v1/deck/next`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ slot, count }),
  });

  if (!response.ok) {
    throw new Error(`Failed to request next block: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Pick types for sync queue
 */
export interface PickItem {
  slot: number;
  name: string;
  verdict: 'keep' | 'no';
  decidedAt: string;  // ISO 8601
}

export interface PicksRequest {
  picks: PickItem[];
}

export interface SwiperPosition {
  slot: number;
  position: number;
}

export interface PicksResponse {
  accepted: number;
  swipers: SwiperPosition[];
}

/**
 * POST /v1/picks - Flush the offline outbox
 */
export async function postPicks(picks: PickItem[]): Promise<PicksResponse> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/v1/picks`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ picks }),
  });

  if (!response.ok) {
    if (response.status === 429) {
      const error = await response.json();
      throw new Error('rate_limited');
    }
    throw new Error(`Failed to post picks: ${response.statusText}`);
  }

  return response.json();
}
