import type { FormEvent, KeyboardEvent } from 'react'
import type { HandoffState } from '../../types/enums'
import styles from './chat.module.css'

interface ComposerProps {
  value: string
  busy: boolean
  handoffState: HandoffState
  onChange: (value: string) => void
  onSend: () => void
  onTransfer: () => void
}

export function Composer({
  value,
  busy,
  handoffState,
  onChange,
  onSend,
  onTransfer,
}: ComposerProps) {
  const canSend = Boolean(value.trim()) && !busy
  const transferLocked = busy || handoffState === 'waiting' || handoffState === 'in_progress'

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (canSend) onSend()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (canSend) onSend()
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        rows={2}
        placeholder="输入问题"
        value={value}
        disabled={busy && handoffState === 'none'}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <div className={styles.composerActions}>
        <button className="btn btn-secondary" type="button" disabled={transferLocked} onClick={onTransfer}>
          转人工
        </button>
        <button className="btn btn-primary" type="submit" disabled={!canSend}>
          发送
        </button>
      </div>
    </form>
  )
}
