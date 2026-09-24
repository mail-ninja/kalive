export type CanvasMode = 'monaco' | 'iframe'

export type Canvas = {
  path: string
  language: string
  text: string
  mode: CanvasMode
  preview: string
  rev?: number
}

type Fn = (c: Canvas) => void
const listeners = new Set<Fn>()

let state: Canvas = {
  path: 'untitled.md',
  language: 'markdown',
  text: '// cockpit editor — monaco\n',
  mode: 'monaco',
  preview: '',
  rev: 0,
}

const ptyFns = new Set<(s: string) => void>()

export function getCanvas(): Canvas {
  return state
}

export function setCanvas(p: Partial<Canvas>) {
  state = { ...state, ...p }
  listeners.forEach((fn) => fn(state))
}

export function subscribeCanvas(fn: Fn) {
  listeners.add(fn)
  fn(state)
  return () => listeners.delete(fn)
}

export function onPtyWrite(fn: (s: string) => void) {
  ptyFns.add(fn)
  return () => ptyFns.delete(fn)
}

export function ptyWrite(s: string) {
  ptyFns.forEach((fn) => fn(s))
}

export function applyToolResult(r: Record<string, unknown> | undefined) {
  if (!r) return
  if (typeof r.pty_write === 'string') ptyWrite(r.pty_write)
  // repo_read/grep must not clobber the open Monaco buffer.
  const canvasish = r.mode === 'iframe' || r.mode === 'monaco' || typeof r.preview === 'string'
  if (!canvasish) return
  const mode = r.mode === 'iframe' || r.mode === 'monaco' ? r.mode : undefined
  const patch: Partial<Canvas> = {}
  if (typeof r.path === 'string') patch.path = r.path
  if (typeof r.language === 'string') patch.language = r.language
  if (typeof r.text === 'string') patch.text = r.text
  if (mode) patch.mode = mode
  if (typeof r.preview === 'string') patch.preview = r.preview
  if (typeof r.rev === 'number') patch.rev = r.rev
  if (Object.keys(patch).length) setCanvas(patch)
}
