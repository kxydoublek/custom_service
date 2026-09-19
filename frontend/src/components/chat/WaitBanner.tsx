import type { HandoffState } from '../../types/enums'
import { WAIT_HUMAN_TEXT } from '../../types/enums'

interface WaitBannerProps {
  handoffState: HandoffState
}

export function WaitBanner({ handoffState }: WaitBannerProps) {
  if (handoffState === 'none') return null
  const text = handoffState === 'in_progress' ? '人工客服处理中' : WAIT_HUMAN_TEXT
  return (
    <div className="wait-banner" role="status">
      {text}
    </div>
  )
}
