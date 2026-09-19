import { installWsMock } from '../mocks/ws'
import { MOCK_TOKEN } from '../mocks/auth'
import type { BusEvent } from '../mocks/bus'
import { getAccessToken, setRealtimeCloser } from '../utils/authStorage'

installWsMock()

export type RealtimeEvent = BusEvent

const handlers = new Set<(event: RealtimeEvent) => void>()

let activeSocket: WebSocket | null = null
let connectedToken: string | null = null

export function isMockSession(): boolean {
  return (getAccessToken() ?? '') === MOCK_TOKEN
}

function disposeActiveSocket(): void {
  if (!activeSocket) return
  const socket = activeSocket
  activeSocket = null
  connectedToken = null
  socket.onmessage = null
  socket.onopen = null
  socket.onerror = null
  socket.onclose = null
  if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
    socket.close()
  }
}

setRealtimeCloser(disposeActiveSocket)

function socketUrl(token: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws?access_token=${encodeURIComponent(token)}`
}

function socketAlive(): boolean {
  return (
    activeSocket != null &&
    (activeSocket.readyState === WebSocket.OPEN || activeSocket.readyState === WebSocket.CONNECTING)
  )
}

function openSocket(): void {
  disposeActiveSocket()
  const token = getAccessToken() ?? ''
  connectedToken = token
  const socket = new WebSocket(socketUrl(token))
  activeSocket = socket

  socket.onmessage = (message) => {
    const raw = typeof message.data === 'string' ? message.data : ''
    if (raw === 'ping') {
      if (socket.readyState === WebSocket.OPEN) socket.send('pong')
      return
    }
    if (!raw) return
    try {
      const parsed = JSON.parse(raw) as RealtimeEvent
      if (parsed && typeof parsed.event === 'string') {
        handlers.forEach((handler) => handler(parsed))
      }
    } catch {
      // ignore malformed frames
    }
  }
}

export function connectRealtime(onEvent: (event: RealtimeEvent) => void): () => void {
  handlers.add(onEvent)
  const token = getAccessToken() ?? ''
  if (!socketAlive() || connectedToken !== token) {
    openSocket()
  }

  return () => {
    handlers.delete(onEvent)
    if (handlers.size === 0) {
      disposeActiveSocket()
    }
  }
}
