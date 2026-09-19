import type { DocumentDetail, DocumentSummary } from '../../types/dto'
import { documentStatusDot, documentStatusLabel } from './documentStatus'
import { objectTypeName, requestTypeName } from './tagLabels'

type DocumentDetailPanelProps = {
  summary: DocumentSummary | null
  detail: DocumentDetail | null
}

export default function DocumentDetailPanel({ summary, detail }: DocumentDetailPanelProps) {
  const doc = detail ?? summary
  if (!doc) {
    return (
      <div className="detail">
        <p className="empty">选择一份文档查看详情。</p>
      </div>
    )
  }

  if (doc.status === 'failed') {
    return (
      <div className="detail">
        <h2 className="page-title">{doc.filename}</h2>
        <div className="error-bar" role="status">
          {doc.error_message ?? '入库失败，请重新上传'}
        </div>
      </div>
    )
  }

  if (doc.status !== 'ready') {
    return (
      <div className="detail">
        <h2 className="page-title">{doc.filename}</h2>
        <p className="hint">正在处理，你可以切换到其它页面，稍后再回来看。</p>
        <p>
          <span className={`status-dot ${documentStatusDot(doc.status)}`} />
          {documentStatusLabel(doc.status)} {doc.progress_percent}%
        </p>
      </div>
    )
  }

  const tags = [
    ...doc.object_types.map((code) => objectTypeName(code)),
    ...doc.request_types.map((code) => requestTypeName(code)),
  ]

  return (
    <div className="detail">
      <h2 className="page-title">{doc.filename}</h2>
      <p>
        {tags.map((name) => (
          <span className="tag" key={name}>
            {name}
          </span>
        ))}
      </p>
      <h3 className="knowledge-detail-section">分块</h3>
      {detail?.chunks.length ? (
        detail.chunks.map((chunk) => (
          <p className="knowledge-chunk" key={chunk.id}>
            {chunk.content}
          </p>
        ))
      ) : (
        <p className="hint">暂无分块。</p>
      )}
      <h3 className="knowledge-detail-section">抽出的 FAQ</h3>
      {detail?.faqs.length ? (
        detail.faqs.map((faq) => (
          <p className="knowledge-faq" key={faq.id}>
            <strong>{faq.question}</strong>
            <br />
            {faq.answer}
          </p>
        ))
      ) : (
        <p className="hint">暂无 FAQ。</p>
      )}
      <p className="hint">入库成功立即生效，无需再确认。</p>
    </div>
  )
}
