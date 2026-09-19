import { useRef } from 'react'
import type { ChangeEvent } from 'react'

type KnowledgeUploadProps = {
  error: string | null
  onFile: (file: File) => void
}

export default function KnowledgeUpload({ error, onFile }: KnowledgeUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) onFile(file)
  }

  return (
    <div className="upload knowledge-upload">
      {error ? (
        <div className="error-bar" role="alert">
          {error}
        </div>
      ) : null}
      <button
        className="btn btn-primary"
        type="button"
        onClick={() => inputRef.current?.click()}
      >
        上传文档
      </button>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept=".pdf,.docx,.md,.markdown,.txt"
        aria-label="选择知识库文档"
        onChange={handleChange}
      />
      <span className="hint">PDF、Word（.docx）、Markdown、txt。提交后可离开，回来看进度。</span>
    </div>
  )
}
