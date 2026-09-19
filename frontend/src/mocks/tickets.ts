import { AxiosError } from 'axios'
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import api, { passthroughAdapter } from '../services/api'
import type { ApiEnvelope, Pagination } from '../types/api'
import type { TicketDetail, TicketSummary } from '../types/dto'
import type { TicketStatus } from '../types/enums'
import { MOCK_TOKEN } from './auth'
import { publish, subscribe } from './bus'
import { appendAgentMessage, getConversationMessages } from './conversations'

interface TicketRecord {
  id: number
  conversation_id: number
  status: TicketStatus
  title: string
  preview: string
  created_at: string
  accepted_at: string | null
  closed_at: string | null
}

interface PaginatedEnvelope<T> extends ApiEnvelope<T> {
  pagination: Pagination
}

const tickets = new Map<number, TicketRecord>()
const STATUSES: TicketStatus[] = ['pending', 'processing', 'closed']

function nowIso(): string {
  return new Date().toISOString()
}

function ok<T>(data: T, requestId: string): ApiEnvelope<T> {
  return {
    success: true,
    data,
    error: null,
    error_code: null,
    message: 'ok',
    timestamp: nowIso(),
    request_id: requestId,
    metadata: {},
  }
}

function okPage<T>(data: T, pagination: Pagination, requestId: string): PaginatedEnvelope<T> {
  return { ...ok(data, requestId), pagination }
}

function fail(error: string, errorCode: string, requestId: string): ApiEnvelope<null> {
  return {
    success: false,
    data: null,
    error,
    error_code: errorCode,
    message: null,
    timestamp: nowIso(),
    request_id: requestId,
    metadata: {},
  }
}

function pathOf(config: InternalAxiosRequestConfig): string {
  const url = config.url ?? ''
  const base = config.baseURL ?? ''
  const combined = url.startsWith('http') ? url : `${base}${url}`
  try {
    const parsed = combined.startsWith('http')
      ? new URL(combined)
      : new URL(combined, 'http://local.invalid')
    return parsed.pathname.replace(/\/+$/, '') || '/'
  } catch {
    return url.split('?')[0] ?? url
  }
}

function queryOf(config: InternalAxiosRequestConfig): URLSearchParams {
  const url = config.url ?? ''
  const qIndex = url.indexOf('?')
  const params = new URLSearchParams(qIndex >= 0 ? url.slice(qIndex + 1) : '')
  const extra = config.params as Record<string, unknown> | undefined
  if (extra) {
    Object.entries(extra).forEach(([key, value]) => {
      if (value != null) params.set(key, String(value))
    })
  }
  return params
}

function matchTicketPath(
  path: string,
):
  | { kind: 'collection' }
  | { kind: 'detail'; id: number }
  | { kind: 'accept'; id: number }
  | { kind: 'messages'; id: number }
  | { kind: 'close'; id: number }
  | null {
  const match = path.match(/\/tickets(?:\/(\d+)(?:\/(accept|messages|close))?)?$/)
  if (!match) return null
  const id = match[1] ? Number(match[1]) : null
  const tail = match[2]
  if (id == null) return { kind: 'collection' }
  if (tail === 'accept') return { kind: 'accept', id }
  if (tail === 'messages') return { kind: 'messages', id }
  if (tail === 'close') return { kind: 'close', id }
  return { kind: 'detail', id }
}

function isTicketPath(path: string): boolean {
  return matchTicketPath(path) != null
}

function jsonResponse<T>(
  config: InternalAxiosRequestConfig,
  status: number,
  data: T,
): AxiosResponse<T> {
  return {
    data,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: { 'content-type': 'application/json' },
    config,
  }
}

function rejectEnvelope(
  config: InternalAxiosRequestConfig,
  status: number,
  data: ApiEnvelope<null>,
): Promise<never> {
  return Promise.reject(
    new AxiosError(
      data.error ?? 'Error',
      AxiosError.ERR_BAD_REQUEST,
      config,
      undefined,
      jsonResponse(config, status, data),
    ),
  )
}

