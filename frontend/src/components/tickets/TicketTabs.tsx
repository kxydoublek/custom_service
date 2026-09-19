import type { TicketStatus } from '../../types/enums'
import { TICKET_STATUS_LABEL } from './ticketStatus'

const TABS: TicketStatus[] = ['pending', 'processing', 'closed']

interface TicketTabsProps {
  value: TicketStatus
  onChange: (status: TicketStatus) => void
}

export function TicketTabs({ value, onChange }: TicketTabsProps) {
  return (
    <div className="tabs" role="tablist" aria-label="工单状态">
      {TABS.map((status) => (
        <button
          key={status}
          type="button"
          role="tab"
          aria-selected={value === status}
          className={`tab ${value === status ? 'active' : ''}`}
          onClick={() => onChange(status)}
        >
          {TICKET_STATUS_LABEL[status]}
        </button>
      ))}
    </div>
  )
}
