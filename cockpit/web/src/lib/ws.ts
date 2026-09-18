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
  ws.onmessage = (ev) => {
    try {
      onFrame(JSON.parse(String(ev.data)) as Frame)
    } catch {
      /* ignore */
    }
  }
  return ws
}

export function send(ws: WebSocket, ch: string, type: string, payload: Record<string, unknown> = {}) {
  if (ws.readyState !== WebSocket.OPEN) return
  ws.send(JSON.stringify({ v: 1, ch, id: crypto.randomUUID(), type, payload }))
}
