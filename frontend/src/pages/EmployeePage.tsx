import { useCallback, useEffect, useRef, useState } from 'react'
import { Composer } from '../components/chat/Composer'
import { ConversationSidebar } from '../components/chat/ConversationSidebar'
import { MessageBubble } from '../components/chat/MessageBubble'
import { WaitBanner } from '../components/chat/WaitBanner'
import styles from '../components/chat/chat.module.css'
import {
  createConversation,
  getConversation,
  listConversations,
  openAssistantStream,
  sendMessage,
  transferConversation,
} from '../services/conversations'
import { connectRealtime, isMockSession } from '../services/ws'
import type { ConversationDetail, ConversationSummary, MessagePublic } from '../types/dto'
import type { HandoffState, SourceType } from '../types/enums'
import { getApiErrorMessage } from '../utils/apiError'

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = () => setReduced(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return reduced
}

function upsertSummary(items: ConversationSummary[], next: ConversationSummary): ConversationSummary[] {
  const others = items.filter((item) => item.id !== next.id)
  return [next, ...others].sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))
}

function summaryFromDetail(detail: ConversationDetail, preview: string): ConversationSummary {
  return {
    id: detail.id,
    title: detail.title,
    updated_at: detail.updated_at,
    preview,
  }
}

export default function EmployeePage() {
  const reducedMotion = usePrefersReducedMotion()
  const [items, setItems] = useState<ConversationSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [detail, setDetail] = useState<ConversationDetail | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [streaming, setStreaming] = useState<{ source: SourceType; text: string } | null>(null)
  const messagesRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const detailRef = useRef<ConversationDetail | null>(null)
  const reducedRef = useRef(reducedMotion)

  detailRef.current = detail
  reducedRef.current = reducedMotion

  const scrollToBottom = useCallback(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [detail?.messages, streaming, scrollToBottom])

  const abortStream = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStreaming(null)
  }, [])

  const startStream = useCallback(async (conversationId: number, afterUserMessageId: number) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setBusy(true)
    setStreaming(null)
    try {
      await openAssistantStream(
        conversationId,
        afterUserMessageId,
        {
          onMeta: (meta) => {
            setStreaming({ source: meta.source, text: '' })
          },
          onDelta: (text) => {
            if (!reducedRef.current) {
              setStreaming((current) => (current ? { ...current, text: current.text + text } : current))
            }
          },
          onDone: (message) => {
            setDetail((current) => {
              if (!current || current.id !== conversationId) return current
              const exists = current.messages.some((item) => item.id === message.id)
              const messages = exists ? current.messages : [...current.messages, message]
              const next = {
                ...current,
                messages,
                updated_at: message.created_at,
              }
              setItems((list) => upsertSummary(list, summaryFromDetail(next, message.content)))
              return next
            })
            setStreaming(null)
            setBusy(false)
          },
          onError: (message) => {
            setError(message)
            setStreaming(null)
            setBusy(false)
          },
        },
        controller.signal,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      setError(getApiErrorMessage(err, '无法继续回复'))
      setStreaming(null)
      setBusy(false)
    }
  }, [])

  const openConversation = useCallback(
    async (conversationId: number) => {
      abortStream()
      setBusy(false)
      setError(null)
      const envelope = await getConversation(conversationId)
      if (!envelope.success || !envelope.data) {
        setError(envelope.error ?? '会话不存在')
        return
      }
      setDetail(envelope.data)
      const messages = envelope.data.messages
      const last = messages[messages.length - 1]
      if (envelope.data.handoff_state === 'none' && last?.role === 'user') {
        void startStream(conversationId, last.id)
      }
    },
    [abortStream, startStream],
  )

  useEffect(() => {
    let cancelled = false
    async function boot() {
      try {
        const envelope = await listConversations()
        if (cancelled) return
        if (envelope.success && envelope.data) {
          setItems(envelope.data)
          if (envelope.data[0]) void openConversation(envelope.data[0].id)
        }
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err, '无法加载会话'))
      } finally {
        if (!cancelled) setListLoading(false)
      }
    }
    void boot()
    return () => {
      cancelled = true
      abortRef.current?.abort()
    }
  }, [openConversation])

  useEffect(() => {
    return connectRealtime((event) => {
      if (event.event === 'handoff.changed') {
        const current = detailRef.current
        if (!current || event.conversation_id !== current.id) return
        if (event.handoff_state === 'waiting' || event.handoff_state === 'in_progress') {
          abortStream()
          setBusy(false)
        }
        setDetail((prev) => (prev ? { ...prev, handoff_state: event.handoff_state } : prev))
        return
      }
      if (event.event !== 'message.created') return
      const incoming = event.message
      setItems((list) => {
        const existing = list.find((item) => item.id === event.conversation_id)
        if (!existing) return list
        return upsertSummary(list, {
          ...existing,
          preview: incoming.content,
          updated_at: incoming.created_at,
        })
      })
      setDetail((prev) => {
        if (!prev || prev.id !== event.conversation_id) return prev
        if (prev.messages.some((message) => message.id === incoming.id)) return prev
        return {
          ...prev,
          messages: [...prev.messages, incoming],
          updated_at: incoming.created_at,
        }
      })
    })
  }, [abortStream])

  async function handleCreate() {
    setError(null)
    abortStream()
    setBusy(true)
    try {
      const envelope = await createConversation()
      if (!envelope.success || !envelope.data) {
        setError(envelope.error ?? '无法新建会话')
        return
      }
      setDetail(envelope.data)
      setItems((list) => upsertSummary(list, summaryFromDetail(envelope.data as ConversationDetail, '')))
    } catch (err) {
      setError(getApiErrorMessage(err, '无法新建会话'))
    } finally {
      setBusy(false)
    }
  }

  async function handleSend() {
    const content = draft.trim()
    if (!content || busy) return
    setError(null)
    setBusy(true)
    try {
      let current = detail
      if (!current) {
        const created = await createConversation()
        if (!created.success || !created.data) {
          setError(created.error ?? '无法新建会话')
          setBusy(false)
          return
        }
        current = created.data
        setDetail(current)
        setItems((list) => upsertSummary(list, summaryFromDetail(current as ConversationDetail, '')))
      }
      const envelope = await sendMessage(current.id, content)
      if (!envelope.success || !envelope.data) {
        setError(envelope.error ?? '发送失败')
        setBusy(false)
        return
      }
      const userMessage = envelope.data.user_message
      setDraft('')
      setDetail((prev) => {
        const base = prev ?? current
        const exists = base.messages.some((message) => message.id === userMessage.id)
        const messages = exists ? base.messages : [...base.messages, userMessage]
        const next: ConversationDetail = {
          ...base,
          title: messages.filter((message) => message.role === 'user').length === 1
            ? userMessage.content.slice(0, 30)
            : base.title,
          messages,
          handoff_state: envelope.data?.handoff_state ?? base.handoff_state,
          updated_at: userMessage.created_at,
        }
        setItems((list) => upsertSummary(list, summaryFromDetail(next, userMessage.content)))
        return next
      })
      if (envelope.data.stream) {
        void startStream(current.id, userMessage.id)
      } else {
        setBusy(false)
      }
    } catch (err) {
      setError(getApiErrorMessage(err, '发送失败'))
      setBusy(false)
    }
  }

  async function handleTransfer() {
    if (!detail) return
    const handoff: HandoffState = detail.handoff_state
    if (busy || handoff === 'waiting' || handoff === 'in_progress') return
    abortStream()
    setError(null)
    try {
      const envelope = await transferConversation(detail.id)
      if (!envelope.success || !envelope.data) {
        setError(envelope.error ?? '转人工失败')
        return
      }
      const waitMessage: MessagePublic = envelope.data.wait_message
      setDetail((prev) => {
        if (!prev) return prev
        const exists = prev.messages.some((message) => message.id === waitMessage.id)
        const next = {
          ...prev,
          handoff_state: envelope.data?.handoff_state ?? 'waiting',
          messages: exists ? prev.messages : [...prev.messages, waitMessage],
          updated_at: waitMessage.created_at,
        }
        setItems((list) => upsertSummary(list, summaryFromDetail(next, waitMessage.content)))
        return next
      })
    } catch (err) {
      setError(getApiErrorMessage(err, '转人工失败'))
    }
  }

  const handoffState = detail?.handoff_state ?? 'none'

  return (
    <div className={styles.page}>
      <ConversationSidebar
        items={items}
        loading={listLoading}
        activeId={detail?.id ?? null}
        showMockMark={isMockSession()}
        onSelect={(id) => {
          void openConversation(id)
        }}
        onCreate={() => {
          void handleCreate()
        }}
      />
      <section className="main">
        <div className="main-head">{detail?.title ?? '会话'}</div>
        <div className="messages" ref={messagesRef}>
          {!detail || detail.messages.length === 0 ? (
            <p className="empty">还没有会话，在下方提问</p>
          ) : (
            detail.messages.map((message) => (
              <MessageBubble
                key={message.id}
                role={message.role}
                content={message.content}
                source={message.source}
              />
            ))
          )}
          {streaming ? (
            <MessageBubble role="assistant" content={streaming.text} source={streaming.source} />
          ) : null}
        </div>
        {error ? (
          <div className="error-bar" role="alert">
            {error}
          </div>
        ) : null}
        <WaitBanner handoffState={handoffState} />
        <Composer
          value={draft}
          busy={busy}
          handoffState={handoffState}
          onChange={setDraft}
          onSend={() => {
            void handleSend()
          }}
          onTransfer={() => {
            void handleTransfer()
          }}
        />
      </section>
    </div>
  )
}
