import { AxiosError } from 'axios'
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import api, { passthroughAdapter } from '../services/api'
import type { ApiEnvelope, Pagination } from '../types/api'
import type { ConversationDetail, ConversationSummary, MessagePublic } from '../types/dto'
import type { HandoffState, SourceType } from '../types/enums'
import { NO_KNOWLEDGE_TEXT, OUT_OF_SCOPE_TEXT, WAIT_HUMAN_TEXT } from '../types/enums'
import { MOCK_TOKEN } from './auth'
import { publish, subscribe } from './bus'
import { installTicketMocks } from './tickets'

const FAQ_ANSWER = '先检查账号是否锁定，再重试连接公司 VPN。'
const SMALL_TALK_ANSWER = '你好，我是内部智能客服，有 IT 问题可以直接问我。'
const KNOWLEDGE_ANSWER = '连接公司 VPN 前请确认网络正常，并使用公司下发的配置文件。'
const STREAM_CHAR_MS = 28

interface ConversationRecord {
  id: number
  title: string
  handoff_state: HandoffState
  messages: MessagePublic[]
  created_at: string
  updated_at: string
  generation_lock: boolean
}

interface StreamJob {
  conversationId: number
  afterUserMessageId: number
  source: SourceType
  fullText: string
  assistant: MessagePublic | null
  completed: boolean
}

interface PaginatedEnvelope<T> extends ApiEnvelope<T> {
  pagination: Pagination
}

const conversations = new Map<number, ConversationRecord>()
const streamJobs = new Map<string, StreamJob>()
let nextConversationId = 1
let nextMessageId = 1
let nextTicketId = 1

function nowIso(): string {
  return new Date().toISOString()
}

function jobKey(conversationId: number, afterUserMessageId: number): string {
  return `${conversationId}:${afterUserMessageId}`
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

function matchConversationPath(
  path: string,
):
  | { kind: 'collection' }
  | { kind: 'detail'; id: number }
  | { kind: 'messages'; id: number }
  | { kind: 'transfer'; id: number }
  | { kind: 'stream'; id: number }
  | null {
  const match = path.match(/\/conversations(?:\/(\d+)(?:\/(messages|transfer|assistant-stream))?)?$/)
  if (!match) return null
  const id = match[1] ? Number(match[1]) : null
  const tail = match[2]
  if (id == null) return { kind: 'collection' }
  if (tail === 'messages') return { kind: 'messages', id }
  if (tail === 'transfer') return { kind: 'transfer', id }
  if (tail === 'assistant-stream') return { kind: 'stream', id }
  return { kind: 'detail', id }
}

function isConversationJsonPath(path: string): boolean {
  const matched = matchConversationPath(path)
  return matched != null && matched.kind !== 'stream'
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

function requireAuth(
  config: InternalAxiosRequestConfig,
): Promise<never> | null {
  if (readBearer(config) === MOCK_TOKEN) return null
  return rejectEnvelope(config, 401, fail('请先登录', 'UNAUTHORIZED', 'req-conv-unauthorized'))
}

function makeMessage(role: MessagePublic['role'], content: string, source: SourceType | null): MessagePublic {
  const message: MessagePublic = {
    id: nextMessageId,
    role,
    content,
    source,
    created_at: nowIso(),
  }
  nextMessageId += 1
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    source: message.source,
    created_at: message.created_at,
  }
}

function toSummary(record: ConversationRecord): ConversationSummary {
  const last = record.messages[record.messages.length - 1]
  return {
    id: record.id,
    title: record.title,
    updated_at: record.updated_at,
    preview: last ? last.content.slice(0, 40) : '',
  }
}

function toDetail(record: ConversationRecord): ConversationDetail {
  return {
    id: record.id,
    title: record.title,
    handoff_state: record.handoff_state,
    messages: record.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      source: message.source,
      created_at: message.created_at,
    })),
    created_at: record.created_at,
    updated_at: record.updated_at,
  }
}

function cloneMessage(message: MessagePublic): MessagePublic {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    source: message.source,
    created_at: message.created_at,
  }
}

