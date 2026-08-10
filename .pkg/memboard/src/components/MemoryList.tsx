import { Button, Card } from '../ui';
import type { Conclusion } from '../types';
import styles from './MemoryList.module.css';

interface MemoryListProps {
  conclusions: Conclusion[];
  total: number;
  loading: boolean;
  searchActive: boolean;
  selectedSession: string | null;
  onDelete: (c: Conclusion) => void;
  onLoadMore: () => void;
  hasMore: boolean;
  error: string | null;
}

export function MemoryList({
  conclusions,
  total,
  loading,
  searchActive,
  selectedSession,
  onDelete,
  onLoadMore,
  hasMore,
  error,
}: MemoryListProps) {
  if (error) {
    return (
      <Card variant="bordered">
        <p className={styles.errorText}>[ ERROR ] {error}</p>
      </Card>
    );
  }

  if (loading && conclusions.length === 0) {
    return (
      <Card variant="flat">
        <p className={styles.emptyHint}>[ LOADING MEMORIES... ]</p>
      </Card>
    );
  }

  if (conclusions.length === 0) {
    return (
      <Card variant="flat">
        <div className={styles.empty}>
          {searchActive ? (
            <>
              <span className={styles.emptyPrimary}>No matches</span>
              <span className={styles.emptyHint}>
                Try a different query or clear the search.
              </span>
            </>
          ) : (
            <>
              <span className={styles.emptyPrimary}>No memories yet</span>
              <span className={styles.emptyHint}>
                Use <code>/honcho-remember</code> in Claude Code to start saving memories.
              </span>
            </>
          )}
        </div>
      </Card>
    );
  }

  const scopeLabel = searchActive
    ? selectedSession
      ? `Search results · "${selectedSession}"`
      : 'Search results'
    : selectedSession
      ? `Memories · "${selectedSession}"`
      : 'All memories';

  return (
    <div className={styles.list}>
      <div className={styles.header}>
        <span className={styles.scope}>{scopeLabel}</span>
        <span className={styles.count}>
          {conclusions.length}
          {total > conclusions.length ? ` / ${total}` : ''}
        </span>
      </div>

      {conclusions.map((c) => (
        <Card key={c.id} className={styles.card}>
          <div className={styles.content}>{c.content}</div>
          <div className={styles.meta}>
            <span className={styles.session} title="Session">
              {c.session_id}
            </span>
            <span className={styles.date}>{c.created_at?.slice(0, 10) ?? ''}</span>
            <span className={styles.metaSpacer} />
            <Button
              variant="ghost"
              compact
              onClick={() => onDelete(c)}
              title="Delete this memory"
            >
              Delete
            </Button>
          </div>
        </Card>
      ))}

      {hasMore && (
        <div className={styles.loadMore}>
          <Button variant="secondary" onClick={onLoadMore} disabled={loading}>
            {loading ? 'Loading...' : 'Load more'}
          </Button>
        </div>
      )}
    </div>
  );
}
