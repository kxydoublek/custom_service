import api from './api'
import type { ApiEnvelope } from '../types/api'
import type { AuthUser, LoginData, LoginRequest, LogoutData } from '../types/auth'

export async function login(payload: LoginRequest): Promise<ApiEnvelope<LoginData>> {
  const { data } = await api.post<ApiEnvelope<LoginData>>('/auth/login', payload)
  return data
}

export async function fetchCurrentUser(): Promise<ApiEnvelope<AuthUser>> {
  const { data } = await api.get<ApiEnvelope<AuthUser>>('/auth/me')
  return data
}

export async function logout(): Promise<ApiEnvelope<LogoutData>> {
  const { data } = await api.post<ApiEnvelope<LogoutData>>('/auth/logout')
  return data
}