function parseBody(data: unknown): Record<string, unknown> {
  if (typeof data === 'string' && data.length > 0) {
    return JSON.parse(data) as Record<string, unknown>
  }
  if (data && typeof data === 'object') {
    return data as Record<string, unknown>
  }
  return {}
}

function readBearer(config: InternalAxiosRequestConfig): string {
  const raw = config.headers.Authorization ?? config.headers.authorization ?? ''
  return String(raw).replace(/^Bearer\s+/i, '')
}

function requireAuth(config: InternalAxiosRequestConfig): Promise<never> | null {
  if (readBearer(config) === MOCK_TOKEN) return null
  return rejectEnvelope(config, 401, fail('请先登录', 'UNAUTHORIZED', 'req-ticket-unauthorized'))
}

function toSummary(record: TicketRecord): TicketSummary {
  return {
    id: record.id,
    conversation_id: record.conversation_id,
    status: record.status,
    title: record.title,
    preview: record.preview,
    created_at: record.created_at,
  }
}

function toDetail(record: TicketRecord): TicketDetail {
  return {
    ...toSummary(record),
    messages: getConversationMessages(record.conversation_id),
    accepted_at: record.accepted_at,
    closed_at: record.closed_at,
  }
}

function rememberCreated(payload: {
  ticket_id: number
  conversation_id: number
  title: string
  preview: string
}): void {
  if (tickets.has(payload.ticket_id)) return
  const open = [...tickets.values()].find(
    (item) =>
      item.conversation_id === payload.conversation_id &&
      (item.status === 'pending' || item.status === 'processing'),
  )
  if (open) return
  tickets.set(payload.ticket_id, {
    id: payload.ticket_id,
    conversation_id: payload.conversation_id,
    status: 'pending',
    title: payload.title,
    preview: payload.preview,
    created_at: nowIso(),
    accepted_at: null,
    closed_at: null,
  })
}

