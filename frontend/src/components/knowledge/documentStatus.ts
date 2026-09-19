import type { DocumentStatus } from '../../types/enums'

export function documentStatusLabel(status: DocumentStatus): string {
  if (status === 'queued') return '排队中'
  if (status === 'processing') return '处理中'
  if (status === 'ready') return '已生效'
  return '失败'
}

export function documentStatusDot(status: DocumentStatus): string {
  if (status === 'ready') return 'dot-success'
  if (status === 'failed') return 'dot-error'
  return 'dot-warning'
}
