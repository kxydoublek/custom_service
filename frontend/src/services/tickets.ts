import api from './api'
import { installTicketMocks } from '../mocks/tickets'
import type { ApiEnvelope, Pagination } from '../types/api'
import type { MessagePublic, TicketDetail, TicketSummary } from '../types/dto'
import type { TicketStatus } from '../types/enums'

installTicketMocks()

export interface PaginatedTickets extends ApiEnvelope<TicketSummary[]> {
  pagination: Pagination
}

export interface AcceptTicketData {
  id: number
  status: 'processing'
  accepted_at: string
}

export interface CloseTicketData {
  id: number
  status: 'closed'
  closed_at: string
}

export interface ReplyTicketData {
  agent_message: MessagePublic
}

export async function listTickets(
  status?: TicketStatus,
  page = 1,
  pageSize = 20,
): Promise<PaginatedTickets> {
  const { data } = await api.get<PaginatedTickets>('/tickets', {
    params: {
      page,
      page_size: pageSize,
      status,
    },
  })
  return data
}

export async function getTicket(ticketId: number): Promise<ApiEnvelope<TicketDetail>> {
  const { data } = await api.get<ApiEnvelope<TicketDetail>>(`/tickets/${ticketId}`)
  return data
}

export async function acceptTicket(ticketId: number): Promise<ApiEnvelope<AcceptTicketData>> {
  const { data } = await api.post<ApiEnvelope<AcceptTicketData>>(`/tickets/${ticketId}/accept`, {})
  return data
}

export async function replyTicket(
  ticketId: number,
  content: string,
): Promise<ApiEnvelope<ReplyTicketData>> {
  const { data } = await api.post<ApiEnvelope<ReplyTicketData>>(`/tickets/${ticketId}/messages`, {
    content,
  })
  return data
}

export async function closeTicket(ticketId: number): Promise<ApiEnvelope<CloseTicketData>> {
  const { data } = await api.post<ApiEnvelope<CloseTicketData>>(`/tickets/${ticketId}/close`, {})
  return data
}
