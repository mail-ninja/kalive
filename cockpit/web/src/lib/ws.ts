export type Frame = {
  v: number
  ch: string
  id: string
  type: string
  payload: Record<string, unknown>
}

type Status = 'open' | 'close'
const frames = new Set<(f: Frame) => void>()
const statuses = new Set<(s: Status) => void>()
let sock: WebSocket | null = null
let ping: number | undefined
let reconnecting = false

function ensure() {
  if (sock && (sock.readyState === WebSocket.OPEN || sock.readyState === WebSocket.CONNECTING)) return
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/v1/ws`)
  sock = ws
  ws.onopen = () => {
    reconnecting = false
    ping = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) send('log', 'ping', { t: Date.now() })
    }, 20000)
    statuses.forEach((fn) => fn('open'))
  }
  ws.onmessage = (ev) => {
    try {
      const f = JSON.parse(String(ev.data)) as Frame
      if (f.ch === 'log' && f.type === 'pong') return
      frames.forEach((fn) => fn(f))
    } catch {
      /* ignore */
    }
  }
  ws.addEventListener('close', () => {
    if (ping) window.clearInterval(ping)
    ping = undefined
    if (sock === ws) sock = null
    statuses.forEach((fn) => fn('close'))
    if (!reconnecting) {
      reconnecting = true
      window.setTimeout(() => {
        reconnecting = false
        if (frames.size) ensure()
      }, 1200)
    }
  })
}

/** Subscribe. Does not close the socket on unsubscribe — survives Vite HMR / remount. */
export function connect(onFrame: (f: Frame) => void, onStatus?: (s: Status) => void) {
  frames.add(onFrame)
  if (onStatus) statuses.add(onStatus)
  ensure()
  return () => {
    frames.delete(onFrame)
    if (onStatus) statuses.delete(onStatus)
  }
}

export function send(ch: string, type: string, payload: Record<string, unknown> = {}) {
  if (!sock || sock.readyState !== WebSocket.OPEN) return
  sock.send(JSON.stringify({ v: 1, ch, id: crypto.randomUUID(), type, payload }))
}

/** @deprecated use send(ch, type, payload) — kept so old call sites compile if any remain */
export function sendTo(ws: WebSocket, ch: string, type: string, payload: Record<string, unknown> = {}) {
  if (ws.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify({ v: 1, ch, id: crypto.randomUUID(), type, payload }))
}
