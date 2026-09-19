import { AxiosError } from 'axios'
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import api, { passthroughAdapter } from '../services/api'
import type { ApiEnvelope, Pagination } from '../types/api'
import type { DocumentChunk, DocumentDetail, DocumentFaq, DocumentSummary } from '../types/dto'
import type { ContentType, DocumentStatus, IngestStage, ObjectType, RequestType } from '../types/enums'
import { MOCK_TOKEN } from './auth'
import { publish } from './bus'

const UPLOAD_MAX_BYTES = 20_971_520
const UNSUPPORTED_FORMAT_ERROR = '不支持该格式，请上传 PDF、Word（.docx）、Markdown 或 txt'
const EXTRACT_FAIL_ERROR = '无法提取正文，文档未入库'

type DocumentRecord = {
  id: number
  filename: string
  content_type: ContentType
  status: DocumentStatus
  stage: IngestStage
  progress_percent: number
  error_message: string | null
  char_count: number
  created_at: string
  object_types: ObjectType[]
  request_types: RequestType[]
  chunks: DocumentChunk[]
  faqs: DocumentFaq[]
}

type DocumentListResponse = ApiEnvelope<DocumentSummary[]> & { pagination: Pagination }

const store = new Map<number, DocumentRecord>()
let nextDocumentId = 1
let nextChunkId = 1
let nextFaqId = 1

function nowIso(): string {
  return new Date().toISOString()
}

function ok<T>(data: T, requestId: string): ApiEnvelope<T> {
  return {
    success: true,
    data,
    error: null,
    error_code: null,
    message: 'ok',
    timestamp: nowIso(),
    request_id: requestId,
    metadata: {},
  }
}

function okList(
  data: DocumentSummary[],
  pagination: Pagination,
  requestId: string,
): DocumentListResponse {
  return {
    ...ok(data, requestId),
    pagination,
  }
}

function fail(error: string, errorCode: string, requestId: string): ApiEnvelope<null> {
  return {
    success: false,
    data: null,
    error,
    error_code: errorCode,
    message: null,
    timestamp: nowIso(),
    request_id: requestId,
    metadata: {},
  }
}

function pathOf(config: InternalAxiosRequestConfig): string {
  const url = config.url ?? ''
  const base = config.baseURL ?? ''
  const combined = url.startsWith('http') ? url : `${base}${url}`
  try {
    const parsed = combined.startsWith('http')
      ? new URL(combined)
      : new URL(combined, 'http://local.invalid')
    return parsed.pathname.replace(/\/+$/, '') || '/'
  } catch {
    return url.split('?')[0] ?? url
  }
}

function isDocumentPath(path: string): boolean {
  return /\/documents(?:\/\d+)?$/.test(path)
}

function jsonResponse<T>(
  config: InternalAxiosRequestConfig,
  status: number,
  data: T,
): AxiosResponse<T> {
  return {
    data,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: { 'content-type': 'application/json' },
    config,
  }
}

function rejectEnvelope(
  config: InternalAxiosRequestConfig,
  status: number,
  data: ApiEnvelope<null>,
): Promise<never> {
  return Promise.reject(
    new AxiosError(
      data.error ?? 'Error',
      AxiosError.ERR_BAD_REQUEST,
      config,
      undefined,
      jsonResponse(config, status, data),
    ),
  )
}

function readBearer(config: InternalAxiosRequestConfig): string {
  const raw = config.headers.Authorization ?? config.headers.authorization ?? ''
  return String(raw).replace(/^Bearer\s+/i, '')
}

function contentTypeOf(filename: string): ContentType | null {
  const match = filename.toLowerCase().match(/\.([^.]+)$/)
  const ext = match?.[1]
  if (ext === 'pdf') return 'pdf'
  if (ext === 'docx') return 'docx'
  if (ext === 'md' || ext === 'markdown') return 'markdown'
  if (ext === 'txt') return 'txt'
  return null
}

function toSummary(doc: DocumentRecord): DocumentSummary {
  return {
    id: doc.id,
    filename: doc.filename,
    content_type: doc.content_type,
    status: doc.status,
    stage: doc.stage,
    progress_percent: doc.progress_percent,
    error_message: doc.error_message,
    chunk_count: doc.chunks.length,
    faq_count: doc.faqs.length,
    object_types: [...doc.object_types],
    request_types: [...doc.request_types],
    created_at: doc.created_at,
  }
}

