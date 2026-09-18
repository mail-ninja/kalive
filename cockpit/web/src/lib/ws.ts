export type Frame = {
  v: number
  ch: string
  id: string
  type: string
  payload: Record<string, unknown>
}

export function connect(onFrame: (f: Frame) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/v1/ws`)
  let ping: number | undefined
  ws.onopen = () => {
    ping = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) send(ws, 'log', 'ping', { t: Date.now() })
    }, 20000)
  }
  ws.onmessage = (ev) => {
    try {
      const f = JSON.parse(String(ev.data)) as Frame
      if (f.ch === 'log' && f.type === 'pong') return
      onFrame(f)
    } catch {
      /* ignore */
    }
  }
  ws.addEventListener('close', () => {
    if (ping) window.clearInterval(ping)
  })
  return ws
}

export function send(ws: WebSocket, ch: string, type: string, payload: Record<string, unknown> = {}) {
  if (ws.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify({ v: 1, ch, id: crypto.randomUUID(), type, payload }))
}
