import type { DocumentSummary } from '../../types/dto'
import { documentStatusDot, documentStatusLabel } from './documentStatus'

type DocumentListProps = {
  documents: DocumentSummary[]
  activeId: number | null
  loading: boolean
  onSelect: (id: number) => void
}

function statusMeta(doc: DocumentSummary): string {
  const label = documentStatusLabel(doc.status)
  if (doc.status === 'processing') return `${label} ${doc.progress_percent}%`
  return label
}

export default function DocumentList({
  documents,
  activeId,
  loading,
  onSelect,
}: DocumentListProps) {
  return (
    <aside className="side knowledge-side">
      <h2>已入库文档</h2>
      <div className="list knowledge-list">
        {loading ? (
          [0, 1, 2].map((index) => (
            <div className="knowledge-skeleton-row" key={index}>
              <div className="knowledge-skeleton-bar" />
              <div className="knowledge-skeleton-bar short" />
            </div>
          ))
        ) : documents.length === 0 ? (
          <div className="empty">还没有文档，请上传。</div>
        ) : (
          documents.map((doc) => (
            <button
              key={doc.id}
              type="button"
              className={`list-row knowledge-list-row${doc.id === activeId ? ' active' : ''}`}
              onClick={() => onSelect(doc.id)}
            >
              <div className="title truncate">{doc.filename}</div>
              <div className="meta">
                <span className={`status-dot ${documentStatusDot(doc.status)}`} />
                {statusMeta(doc)}
              </div>
            </button>
          ))
        )}
      </div>
    </aside>
  )
}