export function getConversationMessages(conversationId: number): MessagePublic[] {
  const record = conversations.get(conversationId)
  if (!record) return []
  return record.messages.map(cloneMessage)
}

export function applyHandoffState(conversationId: number, state: HandoffState): void {
  const record = conversations.get(conversationId)
  if (!record) return
  record.handoff_state = state
  record.updated_at = nowIso()
}

export function appendAgentMessage(conversationId: number, content: string): MessagePublic | null {
  const record = conversations.get(conversationId)
  if (!record) return null
  const message = makeMessage('agent', content, null)
  record.messages.push(message)
  record.updated_at = message.created_at
  return cloneMessage(message)
}

function absorbMessage(conversationId: number, message: MessagePublic): void {
  const record = conversations.get(conversationId)
  if (!record) return
  if (record.messages.some((item) => item.id === message.id)) return
  record.messages.push(cloneMessage(message))
  record.updated_at = message.created_at
}

function classifyReply(text: string): { source: SourceType; content: string } {
  const trimmed = text.trim()
  if (/vpn|认证失败/i.test(trimmed)) {
    return { source: 'faq', content: FAQ_ANSWER }
  }
  if (/天气|你好|哈哈|聊|早上好|谢谢/.test(trimmed)) {
    return { source: 'small_talk', content: SMALL_TALK_ANSWER }
  }
  if (
    /工单|办到哪|进度|我那张/.test(trimmed) ||
    /红烧肉|股票|请假|工资/.test(trimmed) ||
    trimmed.length < 4
  ) {
    return { source: 'knowledge_qa', content: OUT_OF_SCOPE_TEXT }
  }
  if (/photoshop|没见过的系统|没入库/i.test(trimmed)) {
    return { source: 'knowledge_qa', content: NO_KNOWLEDGE_TEXT }
  }
  return { source: 'knowledge_qa', content: KNOWLEDGE_ANSWER }
}

function assistantAfter(record: ConversationRecord, userMessageId: number): MessagePublic | null {
  const index = record.messages.findIndex((message) => message.id === userMessageId)
  if (index < 0) return null
  const next = record.messages[index + 1]
  if (next && next.role === 'assistant') return next
  return null
}

function finalizeJob(job: StreamJob): MessagePublic | null {
  if (job.completed && job.assistant) return job.assistant
  const record = conversations.get(job.conversationId)
  if (!record) return null
  const existing = assistantAfter(record, job.afterUserMessageId)
  if (existing) {
    job.assistant = {
      id: existing.id,
      role: existing.role,
      content: existing.content,
      source: existing.source,
      created_at: existing.created_at,
    }
    job.completed = true
    record.generation_lock = false
    return job.assistant
  }
  const assistant = makeMessage('assistant', job.fullText, job.source)
  const userIndex = record.messages.findIndex((message) => message.id === job.afterUserMessageId)
  if (userIndex >= 0) {
    record.messages.splice(userIndex + 1, 0, assistant)
  } else {
    record.messages.push(assistant)
  }
  record.updated_at = nowIso()
  record.generation_lock = false
  job.assistant = {
    id: assistant.id,
    role: assistant.role,
    content: assistant.content,
    source: assistant.source,
    created_at: assistant.created_at,
  }
  job.completed = true
  return job.assistant
}

function seedStore(): void {
  const created = '2026-09-12T07:10:00.000Z'
  const user = makeMessage('user', 'VPN 提示认证失败怎么办', null)
  user.created_at = created
  const assistant = makeMessage('assistant', FAQ_ANSWER, 'faq')
  assistant.created_at = '2026-09-12T07:10:01.000Z'
  const record: ConversationRecord = {
    id: nextConversationId,
    title: 'VPN 提示认证失败怎么办',
    handoff_state: 'none',
    messages: [user, assistant],
    created_at: created,
    updated_at: assistant.created_at,
    generation_lock: false,
  }
  nextConversationId += 1
  conversations.set(record.id, record)
}

seedStore()

