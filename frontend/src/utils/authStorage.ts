export const ACCESS_TOKEN_KEY = 'access_token'
export const AUTH_NOTICE_KEY = 'auth_notice'

const NEED_LOGIN_TEXT = '请先登录'

let realtimeCloser: (() => void) | null = null

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function setAccessToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token)
}

export function setRealtimeCloser(handler: (() => void) | null): void {
  realtimeCloser = handler
}

export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  realtimeCloser?.()
}

export function setNeedLoginNotice(): void {
  sessionStorage.setItem(AUTH_NOTICE_KEY, NEED_LOGIN_TEXT)
}

export function peekAuthNotice(): string | null {
  return sessionStorage.getItem(AUTH_NOTICE_KEY)
}

export function clearAuthNotice(): void {
  sessionStorage.removeItem(AUTH_NOTICE_KEY)
}
