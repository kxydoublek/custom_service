import { useCallback, useEffect, useRef, useState } from 'react'
import { MessageBubble } from '../components/chat/MessageBubble'
import chat from '../components/chat/chat.module.css'
import { TicketComposer } from '../components/tickets/TicketComposer'
import { TicketList } from '../components/tickets/TicketList'
import { TicketTabs } from '../components/tickets/TicketTabs'
import { TICKET_STATUS_LABEL } from '../components/tickets/ticketStatus'
import {
  acceptTicket,
  closeTicket,
  getTicket,
  listTickets,
  replyTicket,
} from '../services/tickets'
import { connectRealtime, isMockSession } from '../services/ws'
import type { TicketDetail, TicketSummary } from '../types/dto'
import type { TicketStatus } from '../types/enums'
import { getApiErrorMessage } from '../utils/apiError'

export default function AgentPage() {
  const [filter, setFilter] = useState<TicketStatus>('pending')
  const [items, setItems] = useState<TicketSummary[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const messagesRef = useRef<HTMLDivElement>(null)
  const filterRef = useRef(filter)
  const activeIdRef = useRef<number | null>(null)

  filterRef.current = filter
  activeIdRef.current = detail?.id ?? null

  const scrollToBottom = useCallback(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [detail?.messages, scrollToBottom])

  const loadList = useCallback(async (status: TicketStatus) => {
    const envelope = await listTickets(status)
    if (!envelope.success || !envelope.data) {
      setError(envelope.error ?? '无法加载工单')
      setItems([])
      return
    }
    if (filterRef.current !== status) return
    const incoming = envelope.data
    setItems((current) => {
      if (status !== 'pending') return incoming
      const extras = current.filter(
        (item) => item.status === 'pending' && !incoming.some((row) => row.id === item.id),
      )
      return extras.length > 0 ? [...extras, ...incoming] : incoming
    })
  }, [])

  const openTicket = useCallback(async (ticketId: number) => {
    setError(null)
    const envelope = await getTicket(ticketId)
    if (!envelope.success || !envelope.data) {
      setError(envelope.error ?? '工单不存在')
      return
    }
    setDetail(envelope.data)
    setDraft('')
  }, [])

  useEffect(() => {
    let cancelled = false
    setListLoading(true)
    void loadList(filter)
      .catch((err) => {
        if (!cancelled) setError(getApiErrorMessage(err, '无法加载工单'))
      })
      .finally(() => {
        if (!cancelled) setListLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [filter, loadList])

  useEffect(() => {
    return connectRealtime((event) => {
      if (event.event === 'ticket.created') {
        const created: TicketSummary = {
          id: event.ticket_id,
          conversation_id: event.conversation_id,
          status: 'pending',
          title: event.title,
          preview: event.preview,
          created_at: new Date().toISOString(),
        }
        if (filterRef.current === 'pending') {
          setItems((list) => (list.some((item) => item.id === created.id) ? list : [created, ...list]))
          if (activeIdRef.current == null) {
            void openTicket(event.ticket_id)
          }
        }
        return
      }
      if (event.event === 'ticket.accepted') {
        if (filterRef.current === 'pending') {
          setItems((list) => list.filter((item) => item.id !== event.ticket_id))
        } else if (filterRef.current === 'processing') {
          void loadList('processing').catch(() => {
            // keep current snapshot
          })
        }
        if (activeIdRef.current === event.ticket_id) {
          void openTicket(event.ticket_id)
        }
        return
      }
      if (event.event === 'ticket.closed') {
        if (filterRef.current === 'processing') {
          setItems((list) => list.filter((item) => item.id !== event.ticket_id))
        } else if (filterRef.current === 'closed') {
          void loadList('closed').catch(() => {
            // keep current snapshot
          })
        }
        if (activeIdRef.current === event.ticket_id) {
          void openTicket(event.ticket_id)
        }
        return
      }
      if (event.event === 'message.created') {
        setDetail((current) => {
          if (!current || current.conversation_id !== event.conversation_id) return current
          if (current.messages.some((message) => message.id === event.message.id)) return current
          return {
            ...current,
            messages: [...current.messages, event.message],
            preview: event.message.content.slice(0, 40),
          }
        })
      }
    })
  }, [loadList, openTicket])

  async function handleAccept() {
    if (!detail || busy) return
    setBusy(true)
    setError(null)
    try {
      const envelope = await acceptTicket(detail.id)
      if (!envelope.success || !envelope.data) {
        setError(envelope.error ?? '无法接入')
        return
      }
      setFilter('processing')
      setDetail((current) =>
        current
          ? {
              ...current,
              status: 'processing',
              accepted_at: envelope.data?.accepted_at ?? current.accepted_at,
            }
          : current,
      )
      await openTicket(detail.id)
    } catch (err) {
      setError(getApiErrorMessage(err, '无法接入'))
    } finally {
      setBusy(false)
    }
  }

  async function handleReply() {
    const content = draft.trim()
    if (!detail || !content || busy) return
    setBusy(true)
    setError(null)
    try {
      const envelope = await replyTicket(detail.id, content)
      if (!envelope.success || !envelope.data) {
        setError(envelope.error ?? '不能回复')
        return
      }
      const message = envelope.data.agent_message
      setDraft('')
      setDetail((current) => {
        if (!current) return current
        if (current.messages.some((item) => item.id === message.id)) return current
        return {
          ...current,
          messages: [...current.messages, message],
          preview: message.content.slice(0, 40),
        }
      })
    } catch (err) {
      setError(getApiErrorMessage(err, '不能回复'))
    } finally {
      setBusy(false)
    }
  }

  async function handleClose() {
    if (!detail || busy) return
    setBusy(true)
    setError(null)
    try {
      const envelope = await closeTicket(detail.id)
      if (!envelope.success || !envelope.data) {
        setError(envelope.error ?? '已关闭')
        return
      }
      setFilter('closed')
      setDetail((current) =>
        current
          ? {
              ...current,
              status: 'closed',
              closed_at: envelope.data?.closed_at ?? current.closed_at,
            }
          : current,
      )
      await openTicket(detail.id)
    } catch (err) {
      setError(getApiErrorMessage(err, '已关闭'))
    } finally {
      setBusy(false)
    }
  }

  const title = detail
    ? `${detail.title} · ${TICKET_STATUS_LABEL[detail.status]}`
    : '选择一张工单'

  return (
    <div className={chat.page}>
      <aside className="side side-wide">
        <h2>工单</h2>
        <TicketTabs value={filter} onChange={setFilter} />
        <TicketList
          items={items}
          loading={listLoading}
          activeId={detail?.id ?? null}
          showMockMark={isMockSession()}
          onSelect={(id) => {
            void openTicket(id)
          }}
        />
      </aside>
      <section className="main">
        <div className="main-head">
          {title}
          {isMockSession() ? <span className={chat.mockMark}>[Mock]</span> : null}
        </div>
        <div className="messages" ref={messagesRef}>
          {!detail ? (
            <p className="empty">选择一张工单查看对话。</p>
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
        </div>
        {error ? (
          <div className="error-bar" role="alert">
            {error}
          </div>
        ) : null}
        <TicketComposer
          status={detail?.status ?? null}
          draft={draft}
          busy={busy}
          onChange={setDraft}
          onAccept={() => {
            void handleAccept()
          }}
          onReply={() => {
            void handleReply()
          }}
          onClose={() => {
            void handleClose()
          }}
        />
      </section>
    </div>
  )
}
