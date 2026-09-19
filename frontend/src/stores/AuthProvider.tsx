import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useLocation } from 'react-router'
import { fetchCurrentUser, login as loginRequest, logout as logoutRequest } from '../services/auth'
import type { AuthUser } from '../types/auth'
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
  setNeedLoginNotice,
} from '../utils/authStorage'
import { AuthContext } from './authContext'
import type { AuthStatus } from './authContext'

const PROTECTED_PATHS = ['/employee', '/agent', '/knowledge']

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`))
}

function rememberNeedLogin(pathname: string): void {
  if (isProtectedPath(pathname)) {
    setNeedLoginNotice()
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)

  useEffect(() => {
    let cancelled = false

    async function restore() {
      const token = getAccessToken()
      if (!token) {
        rememberNeedLogin(window.location.pathname)
        if (!cancelled) setStatus('anonymous')
        return
      }
      try {
        const envelope = await fetchCurrentUser()
        if (cancelled) return
        if (envelope.success && envelope.data) {
          setUser(envelope.data)
          setStatus('authenticated')
        } else {
          rememberNeedLogin(window.location.pathname)
          clearAccessToken()
          setUser(null)
          setStatus('anonymous')
        }
      } catch {
        if (cancelled) return
        rememberNeedLogin(window.location.pathname)
        clearAccessToken()
        setUser(null)
        setStatus('anonymous')
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (status === 'anonymous') {
      rememberNeedLogin(location.pathname)
    }
  }, [status, location.pathname])

  const login = useCallback(async (username: string, password: string) => {
    const envelope = await loginRequest({ username, password })
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.error ?? '账号或密码不正确')
    }
    setAccessToken(envelope.data.access_token)
    setUser(envelope.data.user)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutRequest()
    } finally {
      clearAccessToken()
      setUser(null)
      setStatus('anonymous')
    }
  }, [])

  const value = useMemo(
    () => ({ status, user, login, logout }),
    [status, user, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
