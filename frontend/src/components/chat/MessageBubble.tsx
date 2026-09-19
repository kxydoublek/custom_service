import type { MessageRole, SourceType } from '../../types/enums'

const SOURCE_LABEL: Record<SourceType, string> = {
  faq: 'FAQ',
  small_talk: '闲聊',
  knowledge_qa: '知识问答',
}

const SOURCE_CLASS: Record<SourceType, string> = {
  faq: 'source-faq',
  small_talk: 'source-chat',
  knowledge_qa: 'source-knowledge',
}

function bubbleKind(role: MessageRole): string {
  if (role === 'user') return 'user'
  if (role === 'agent') return 'agent'
  return 'sys'
}

interface MessageBubbleProps {
  role: MessageRole
  content: string
  source?: SourceType | null
}

export function MessageBubble({ role, content, source }: MessageBubbleProps) {
  return (
    <div className={`bubble ${bubbleKind(role)}`}>
      {source ? <span className={`source ${SOURCE_CLASS[source]}`}>{SOURCE_LABEL[source]}</span> : null}
      {content ? <div>{content}</div> : null}
    </div>
  )
}

