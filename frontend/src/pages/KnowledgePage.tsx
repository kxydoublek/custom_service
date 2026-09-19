import { useEffect, useRef, useState } from 'react'
import DocumentDetailPanel from '../components/knowledge/DocumentDetailPanel'
import DocumentList from '../components/knowledge/DocumentList'
import KnowledgeUpload from '../components/knowledge/KnowledgeUpload'
import '../components/knowledge/knowledge.css'
import {
  getDocument,
  isSupportedDocumentFilename,
  listDocuments,
  toDocumentSummary,
  uploadDocument,
} from '../services/documents'
import { connectRealtime, type RealtimeEvent } from '../services/ws'
import type { DocumentDetail, DocumentSummary } from '../types/dto'
import type { DocumentStatus, IngestStage } from '../types/enums'
import { getApiErrorMessage } from '../utils/apiError'

const FORMAT_ERROR = '不支持该格式'

function statusRank(status: DocumentStatus): number {
  if (status === 'queued') return 0
  if (status === 'processing') return 1
  return 2
}

function keepNewer<T extends { id: number; status: DocumentStatus; progress_percent: number }>(
  prev: T | null,
  incoming: T,
): T {
  if (prev && prev.id === incoming.id) {
    if (statusRank(prev.status) > statusRank(incoming.status)) return prev
    if (prev.progress_percent > incoming.progress_percent && prev.status === incoming.status) {
      return prev
    }
  }
  return incoming
}

function patchFromProgress(
  doc: DocumentSummary,
  event: Extract<RealtimeEvent, { event: 'document.progress' }>,
): DocumentSummary {
  return {
    ...doc,
    status: event.status as DocumentStatus,
    stage: event.stage as IngestStage,
    progress_percent: event.progress_percent,
  }
}

export default function KnowledgePage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [detail, setDetail] = useState<DocumentDetail | null>(null)
  const [listLoading, setListLoading] = useState(true)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const activeIdRef = useRef<number | null>(null)
  activeIdRef.current = activeId

  useEffect(() => {
    let cancelled = false
    setListLoading(true)
    void listDocuments()
      .then((res) => {
        if (cancelled) return
        const items = res.data ?? []
        setDocuments(items)
        setActiveId((current) => current ?? items[0]?.id ?? null)
      })
      .catch(() => {
        if (!cancelled) setDocuments([])
      })
      .finally(() => {
        if (!cancelled) setListLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    return connectRealtime((event) => {
      if (event.event === 'document.progress') {
        setDocuments((prev) =>
          prev.map((doc) => (doc.id === event.document_id ? patchFromProgress(doc, event) : doc)),
        )
        setDetail((prev) =>
          prev && prev.id === event.document_id
            ? {
                ...prev,
                status: event.status as DocumentStatus,
                stage: event.stage as IngestStage,
                progress_percent: event.progress_percent,
              }
            : prev,
        )
        return
      }

      if (event.event === 'document.failed') {
        setDocuments((prev) =>
          prev.map((doc) =>
            doc.id === event.document_id
              ? {
                  ...doc,
                  status: 'failed',
                  stage: 'failed',
                  progress_percent: 0,
                  error_message: event.error_message,
                }
              : doc,
          ),
        )
        setDetail((prev) =>
          prev && prev.id === event.document_id
            ? {
                ...prev,
                status: 'failed',
                stage: 'failed',
                progress_percent: 0,
                error_message: event.error_message,
                chunks: [],
                faqs: [],
              }
            : prev,
        )
        return
      }

      if (event.event === 'document.ready') {
        void getDocument(event.document_id).then((res) => {
          const data = res.data
          if (!data) return
          setDocuments((prev) =>
            prev.map((doc) => (doc.id === data.id ? toDocumentSummary(data) : doc)),
          )
          if (activeIdRef.current === data.id) setDetail(data)
        })
      }
    })
  }, [])

  useEffect(() => {
    if (activeId == null) {
      setDetail(null)
      return
    }
    let cancelled = false
    void getDocument(activeId)
      .then((res) => {
        if (cancelled || !res.data) return
        setDetail((prev) => keepNewer(prev, res.data as DocumentDetail))
      })
      .catch(() => {
        if (!cancelled) setDetail(null)
      })
    return () => {
      cancelled = true
    }
  }, [activeId])

  async function handleFile(file: File) {
    if (!isSupportedDocumentFilename(file.name)) {
      setUploadError(FORMAT_ERROR)
      return
    }
    setUploadError(null)
    try {
      const res = await uploadDocument(file)
      const item = res.data
      if (!item) return
      setDocuments((prev) => [item, ...prev.filter((doc) => doc.id !== item.id)])
      setActiveId(item.id)
      setDetail(null)
    } catch (error) {
      setUploadError(getApiErrorMessage(error, FORMAT_ERROR))
    }
  }

  const activeSummary = documents.find((doc) => doc.id === activeId) ?? null
  const activeDetail = detail && detail.id === activeId ? detail : null

  return (
    <main className="knowledge-page">
      <KnowledgeUpload error={uploadError} onFile={(file) => void handleFile(file)} />
      <div className="split">
        <DocumentList
          documents={documents}
          activeId={activeId}
          loading={listLoading}
          onSelect={setActiveId}
        />
        <DocumentDetailPanel summary={activeSummary} detail={activeDetail} />
      </div>
    </main>
  )
}
