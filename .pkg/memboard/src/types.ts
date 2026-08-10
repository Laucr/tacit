/* Honcho API data shapes — derived from the v3 REST responses */

export interface Conclusion {
  id: string;
  content: string;
  session_id: string;
  observer_id: string;
  observed_id: string;
  created_at: string; // ISO datetime
}

export interface Session {
  id: string;
  is_active: boolean;
  workspace_id: string;
  metadata: Record<string, unknown>;
  configuration: Record<string, unknown>;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface HealthStatus {
  status: string; // "ok" when healthy
}
