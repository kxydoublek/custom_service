import axios from 'axios'
import type { ApiEnvelope } from '../types/api'

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiEnvelope<unknown> | undefined
    if (data?.error) return data.error
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

export function isUnauthorized(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401
}
