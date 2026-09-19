import type { TicketSummary } from '../../types/dto'
import chat from '../chat/chat.module.css'
import { TICKET_STATUS_LABEL, ticketDotClass } from './ticketStatus'

interface TicketListProps {
  items: TicketSummary[]
  loading: boolean
  activeId: number | null
  showMockMark?: boolean
  onSelect: (id: number) => void
}

export function TicketList({
  items,
  loading,
  activeId,
  showMockMark = false,
  onSelect,
}: TicketListProps) {
  return (
    <div className="list">
      {loading ? (
        <>
          <div className={chat.skeleton} />
          <div className={chat.skeleton} />
          <div className={chat.skeleton} />
        </>
      ) : items.length === 0 ? (
        <p className="empty">这个状态下没有工单。</p>
      ) : (
        items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`list-row ${chat.rowButton} ${item.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(item.id)}
          >
            <div className="title truncate">
              {showMockMark ? `[Mock] ${item.title}` : item.title}
            </div>
            <div className="meta">
              <span className={`status-dot ${ticketDotClass(item.status)}`} />
              {TICKET_STATUS_LABEL[item.status]}
            </div>
          </button>
        ))
      )}
    </div>
  )
}
