import api from './api'
import { installConversationMocks } from '../mocks/conversations'
import type { ApiEnvelope, Pagination } from '../types/api'
import type { ConversationDetail, ConversationSummary, MessagePublic } from '../types/dto'
import type { HandoffState, SourceType } from '../types/enums'
import { getAccessToken } from '../utils/authStorage'

installConversationMocks()

export interface SendMessageData {
  user_message: MessagePublic
  assistant_message: MessagePublic | null
  handoff_state: HandoffState
  stream: boolean
}

export interface TransferData {
  handoff_state: 'waiting'
  wait_message: MessagePublic
}

export interface PaginatedEnvelope<T> extends ApiEnvelope<T> {
  pagination: Pagination
}

export interface AssistantStreamMeta {
  assistant_message_id: number | null
  source: SourceType
  handoff_state: HandoffState
}

export interface AssistantStreamHandlers {
  onMeta: (meta: AssistantStreamMeta) => void
  onDelta: (text: string) => void
  onDone: (message: MessagePublic) => void
  onError: (error: string) => void
}

export async function createConversation(): Promise<ApiEnvelope<ConversationDetail>> {
  const { data } = await api.post<ApiEnvelope<ConversationDetail>>('/conversations', {})
  return data
}

export async function listConversations(
  page = 1,
  pageSize = 20,
): Promise<PaginatedEnvelope<ConversationSummary[]>> {
  const { data } = await api.get<PaginatedEnvelope<ConversationSummary[]>>('/conversations', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function getConversation(
  conversationId: number,
): Promise<ApiEnvelope<ConversationDetail>> {
  const { data } = await api.get<ApiEnvelope<ConversationDetail>>(`/conversations/${conversationId}`)
  return data
}

export async function sendMessage(
  conversationId: number,
  content: string,
): Promise<ApiEnvelope<SendMessageData>> {
  const { data } = await api.post<ApiEnvelope<SendMessageData>>(
    `/conversations/${conversationId}/messages`,
    { content },
  )
  return data
}

export async function transferConversation(
  conversationId: number,
): Promise<ApiEnvelope<TransferData>> {
  const { data } = await api.post<ApiEnvelope<TransferData>>(
    `/conversations/${conversationId}/transfer`,
    {},
  )
  return data
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const rawLine of block.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (dataLines.length === 0) return null
  return { event, data: dataLines.join('\n') }
}

export async function openAssistantStream(
  conversationId: number,
  afterUserMessageId: number,
  handlers: AssistantStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const base = import.meta.env.VITE_API_BASE_URL || '/api'
  const token = getAccessToken()
  const response = await fetch(
    `${base}/conversations/${conversationId}/assistant-stream?after_user_message_id=${afterUserMessageId}`,
    {
      headers: {
        Authorization: token ? `Bearer ${token}` : '',
        Accept: 'text/event-stream',
      },
      signal,
    },
  )
  if (!response.ok) {
    let message = '无法继续回复'
    try {
      const envelope = (await response.json()) as ApiEnvelope<null>
      if (envelope.error) message = envelope.error
    } catch {
      // keep fallback
    }
    handlers.onError(message)
    return
  }
  if (!response.body) {
    handlers.onError('无法继续回复')
    return
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatchBlock = (part: string) => {
    const parsed = parseSseBlock(part)
    if (!parsed) return
    const payload = JSON.parse(parsed.data) as Record<string, unknown>
    if (parsed.event === 'meta') {
      handlers.onMeta({
        assistant_message_id: (payload.assistant_message_id as number | null) ?? null,
        source: payload.source as SourceType,
        handoff_state: payload.handoff_state as HandoffState,
      })
    } else if (parsed.event === 'delta') {
      handlers.onDelta(String(payload.text ?? ''))
    } else if (parsed.event === 'done') {
      handlers.onDone(payload.assistant_message as MessagePublic)
    } else if (parsed.event === 'error') {
      handlers.onError(String(payload.error ?? '回复生成失败'))
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) dispatchBlock(part)
  }
  buffer += decoder.decode()
  if (buffer.trim()) dispatchBlock(buffer)
}
