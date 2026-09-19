import type {
  ContentType,
  DocumentStatus,
  HandoffState,
  IngestStage,
  MessageRole,
  ObjectType,
  RequestType,
  SourceType,
  TicketStatus,
} from './enums'

export interface MessagePublic {
  id: number
  role: MessageRole
  content: string
  source: SourceType | null
  created_at: string
}

export interface ConversationSummary {
  id: number
  title: string
  updated_at: string
  preview: string
}

export interface ConversationDetail {
  id: number
  title: string
  handoff_state: HandoffState
  messages: MessagePublic[]
  created_at: string
  updated_at: string
}

export interface DocumentSummary {
  id: number
  filename: string
  content_type: ContentType
  status: DocumentStatus
  stage: IngestStage
  progress_percent: number
  error_message: string | null
  chunk_count: number
  faq_count: number
  object_types: ObjectType[]
  request_types: RequestType[]
  created_at: string
}

export interface DocumentChunk {
  id: number
  ordinal: number
  content: string
  object_types: ObjectType[]
  request_types: RequestType[]
}

export interface DocumentFaq {
  id: number
  question: string
  answer: string
}

export interface DocumentDetail extends DocumentSummary {
  char_count: number
  chunks: DocumentChunk[]
  faqs: DocumentFaq[]
}

export interface TicketSummary {
  id: number
  conversation_id: number
  status: TicketStatus
  title: string
  preview: string
  created_at: string
}

export interface TicketDetail extends TicketSummary {
  messages: MessagePublic[]
  accepted_at: string | null
  closed_at: string | null
}
