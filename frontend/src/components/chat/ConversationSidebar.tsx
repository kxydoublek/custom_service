import type { ConversationSummary } from '../../types/dto'
import styles from './chat.module.css'

interface ConversationSidebarProps {
  items: ConversationSummary[]
  loading: boolean
  activeId: number | null
  showMockMark?: boolean
  onSelect: (id: number) => void
  onCreate: () => void
}

export function ConversationSidebar({
  items,
  loading,
  activeId,
  showMockMark = false,
  onSelect,
  onCreate,
}: ConversationSidebarProps) {
  return (
    <aside className="side">
      <div className={styles.sideHead}>
        <h2>历史会话</h2>
        <button className={`btn btn-secondary ${styles.newSession}`} type="button" onClick={onCreate}>
          新会话
        </button>
      </div>
      <div className="list">
        {loading ? (
          <>
            <div className={styles.skeleton} />
            <div className={styles.skeleton} />
            <div className={styles.skeleton} />
          </>
        ) : items.length === 0 ? (
          <p className="empty">还没有会话，在下方提问</p>
        ) : (
          items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`list-row ${styles.rowButton} ${item.id === activeId ? 'active' : ''}`}
              onClick={() => onSelect(item.id)}
            >
              <div className="title truncate">
                {showMockMark ? `[Mock] ${item.title}` : item.title}
              </div>
              <div className="meta truncate">{item.preview}</div>
            </button>
          ))
        )}
      </div>
    </aside>
  )
}
