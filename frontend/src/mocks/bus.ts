import type { HandoffState } from '../types/enums'
import type { MessagePublic } from '../types/dto'

export type BusEvent =
  | {
      event: 'document.progress'
      document_id: number
      status: string
      stage: string
      progress_percent: number
    }
  | { event: 'document.ready'; document_id: number }
  | { event: 'document.failed'; document_id: number; error_message: string }
  | {
      event: 'ticket.created'
      ticket_id: number
      conversation_id: number
      title: string
      preview: string
    }
  | { event: 'ticket.accepted'; ticket_id: number; conversation_id: number }
  | { event: 'ticket.closed'; ticket_id: number; conversation_id: number }
  | { event: 'message.created'; conversation_id: number; message: MessagePublic }
  | { event: 'handoff.changed'; conversation_id: number; handoff_state: HandoffState }

export type BusHandler = (event: BusEvent) => void

const listeners = new Set<BusHandler>()

export function publish(event: BusEvent): void {
  listeners.forEach((handler) => {
    handler(event)
  })
}

export function subscribe(handler: BusHandler): () => void {
  listeners.add(handler)
  return () => {
    listeners.delete(handler)
  }
}
