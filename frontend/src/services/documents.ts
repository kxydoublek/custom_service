import { installDocumentMocks, isSupportedDocumentFilename } from '../mocks/documents'
import type { ApiEnvelope, Pagination } from '../types/api'
import type { DocumentDetail, DocumentSummary } from '../types/dto'
import type { DocumentStatus } from '../types/enums'
import api from './api'

installDocumentMocks()

export { isSupportedDocumentFilename }

export type PaginatedDocuments = ApiEnvelope<DocumentSummary[]> & { pagination: Pagination }

export function toDocumentSummary(doc: DocumentSummary): DocumentSummary {
  return {
    id: doc.id,
    filename: doc.filename,
    content_type: doc.content_type,
    status: doc.status,
    stage: doc.stage,
    progress_percent: doc.progress_percent,
    error_message: doc.error_message,
    chunk_count: doc.chunk_count,
    faq_count: doc.faq_count,
    object_types: doc.object_types,
    request_types: doc.request_types,
    created_at: doc.created_at,
  }
}

export async function uploadDocument(file: File): Promise<ApiEnvelope<DocumentSummary>> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<ApiEnvelope<DocumentSummary>>('/documents', form)
  return data
}

export async function listDocuments(query?: {
  page?: number
  page_size?: number
  status?: DocumentStatus
}): Promise<PaginatedDocuments> {
  const { data } = await api.get<PaginatedDocuments>('/documents', {
    params: {
      page: query?.page ?? 1,
      page_size: query?.page_size ?? 20,
      status: query?.status,
    },
  })
  return data
}

export async function getDocument(documentId: number): Promise<ApiEnvelope<DocumentDetail>> {
  const { data } = await api.get<ApiEnvelope<DocumentDetail>>(`/documents/${documentId}`)
  return data
}