let handoffSyncInstalled = false
function installConversationHandoffSync(): void {
  if (handoffSyncInstalled) return
  handoffSyncInstalled = true
  subscribe((event) => {
    if (event.event === 'ticket.accepted') {
      applyHandoffState(event.conversation_id, 'in_progress')
      return
    }
    if (event.event === 'ticket.closed') {
      applyHandoffState(event.conversation_id, 'none')
      return
    }
    if (event.event === 'message.created' && event.message.role === 'agent') {
      absorbMessage(event.conversation_id, event.message)
    }
  })
}
installConversationHandoffSync()

function createRecord(): ConversationRecord {
  const stamp = nowIso()
  const record: ConversationRecord = {
    id: nextConversationId,
    title: '新会话',
    handoff_state: 'none',
    messages: [],
    created_at: stamp,
    updated_at: stamp,
    generation_lock: false,
  }
  nextConversationId += 1
  conversations.set(record.id, record)
  return record
}

const conversationAdapter: AxiosAdapter = (config) => {
  if (readBearer(config) !== MOCK_TOKEN) {
    return passthroughAdapter(config)
  }
  const unauthorized = requireAuth(config)
  if (unauthorized) return unauthorized

  const path = pathOf(config)
  const method = (config.method ?? 'get').toLowerCase()
  const matched = matchConversationPath(path)
  if (!matched) {
    return Promise.reject(new Error(`Unhandled conversation mock: ${method} ${path}`))
  }

  if (method === 'post' && matched.kind === 'collection') {
    return Promise.resolve(jsonResponse(config, 200, ok(toDetail(createRecord()), 'req-conv-create')))
  }

  if (method === 'get' && matched.kind === 'collection') {
    const query = queryOf(config)
    const page = Math.max(1, Number(query.get('page') ?? 1))
    const pageSize = Math.min(50, Math.max(1, Number(query.get('page_size') ?? 20)))
    const sorted = [...conversations.values()].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
    const start = (page - 1) * pageSize
    const slice = sorted.slice(start, start + pageSize).map(toSummary)
    return Promise.resolve(
      jsonResponse(
        config,
        200,
        okPage(slice, { page, page_size: pageSize, total: sorted.length }, 'req-conv-list'),
      ),
    )
  }

  if (method === 'get' && matched.kind === 'detail') {
    const record = conversations.get(matched.id)
    if (!record) {
      return rejectEnvelope(config, 404, fail('会话不存在', 'NOT_FOUND', 'req-conv-missing'))
    }
    return Promise.resolve(jsonResponse(config, 200, ok(toDetail(record), 'req-conv-detail')))
  }

  if (method === 'post' && matched.kind === 'messages') {
    const record = conversations.get(matched.id)
    if (!record) {
      return rejectEnvelope(config, 404, fail('会话不存在', 'NOT_FOUND', 'req-msg-missing'))
    }
    const body = parseBody(config.data)
    const content = String(body.content ?? '').trim()
    if (!content) {
      return rejectEnvelope(config, 400, fail('请输入要发送的内容', 'VALIDATION_ERROR', 'req-msg-empty'))
    }
    if (content.length > 2000) {
      return rejectEnvelope(config, 400, fail('内容不能超过 2000 字', 'VALIDATION_ERROR', 'req-msg-long'))
    }

    const last = record.messages[record.messages.length - 1]
    if (
      last &&
      last.role === 'user' &&
      last.content === content &&
      !assistantAfter(record, last.id) &&
      record.handoff_state === 'none'
    ) {
      return Promise.resolve(
        jsonResponse(
          config,
          200,
          ok(
            {
              user_message: {
                id: last.id,
                role: last.role,
                content: last.content,
                source: last.source,
                created_at: last.created_at,
              },
              assistant_message: null,
              handoff_state: record.handoff_state,
              stream: true,
            },
            'req-msg-replay',
          ),
        ),
      )
    }

    if (record.generation_lock) {
      return rejectEnvelope(config, 409, fail('请等待当前回复结束', 'CONFLICT', 'req-msg-busy'))
    }

    const userMessage = makeMessage('user', content, null)
    record.messages.push(userMessage)
    if (record.messages.filter((message) => message.role === 'user').length === 1) {
      record.title = content.slice(0, 30)
    }
    record.updated_at = userMessage.created_at

    if (record.handoff_state === 'waiting' || record.handoff_state === 'in_progress') {
      publish({
        event: 'message.created',
        conversation_id: record.id,
        message: {
          id: userMessage.id,
          role: userMessage.role,
          content: userMessage.content,
          source: userMessage.source,
          created_at: userMessage.created_at,
        },
      })
      return Promise.resolve(
        jsonResponse(
          config,
          200,
          ok(
            {
              user_message: {
                id: userMessage.id,
                role: userMessage.role,
                content: userMessage.content,
                source: userMessage.source,
                created_at: userMessage.created_at,
              },
              assistant_message: null,
              handoff_state: record.handoff_state,
              stream: false,
            },
            'req-msg-human',
          ),
        ),
      )
    }

    const reply = classifyReply(content)
    record.generation_lock = true
    const job: StreamJob = {
      conversationId: record.id,
      afterUserMessageId: userMessage.id,
      source: reply.source,
      fullText: reply.content,
      assistant: null,
      completed: false,
    }
    streamJobs.set(jobKey(record.id, userMessage.id), job)
    window.setTimeout(() => {
      finalizeJob(job)
    }, Math.max(STREAM_CHAR_MS, reply.content.length * STREAM_CHAR_MS))

    return Promise.resolve(
      jsonResponse(
        config,
        200,
        ok(
          {
            user_message: {
              id: userMessage.id,
              role: userMessage.role,
              content: userMessage.content,
              source: userMessage.source,
              created_at: userMessage.created_at,
            },
            assistant_message: null,
            handoff_state: record.handoff_state,
            stream: true,
          },
          'req-msg-stream',
        ),
      ),
    )
  }

  if (method === 'post' && matched.kind === 'transfer') {
    const record = conversations.get(matched.id)
    if (!record) {
      return rejectEnvelope(config, 404, fail('会话不存在', 'NOT_FOUND', 'req-transfer-missing'))
    }
    if (record.handoff_state === 'waiting' || record.handoff_state === 'in_progress') {
      return rejectEnvelope(
        config,
        409,
        fail('当前已在等待或由人工处理', 'CONFLICT', 'req-transfer-conflict'),
      )
    }
    record.handoff_state = 'waiting'
    const waitMessage = makeMessage('system', WAIT_HUMAN_TEXT, null)
    record.messages.push(waitMessage)
    record.updated_at = waitMessage.created_at
    const ticketId = nextTicketId
    nextTicketId += 1
    const waitDto: MessagePublic = {
      id: waitMessage.id,
      role: waitMessage.role,
      content: waitMessage.content,
      source: waitMessage.source,
      created_at: waitMessage.created_at,
    }
    const firstUser = record.messages.find((message) => message.role === 'user')
    publish({
      event: 'ticket.created',
      ticket_id: ticketId,
      conversation_id: record.id,
      title: record.title,
      preview: (firstUser?.content ?? record.title).slice(0, 40),
    })
    publish({
      event: 'handoff.changed',
      conversation_id: record.id,
      handoff_state: 'waiting',
    })
    publish({
      event: 'message.created',
      conversation_id: record.id,
      message: waitDto,
    })
    return Promise.resolve(
      jsonResponse(
        config,
        200,
        ok({ handoff_state: 'waiting' as const, wait_message: waitDto }, 'req-transfer-1'),
      ),
    )
  }

  return Promise.reject(new Error(`Unhandled conversation mock: ${method} ${path}`))
}

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