const ticketAdapter: AxiosAdapter = (config) => {
  if (readBearer(config) !== MOCK_TOKEN) {
    return passthroughAdapter(config)
  }
  const unauthorized = requireAuth(config)
  if (unauthorized) return unauthorized

  const path = pathOf(config)
  const method = (config.method ?? 'get').toLowerCase()
  const matched = matchTicketPath(path)
  if (!matched) {
    return Promise.reject(new Error(`Unhandled ticket mock: ${method} ${path}`))
  }

  if (method === 'get' && matched.kind === 'collection') {
    const query = queryOf(config)
    const statusRaw = query.get('status')
    if (statusRaw && !STATUSES.includes(statusRaw as TicketStatus)) {
      return rejectEnvelope(config, 400, fail('状态不正确', 'VALIDATION_ERROR', 'req-ticket-status'))
    }
    const status = statusRaw as TicketStatus | null
    const page = Math.max(1, Number(query.get('page') ?? 1))
    const pageSize = Math.min(50, Math.max(1, Number(query.get('page_size') ?? 20)))
    const sorted = [...tickets.values()]
      .filter((item) => (status ? item.status === status : true))
      .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    const start = (page - 1) * pageSize
    const slice = sorted.slice(start, start + pageSize).map(toSummary)
    return Promise.resolve(
      jsonResponse(
        config,
        200,
        okPage(slice, { page, page_size: pageSize, total: sorted.length }, 'req-ticket-list'),
      ),
    )
  }

  if (method === 'get' && matched.kind === 'detail') {
    const record = tickets.get(matched.id)
    if (!record) {
      return rejectEnvelope(config, 404, fail('工单不存在', 'NOT_FOUND', 'req-ticket-missing'))
    }
    return Promise.resolve(jsonResponse(config, 200, ok(toDetail(record), 'req-ticket-detail')))
  }

  if (method === 'post' && matched.kind === 'accept') {
    const record = tickets.get(matched.id)
    if (!record) {
      return rejectEnvelope(config, 404, fail('工单不存在', 'NOT_FOUND', 'req-ticket-accept-missing'))
    }
    if (record.status !== 'pending') {
      return rejectEnvelope(config, 409, fail('无法接入', 'CONFLICT', 'req-ticket-accept-conflict'))
    }
    record.status = 'processing'
    record.accepted_at = nowIso()
    publish({
      event: 'ticket.accepted',
      ticket_id: record.id,
      conversation_id: record.conversation_id,
    })
    publish({
      event: 'handoff.changed',
      conversation_id: record.conversation_id,
      handoff_state: 'in_progress',
    })
    return Promise.resolve(
      jsonResponse(
        config,
        200,
        ok(
          { id: record.id, status: 'processing' as const, accepted_at: record.accepted_at },
          'req-ticket-accept',
        ),
      ),
    )
  }

  if (method === 'post' && matched.kind === 'messages') {
    const record = tickets.get(matched.id)
    if (!record) {
      return rejectEnvelope(config, 404, fail('工单不存在', 'NOT_FOUND', 'req-ticket-msg-missing'))
    }
    if (record.status !== 'processing') {
      return rejectEnvelope(config, 409, fail('不能回复', 'CONFLICT', 'req-ticket-msg-conflict'))
    }
    const body = parseBody(config.data)
    const content = String(body.content ?? '').trim()
    if (!content) {
      return rejectEnvelope(config, 400, fail('请输入要发送的内容', 'VALIDATION_ERROR', 'req-ticket-msg-empty'))
    }
    if (content.length > 2000) {
      return rejectEnvelope(config, 400, fail('内容不能超过 2000 字', 'VALIDATION_ERROR', 'req-ticket-msg-long'))
    }
    const agentMessage = appendAgentMessage(record.conversation_id, content)
    if (!agentMessage) {
      return rejectEnvelope(config, 404, fail('工单不存在', 'NOT_FOUND', 'req-ticket-msg-conv'))
    }
    record.preview = content.slice(0, 40)
    publish({
      event: 'message.created',
      conversation_id: record.conversation_id,
      message: {
        id: agentMessage.id,
        role: agentMessage.role,
        content: agentMessage.content,
        source: agentMessage.source,
        created_at: agentMessage.created_at,
      },
    })
    return Promise.resolve(
      jsonResponse(
        config,
        200,
        ok(
          {
            agent_message: {
              id: agentMessage.id,
              role: agentMessage.role,
              content: agentMessage.content,
              source: agentMessage.source,
              created_at: agentMessage.created_at,
            },
          },
          'req-ticket-reply',
        ),
      ),
    )
  }

  if (method === 'post' && matched.kind === 'close') {
    const record = tickets.get(matched.id)
    if (!record) {
      return rejectEnvelope(config, 404, fail('工单不存在', 'NOT_FOUND', 'req-ticket-close-missing'))
    }
    if (record.status === 'closed') {
      return rejectEnvelope(config, 409, fail('已关闭', 'CONFLICT', 'req-ticket-close-closed'))
    }
    if (record.status !== 'processing') {
      return rejectEnvelope(config, 409, fail('已关闭', 'CONFLICT', 'req-ticket-close-conflict'))
    }
    record.status = 'closed'
    record.closed_at = nowIso()
    publish({
      event: 'ticket.closed',
      ticket_id: record.id,
      conversation_id: record.conversation_id,
    })
    publish({
      event: 'handoff.changed',
      conversation_id: record.conversation_id,
      handoff_state: 'none',
    })
    return Promise.resolve(
      jsonResponse(
        config,
        200,
        ok(
          { id: record.id, status: 'closed' as const, closed_at: record.closed_at },
          'req-ticket-close',
        ),
      ),
    )
  }

  return Promise.reject(new Error(`Unhandled ticket mock: ${method} ${path}`))
}

let installed = false

export function installTicketMocks(): void {
  if (installed) return
  installed = true
  subscribe((event) => {
    if (event.event === 'ticket.created') {
      rememberCreated(event)
    }
  })
  api.interceptors.request.use((config) => {
    if (isTicketPath(pathOf(config))) {
      config.adapter = ticketAdapter
    }
    return config
  })
}
