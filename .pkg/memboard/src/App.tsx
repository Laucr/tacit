import { useState, useEffect, useCallback } from 'react';
import type { Conclusion, Session } from './types';
import {
  checkHealth,
  listSessions,
  listConclusions,
  searchConclusions,
  deleteConclusion,
} from './api';
import { StatusBar } from './components/StatusBar';
import { SessionsSidebar } from './components/SessionsSidebar';
import { MemoryList } from './components/MemoryList';
import { ConfirmDialog } from './components/ConfirmDialog';

const PAGE_SIZE = 30;

export function App() {
  /* ── state ──────────────────────────────────────────── */
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  const [conclusions, setConclusions] = useState<Conclusion[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  const [searchQuery, setSearchQuery] = useState('');
  const [activeSearch, setActiveSearch] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [confirmTarget, setConfirmTarget] = useState<
    | { type: 'memory'; conclusion: Conclusion }
    | { type: 'session'; session: Session }
    | null
  >(null);

  /* ── data loading ───────────────────────────────────── */
  const loadData = useCallback(
    async (opts?: { search?: string; session?: string | null; reset?: boolean }) => {
      const search = opts?.search ?? activeSearch;
      const session = opts?.session !== undefined ? opts.session : selectedSession;
      const reset = opts?.reset ?? true;

      setLoading(true);
      setError(null);

      try {
        if (search) {
          const results = await searchConclusions({
            query: search,
            sessionId: session ?? undefined,
          });
          setConclusions(results);
          setTotal(results.length);
          setPage(1);
        } else {
          const result = await listConclusions({
            sessionId: session ?? undefined,
            size: reset ? PAGE_SIZE : PAGE_SIZE * (page + 1),
          });
          if (reset) {
            setConclusions(result.items ?? []);
            setPage(1);
          } else {
            setConclusions(result.items ?? []);
          }
          setTotal(result.total ?? (result.items?.length ?? 0));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load memories');
      } finally {
        setLoading(false);
      }
    },
    [activeSearch, selectedSession, page],
  );

  const loadMore = useCallback(async () => {
    const nextPage = page + 1;
    setLoading(true);
    try {
      const result = await listConclusions({
        sessionId: selectedSession ?? undefined,
        size: PAGE_SIZE * nextPage,
      });
      setConclusions(result.items ?? []);
      setTotal(result.total ?? (result.items?.length ?? 0));
      setPage(nextPage);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load more');
    } finally {
      setLoading(false);
    }
  }, [page, selectedSession]);

  const refresh = useCallback(async () => {
    const h = await checkHealth();
    setHealthy(h);
    if (h) {
      const sess = await listSessions();
      setSessions(sess);
      await loadData({ reset: true });
    }
  }, [loadData]);

  /* ── initial load ───────────────────────────────────── */
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ── session filter ─────────────────────────────────── */
  const handleSelectSession = useCallback(
    (sessionName: string | null) => {
      setSelectedSession(sessionName);
      loadData({ session: sessionName, reset: true });
    },
    [loadData],
  );

  /* ── search ─────────────────────────────────────────── */
  const handleSearchSubmit = useCallback(() => {
    setActiveSearch(searchQuery);
    loadData({ search: searchQuery, reset: true });
  }, [searchQuery, loadData]);

  const handleSearchClear = useCallback(() => {
    setSearchQuery('');
    setActiveSearch('');
    loadData({ search: '', reset: true });
  }, [loadData]);

  /* ── delete single ──────────────────────────────────── */
  const handleDeleteConfirm = useCallback(async () => {
    if (!confirmTarget) return;

    if (confirmTarget.type === 'memory') {
      try {
        await deleteConclusion(confirmTarget.conclusion.id);
        setConclusions((prev) =>
          prev.filter((c) => c.id !== confirmTarget.conclusion.id),
        );
        setTotal((prev) => Math.max(0, prev - 1));
      } catch (e) {
        setError(
          e instanceof Error ? e.message : 'Failed to delete memory',
        );
      }
    } else if (confirmTarget.type === 'session') {
      // Wipe all conclusions in the session
      try {
        setLoading(true);
        // The API caps pages at 100. Re-read page one after each batch because
        // deleting items changes pagination until the session is empty.
        while (true) {
          const result = await listConclusions({
            sessionId: confirmTarget.session.id,
            size: 100,
          });
          const items = result.items ?? [];
          if (items.length === 0) break;
          for (const c of items) {
            await deleteConclusion(c.id);
          }
        }
        // Refresh after wipe
        await loadData({ reset: true });
      } catch (e) {
        setError(
          e instanceof Error ? e.message : 'Failed to wipe session',
        );
      } finally {
        setLoading(false);
      }
    }

    setConfirmTarget(null);
  }, [confirmTarget, loadData]);

  /* ── render ─────────────────────────────────────────── */
  return (
    <div className="app">
      <StatusBar
        healthy={healthy}
        total={total}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
        onSearchClear={handleSearchClear}
        onRefresh={refresh}
        loading={loading}
      />

      {healthy === false && (
        <div className="connection-banner">
          Honcho is not reachable. Run <code>/honcho-manage setup</code> to start
          the sidecar.
        </div>
      )}

      <div className="app-layout">
        <SessionsSidebar
          sessions={sessions}
          selected={selectedSession}
          onSelect={handleSelectSession}
          onWipeSession={(s) => setConfirmTarget({ type: 'session', session: s })}
        />

        <main className="app-main">
          <MemoryList
            conclusions={conclusions}
            total={total}
            loading={loading}
            searchActive={!!activeSearch}
            selectedSession={selectedSession}
            onDelete={(c) => setConfirmTarget({ type: 'memory', conclusion: c })}
            onLoadMore={loadMore}
            hasMore={!activeSearch && conclusions.length < total}
            error={error}
          />
        </main>
      </div>

      {confirmTarget && (
        <ConfirmDialog
          message={
            confirmTarget.type === 'memory'
              ? 'Delete this memory?'
              : `Delete ALL memories in session "${confirmTarget.session.id}"?`
          }
          detail={
            confirmTarget.type === 'memory'
              ? confirmTarget.conclusion.content.slice(0, 120) +
                (confirmTarget.conclusion.content.length > 120 ? '...' : '')
              : 'This cannot be undone.'
          }
          confirmLabel={confirmTarget.type === 'memory' ? 'Delete' : 'Wipe session'}
          danger
          onConfirm={handleDeleteConfirm}
          onCancel={() => setConfirmTarget(null)}
        />
      )}
    </div>
  );
}