function isAssistantStreamUrl(url: string): boolean {
  return /\/conversations\/\d+\/assistant-stream/.test(url)
}

function readFetchBearer(init?: RequestInit): string {
  const headers = init?.headers
  if (!headers) return ''
  if (headers instanceof Headers) {
    return (headers.get('Authorization') ?? '').replace(/^Bearer\s+/i, '')
  }
  if (Array.isArray(headers)) {
    const found = headers.find(([key]) => key.toLowerCase() === 'authorization')
    return String(found?.[1] ?? '').replace(/^Bearer\s+/i, '')
  }
  const record = headers as Record<string, string>
  return String(record.Authorization ?? record.authorization ?? '').replace(/^Bearer\s+/i, '')
}

function jsonErrorResponse(status: number, envelope: ApiEnvelope<null>): Response {
  return new Response(JSON.stringify(envelope), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function encodeSse(event: string, data: unknown): Uint8Array {
  return new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
}

async function mockAssistantStream(url: string, init?: RequestInit): Promise<Response> {
  if (readFetchBearer(init) !== MOCK_TOKEN) {
    return jsonErrorResponse(401, fail('请先登录', 'UNAUTHORIZED', 'req-sse-unauthorized'))
  }
  const parsed = new URL(url, 'http://local.invalid')
  const pathMatch = parsed.pathname.match(/\/conversations\/(\d+)\/assistant-stream/)
  const conversationId = pathMatch ? Number(pathMatch[1]) : NaN
  const afterUserMessageId = Number(parsed.searchParams.get('after_user_message_id'))
  const record = conversations.get(conversationId)
  if (!record || Number.isNaN(afterUserMessageId)) {
    return jsonErrorResponse(404, fail('无法继续回复', 'NOT_FOUND', 'req-sse-missing'))
  }
  const user = record.messages.find((message) => message.id === afterUserMessageId && message.role === 'user')
  if (!user) {
    return jsonErrorResponse(400, fail('无法继续回复', 'VALIDATION_ERROR', 'req-sse-user'))
  }

  const key = jobKey(conversationId, afterUserMessageId)
  let job = streamJobs.get(key)
  const existing = assistantAfter(record, afterUserMessageId)
  if (!job && existing) {
    job = {
      conversationId,
      afterUserMessageId,
      source: existing.source ?? 'knowledge_qa',
      fullText: existing.content,
      assistant: existing,
      completed: true,
    }
    streamJobs.set(key, job)
  }
  if (!job) {
    return jsonErrorResponse(409, fail('请等待当前回复结束', 'CONFLICT', 'req-sse-nojob'))
  }

  const replay = job.completed && job.assistant != null
  let aborted = init?.signal?.aborted ?? false
  init?.signal?.addEventListener('abort', () => {
    aborted = true
  })

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const source = job.source
      controller.enqueue(
        encodeSse('meta', {
          assistant_message_id: job.assistant?.id ?? null,
          source,
          handoff_state: record.handoff_state,
        }),
      )
      if (replay && job.assistant) {
        controller.enqueue(encodeSse('delta', { text: job.assistant.content }))
        controller.enqueue(encodeSse('done', { assistant_message: job.assistant }))
        controller.close()
        return
      }
      for (const char of job.fullText) {
        if (aborted) break
        controller.enqueue(encodeSse('delta', { text: char }))
        await new Promise((resolve) => {
          window.setTimeout(resolve, STREAM_CHAR_MS)
        })
      }
      const assistant = finalizeJob(job)
      if (!aborted && assistant) {
        controller.enqueue(encodeSse('done', { assistant_message: assistant }))
        controller.close()
      } else if (!aborted) {
        controller.enqueue(
          encodeSse('error', { error: '回复生成失败', error_code: 'INTERNAL_ERROR' }),
        )
        controller.close()
      } else {
        try {
          controller.close()
        } catch {
          // already cancelled
        }
      }
    },
    cancel() {
      aborted = true
    },
  })

  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

let installed = false

export function installConversationMocks(): void {
  if (installed) return
  installed = true
  api.interceptors.request.use((config) => {
    if (isConversationJsonPath(pathOf(config))) {
      config.adapter = conversationAdapter
    }
    return config
  })

  const originalFetch = window.fetch.bind(window)
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (isAssistantStreamUrl(urlOf(input)) && readFetchBearer(init) === MOCK_TOKEN) {
      return mockAssistantStream(urlOf(input), init)
    }
    return originalFetch(input, init)
  }
  installTicketMocks()
}
