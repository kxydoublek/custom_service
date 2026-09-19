import type { TicketStatus } from '../../types/enums'

export const TICKET_STATUS_LABEL: Record<TicketStatus, string> = {
  pending: '待接入',
  processing: '处理中',
  closed: '关闭',
}

export function ticketDotClass(status: TicketStatus): string {
  return status === 'closed' ? 'dot-success' : 'dot-warning'
}
