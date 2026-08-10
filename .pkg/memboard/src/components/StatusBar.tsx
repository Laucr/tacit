import { Button } from '../ui';
import styles from './StatusBar.module.css';

interface StatusBarProps {
  healthy: boolean | null; // null = checking
  total: number;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSearchSubmit: () => void;
  onSearchClear: () => void;
  onRefresh: () => void;
  loading: boolean;
}

export function StatusBar({
  healthy,
  total,
  searchQuery,
  onSearchChange,
  onSearchSubmit,
  onSearchClear,
  onRefresh,
  loading,
}: StatusBarProps) {
  const healthCls = [
    styles.health,
    healthy === true && styles['health--up'],
    healthy === false && styles['health--down'],
  ]
    .filter(Boolean)
    .join(' ');

  const healthTitle =
    healthy === true
      ? 'Honcho is running'
      : healthy === false
        ? 'Honcho is not reachable'
        : 'Checking...';

  return (
    <header className={styles.statusBar}>
      <div className={styles.left}>
        <span className={styles.title}>MEMBOARD</span>
        <span className={healthCls} title={healthTitle} aria-label={healthTitle} />
        <span className={styles.count}>
          {total} {total === 1 ? 'memory' : 'memories'}
        </span>
      </div>

      <div className={styles.right}>
        <form
          className={styles.searchForm}
          onSubmit={(e) => {
            e.preventDefault();
            onSearchSubmit();
          }}
        >
          <div className={styles.searchField}>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search memories..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                className={styles.searchClear}
                onClick={() => {
                  onSearchClear();
                }}
                title="Clear search"
                aria-label="Clear search"
              >
                ×
              </button>
            )}
          </div>
          <Button type="submit" variant="primary" compact disabled={loading}>
            Search
          </Button>
        </form>
        <Button
          variant="ghost"
          compact
          onClick={onRefresh}
          disabled={loading}
          title="Refresh"
        >
          {loading ? '...' : 'Refresh'}
        </Button>
      </div>
    </header>
  );
}