function toDetail(doc: DocumentRecord): DocumentDetail {
  return {
    ...toSummary(doc),
    char_count: doc.char_count,
    chunks: doc.chunks.map((chunk) => ({
      id: chunk.id,
      ordinal: chunk.ordinal,
      content: chunk.content,
      object_types: [...chunk.object_types],
      request_types: [...chunk.request_types],
    })),
    faqs: doc.faqs.map((faq) => ({
      id: faq.id,
      question: faq.question,
      answer: faq.answer,
    })),
  }
}

function readUploadFile(config: InternalAxiosRequestConfig): File | null {
  const data = config.data
  if (data instanceof FormData) {
    const file = data.get('file')
    if (file instanceof File) return file
  }
  return null
}

function queryValue(
  config: InternalAxiosRequestConfig,
  key: string,
): string | undefined {
  const params = config.params as Record<string, unknown> | undefined
  const fromParams = params?.[key]
  if (fromParams != null && String(fromParams).length > 0) return String(fromParams)
  const url = config.url ?? ''
  const qIndex = url.indexOf('?')
  if (qIndex < 0) return undefined
  return new URLSearchParams(url.slice(qIndex)).get(key) ?? undefined
}

function shouldFailExtract(file: File): boolean {
  return file.size === 0 || /空|empty/i.test(file.name)
}

function buildReadyPayload(filename: string): Pick<
  DocumentRecord,
  'char_count' | 'object_types' | 'request_types' | 'chunks' | 'faqs'
> {
  const stem = filename.replace(/\.[^.]+$/, '')
  const objectTypes: ObjectType[] = ['network']
  const requestTypes: RequestType[] = ['troubleshooting']
  const chunks: DocumentChunk[] = [
    {
      id: nextChunkId++,
      ordinal: 0,
      content: `[Mock] ${stem}：文档已切分并写入检索库。`,
      object_types: [...objectTypes],
      request_types: [...requestTypes],
    },
    {
      id: nextChunkId++,
      ordinal: 1,
      content: '[Mock] 认证失败时先检查账号是否锁定，再重试连接公司网络。',
      object_types: [...objectTypes],
      request_types: [...requestTypes],
    },
  ]
  const faqs: DocumentFaq[] = [
    {
      id: nextFaqId++,
      question: `${stem}怎么办？`,
      answer: '[Mock] 按文档中的步骤操作：先检查账号是否锁定，再重试连接。',
    },
  ]
  const charCount = chunks.reduce((sum, chunk) => sum + chunk.content.length, 0)
  return {
    char_count: charCount,
    object_types: objectTypes,
    request_types: requestTypes,
    chunks,
    faqs,
  }
}

function patchRecord(
  id: number,
  patch: Partial<
    Pick<DocumentRecord, 'status' | 'stage' | 'progress_percent' | 'error_message'>
  > &
    Partial<Pick<DocumentRecord, 'char_count' | 'object_types' | 'request_types' | 'chunks' | 'faqs'>>,
): DocumentRecord | null {
  const current = store.get(id)
  if (!current) return null
  const next: DocumentRecord = { ...current, ...patch }
  store.set(id, next)
  return next
}

function startIngest(id: number, file: File): void {
  const failExtract = shouldFailExtract(file)
  window.setTimeout(() => {
    const next = patchRecord(id, {
      status: 'processing',
      stage: 'extracting',
      progress_percent: 10,
    })
    if (!next) return
    publish({
      event: 'document.progress',
      document_id: id,
      status: next.status,
      stage: next.stage,
      progress_percent: next.progress_percent,
    })
  }, 800)

  if (failExtract) {
    window.setTimeout(() => {
      const next = patchRecord(id, {
        status: 'failed',
        stage: 'failed',
        progress_percent: 0,
        error_message: EXTRACT_FAIL_ERROR,
      })
      if (!next) return
      publish({
        event: 'document.failed',
        document_id: id,
        error_message: EXTRACT_FAIL_ERROR,
      })
    }, 1800)
    return
  }

  const steps: { delay: number; stage: IngestStage; progress_percent: number }[] = [
    { delay: 1800, stage: 'chunking', progress_percent: 25 },
    { delay: 2800, stage: 'tagging', progress_percent: 45 },
    { delay: 3800, stage: 'embedding', progress_percent: 70 },
    { delay: 4800, stage: 'faq_extracting', progress_percent: 90 },
  ]
  for (const step of steps) {
    window.setTimeout(() => {
      const next = patchRecord(id, {
        status: 'processing',
        stage: step.stage,
        progress_percent: step.progress_percent,
      })
      if (!next) return
      publish({
        event: 'document.progress',
        document_id: id,
        status: next.status,
        stage: next.stage,
        progress_percent: next.progress_percent,
      })
    }, step.delay)
  }

  window.setTimeout(() => {
    const ready = buildReadyPayload(file.name)
    const next = patchRecord(id, {
      status: 'ready',
      stage: 'ready',
      progress_percent: 100,
      error_message: null,
      ...ready,
    })
    if (!next) return
    publish({ event: 'document.ready', document_id: id })
  }, 5800)
}

