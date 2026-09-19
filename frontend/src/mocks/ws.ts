import { MOCK_TOKEN } from './auth'
import { subscribe } from './bus'

function isAppWs(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin)
    return parsed.pathname === '/ws' || parsed.pathname === '/ws/'
  } catch {
    return false
  }
}

class MockAppSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3

  url: string
  readyState = MockAppSocket.CONNECTING
  protocol = ''
  extensions = ''
  binaryType: BinaryType = 'blob'
  bufferedAmount = 0
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null

  private unsub: (() => void) | null = null

  constructor(url: string) {
    this.url = url
    queueMicrotask(() => {
      this.open()
    })
  }

  private token(): string {
    try {
      return new URL(this.url, window.location.origin).searchParams.get('access_token') ?? ''
    } catch {
      return ''
    }
  }

  private open(): void {
    if (this.readyState !== MockAppSocket.CONNECTING) return
    if (this.token() !== MOCK_TOKEN) {
      this.readyState = MockAppSocket.CLOSED
      this.onclose?.(new CloseEvent('close', { code: 1008, reason: 'unauthorized' }))
      return
    }
    this.readyState = MockAppSocket.OPEN
    this.onopen?.(new Event('open'))
    this.unsub = subscribe((event) => {
      if (this.readyState !== MockAppSocket.OPEN) return
      this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })
  }

  send(data: string): void {
    void data
  }

  close(): void {
    this.unsub?.()
    this.unsub = null
    if (this.readyState === MockAppSocket.CLOSED) return
    this.readyState = MockAppSocket.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }

  addEventListener(): void {}
  removeEventListener(): void {}
  dispatchEvent(): boolean {
    return false
  }
}

let installed = false

export function installWsMock(): void {
  if (installed) return
  installed = true
  const NativeWebSocket = window.WebSocket
  const Wrapped = new Proxy(NativeWebSocket, {
    construct(target, args: unknown[]) {
      const url = String(args[0] ?? '')
      if (isAppWs(url)) {
        let token = ''
        try {
          token = new URL(url, window.location.origin).searchParams.get('access_token') ?? ''
        } catch {
          token = ''
        }
        if (token === MOCK_TOKEN) {
          return new MockAppSocket(url)
        }
      }
      return new target(args[0] as string | URL, args[1] as string | string[] | undefined)
    },
  })
  window.WebSocket = Wrapped
}
