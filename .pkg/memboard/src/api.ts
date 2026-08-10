import type {
  Conclusion,
  Session,
  PaginatedResponse,
  HealthStatus,
} from './types';

/* ── Config ─────────────────────────────────────────────── */

const BASE = import.meta.env.VITE_HONCHO_BASE_URL || `${import.meta.env.BASE_URL}api`;
const WORKSPACE = import.meta.env.VITE_HONCHO_WORKSPACE || 'codex';
const OBSERVER = import.meta.env.VITE_HONCHO_OBSERVER || 'codex';
const OBSERVED = import.meta.env.VITE_HONCHO_OBSERVED || 'user';

/* ── Fetch wrapper ──────────────────────────────────────── */

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const text = await res.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const message =
      typeof data === 'object' && data !== null
        ? ('error' in data && String(data.error)) ||
          ('detail' in data && String(data.detail))
        : undefined;
    throw new Error(message || `HTTP ${res.status}`);
  }
  return data as T;
}

/* ── Health ──────────────────────────────────────────────── */

export async function checkHealth(): Promise<boolean> {
  try {
    const data = await fetchJSON<HealthStatus>(`${BASE}/health`);
    return data.status === 'ok';
  } catch {
    return false;
  }
}

/* ── Sessions ────────────────────────────────────────────── */

export async function listSessions(): Promise<Session[]> {
  const data = await fetchJSON<PaginatedResponse<Session>>(
    `${BASE}/v3/workspaces/${WORKSPACE}/sessions/list?size=50`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    },
  );
  return data.items ?? [];
}

/* ── Conclusions ─────────────────────────────────────────── */

export interface ListConclusionsOpts {
  sessionId?: string;
  page?: number;
  size?: number;
}

export async function listConclusions(
  opts: ListConclusionsOpts = {},
): Promise<PaginatedResponse<Conclusion>> {
  const size = opts.size ?? 30;
  const filters: Record<string, string> = {
    observer_id: OBSERVER,
    observed_id: OBSERVED,
  };
  if (opts.sessionId) {
    filters.session_id = opts.sessionId;
  }
  return fetchJSON<PaginatedResponse<Conclusion>>(
    `${BASE}/v3/workspaces/${WORKSPACE}/conclusions/list?size=${size}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filters }),
    },
  );
}

export interface SearchConclusionsOpts {
  query: string;
  sessionId?: string;
  topK?: number;
}

export async function searchConclusions(
  opts: SearchConclusionsOpts,
): Promise<Conclusion[]> {
  const filters: Record<string, string> = {
    observer: OBSERVER,
    observed: OBSERVED,
  };
  if (opts.sessionId) {
    filters.session_id = opts.sessionId;
  }
  const result = await fetchJSON<Conclusion[] | PaginatedResponse<Conclusion>>(
    `${BASE}/v3/workspaces/${WORKSPACE}/conclusions/query`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: opts.query,
        top_k: opts.topK ?? 20,
        filters,
      }),
    },
  );
  // The query endpoint returns an array directly
  return Array.isArray(result) ? result : result.items ?? [];
}

/* ── Delete ──────────────────────────────────────────────── */

export async function deleteConclusion(id: string): Promise<void> {
  await fetchJSON<unknown>(
    `${BASE}/v3/workspaces/${WORKSPACE}/conclusions/${id}`,
    { method: 'DELETE' },
  );
}