function handleUpload(config: InternalAxiosRequestConfig): Promise<AxiosResponse<ApiEnvelope<DocumentSummary>>> {
  const file = readUploadFile(config)
  if (!file) {
    return rejectEnvelope(
      config,
      400,
      fail('请选择要上传的文件', 'VALIDATION_ERROR', 'req-doc-upload-missing'),
    )
  }
  if (file.size > UPLOAD_MAX_BYTES) {
    return rejectEnvelope(
      config,
      400,
      fail('文件过大，最大 20MB', 'VALIDATION_ERROR', 'req-doc-upload-too-large'),
    )
  }
  const contentType = contentTypeOf(file.name)
  if (!contentType) {
    return rejectEnvelope(
      config,
      400,
      fail(UNSUPPORTED_FORMAT_ERROR, 'VALIDATION_ERROR', 'req-doc-upload-format'),
    )
  }

  const record: DocumentRecord = {
    id: nextDocumentId++,
    filename: file.name,
    content_type: contentType,
    status: 'queued',
    stage: 'queued',
    progress_percent: 0,
    error_message: null,
    char_count: 0,
    created_at: nowIso(),
    object_types: [],
    request_types: [],
    chunks: [],
    faqs: [],
  }
  store.set(record.id, record)
  startIngest(record.id, file)
  const data: DocumentSummary = toSummary(record)
  return Promise.resolve(jsonResponse(config, 200, ok(data, `req-doc-upload-${record.id}`)))
}

function handleList(config: InternalAxiosRequestConfig): AxiosResponse<DocumentListResponse> {
  const page = Math.max(1, Number(queryValue(config, 'page') ?? 1) || 1)
  const rawSize = Number(queryValue(config, 'page_size') ?? 20) || 20
  const pageSize = Math.min(50, Math.max(1, rawSize))
  const statusFilter = queryValue(config, 'status') as DocumentStatus | undefined
  const all = [...store.values()].sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  const filtered = statusFilter ? all.filter((doc) => doc.status === statusFilter) : all
  const start = (page - 1) * pageSize
  const slice = filtered.slice(start, start + pageSize)
  const data: DocumentSummary[] = slice.map((doc) => toSummary(doc))
  const pagination: Pagination = { page, page_size: pageSize, total: filtered.length }
  return jsonResponse(config, 200, okList(data, pagination, 'req-doc-list-1'))
}

function handleDetail(
  config: InternalAxiosRequestConfig,
  documentId: number,
): Promise<AxiosResponse<ApiEnvelope<DocumentDetail>>> {
  const record = store.get(documentId)
  if (!record) {
    return rejectEnvelope(config, 404, fail('文档不存在', 'NOT_FOUND', 'req-doc-detail-404'))
  }
  const data: DocumentDetail = toDetail(record)
  return Promise.resolve(jsonResponse(config, 200, ok(data, `req-doc-detail-${documentId}`)))
}

const documentsAdapter: AxiosAdapter = (config) => {
  if (readBearer(config) !== MOCK_TOKEN) {
    return passthroughAdapter(config)
  }

  const path = pathOf(config)
  const method = (config.method ?? 'get').toLowerCase()
  const detailMatch = path.match(/\/documents\/(\d+)$/)

  if (method === 'post' && /\/documents$/.test(path)) {
    return handleUpload(config)
  }
  if (method === 'get' && detailMatch) {
    return handleDetail(config, Number(detailMatch[1]))
  }
  if (method === 'get' && /\/documents$/.test(path)) {
    return Promise.resolve(handleList(config))
  }

  return Promise.reject(new Error(`Unhandled document mock: ${method} ${path}`))
}

let installed = false

export function installDocumentMocks(): void {
  if (installed) return
  installed = true
  api.interceptors.request.use((config) => {
    if (isDocumentPath(pathOf(config))) {
      config.adapter = documentsAdapter
    }
    return config
  })
}

export function isSupportedDocumentFilename(filename: string): boolean {
  return contentTypeOf(filename) != null
}
