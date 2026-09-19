import type { FormEvent, KeyboardEvent } from 'react'
import type { TicketStatus } from '../../types/enums'
import chat from '../chat/chat.module.css'

interface TicketComposerProps {
  status: TicketStatus | null
  draft: string
  busy: boolean
  onChange: (value: string) => void
  onAccept: () => void
  onReply: () => void
  onClose: () => void
}

export function TicketComposer({
  status,
  draft,
  busy,
  onChange,
  onAccept,
  onReply,
  onClose,
}: TicketComposerProps) {
  const canReply = Boolean(draft.trim()) && !busy && status === 'processing'

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (status === 'pending') {
      if (!busy) onAccept()
      return
    }
    if (canReply) onReply()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (canReply) onReply()
    }
  }

  if (!status) {
    return <div className="composer" />
  }

  if (status === 'closed') {
    return <div className="composer" />
  }

  if (status === 'pending') {
    return (
      <form className="composer" onSubmit={handleSubmit}>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          接入
        </button>
      </form>
    )
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        rows={2}
        placeholder="回复员工"
        value={draft}
        disabled={busy}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className={chat.composerActions}>
        <button className="btn btn-primary" type="submit" disabled={!canReply}>
          发送
        </button>
        <button className="btn btn-secondary" type="button" disabled={busy} onClick={onClose}>
          关闭
        </button>
      </div>
    </form>
  )
}
