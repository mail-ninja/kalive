import type { Hist } from './hist'

export type SessMeta = {
  id: string
  project: string
  title: string
  created?: string
  used?: string
  n?: number
}

export type SessGroup = {
  project: string
  used?: string
  sessions: SessMeta[]
}

export function projectOf(path: string): string {
  const s = (path || '').replace(/\\/g, '/').replace(/^\.\//, '')
  const m = s.match(/^(docs|apps)\/([^/]+)/)
  if (!m || m[2].includes('.')) return ''
  return m[1] + '/' + m[2]
}

export async function listSessions(project: string, agent = 'build'): Promise<SessMeta[]> {
  const q = new URLSearchParams({ project, agent })
  const r = await fetch('/v1/sessions?' + q.toString())
  if (!r.ok) return []
  const j = await r.json()
  return Array.isArray(j.sessions) ? j.sessions : []
}

export async function listAllSessions(agent = 'build'): Promise<SessGroup[]> {
  const q = new URLSearchParams({ agent })
  const r = await fetch('/v1/sessions?' + q.toString())
  if (!r.ok) return []
  const j = await r.json()
  return Array.isArray(j.projects) ? j.projects : []
}

export async function getSession(
  project: string,
  id: string,
  agent = 'build',
): Promise<{ hist: Hist[]; title?: string; id: string } | null> {
  const q = new URLSearchParams({ project, agent })
  const r = await fetch('/v1/sessions/' + encodeURIComponent(id) + '?' + q.toString())
  if (!r.ok) return null
  const j = await r.json()
  return { id: j.id, title: j.title, hist: Array.isArray(j.hist) ? j.hist : [] }
}

export async function createSession(
  project: string,
  hist: Hist[] = [],
  title = '',
  agent = 'build',
): Promise<SessMeta | null> {
  const r = await fetch('/v1/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent, project, title, hist }),
  })
  if (!r.ok) return null
  return r.json()
}

export async function saveSession(
  project: string,
  id: string,
  hist: Hist[],
  agent = 'build',
): Promise<SessMeta | null> {
  const r = await fetch('/v1/sessions/' + encodeURIComponent(id), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent, project, hist }),
  })
  if (!r.ok) return null
  return r.json()
}
