import { Card } from '../ui';
import type { Session } from '../types';
import styles from './SessionsSidebar.module.css';

interface SessionsSidebarProps {
  sessions: Session[];
  selected: string | null; // null = all sessions
  onSelect: (sessionId: string | null) => void;
  onWipeSession: (session: Session) => void;
}

export function SessionsSidebar({
  sessions,
  selected,
  onSelect,
  onWipeSession,
}: SessionsSidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <span className={styles.heading}>Sessions</span>
      <Card variant="bordered">
        <ul className={styles.list}>
          <li
            className={[
              styles.item,
              selected === null && styles['item--active'],
            ]
              .filter(Boolean)
              .join(' ')}
          >
            <button
              type="button"
              className={styles.itemButton}
              onClick={() => onSelect(null)}
            >
              <span className={styles.itemName}>All sessions</span>
            </button>
          </li>
          {sessions.map((s) => (
            <li
              key={s.id}
              className={[
                styles.item,
                selected === s.id && styles['item--active'],
              ]
                .filter(Boolean)
                .join(' ')}
            >
              <button
                type="button"
                className={styles.itemButton}
                onClick={() => onSelect(s.id)}
              >
                <span className={styles.itemName}>{s.id}</span>
                <span className={styles.itemDate}>
                  {s.created_at?.slice(0, 10) ?? ''}
                </span>
              </button>
              <button
                type="button"
                className={styles.wipe}
                onClick={(e) => {
                  e.stopPropagation();
                  onWipeSession(s);
                }}
                title={`Wipe all memories in "${s.id}"`}
                aria-label={`Wipe ${s.id}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        {sessions.length === 0 && (
          <p className={styles.empty}>
            No sessions yet. Use <code>/honcho-manage setup</code> to get started.
          </p>
        )}
      </Card>
    </aside>
  );
}
