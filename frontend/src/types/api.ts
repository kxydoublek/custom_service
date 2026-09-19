export interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  error: string | null
  error_code: string | null
  message: string | null
  timestamp: string
  request_id: string | null
  metadata: Record<string, unknown>
}

export interface Pagination {
  page: number
  page_size: number
  total: number
}
