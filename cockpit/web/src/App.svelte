<script lang="ts">
  import { onMount } from 'svelte'
  import Editor from './lib/Editor.svelte'
  import ExtensionsPane from './lib/ExtensionsPane.svelte'
  import GitPane from './lib/GitPane.svelte'
  import Hiroshima from './lib/Hiroshima.svelte'
  import Preview from './lib/Preview.svelte'
  import Settings from './lib/Settings.svelte'
  import Split from './lib/Split.svelte'
  import Term from './lib/Term.svelte'
  import Tree from './lib/Tree.svelte'
  import WorkspacePicker from './lib/WorkspacePicker.svelte'
  import { applyToolResult, getCanvas, isLoopbackUrl, onOpenHiroshima, setCanvas, subscribeCanvas } from './lib/desk'
  import { loadHist, persistHist, type Hist } from './lib/hist'
  import {
    createSession,
    getSession,
    listAllSessions,
    listSessions,
    projectOf,
    saveSession,
    type SessGroup,
    type SessMeta,
  } from './lib/sessions'
  import { connect, send, type Frame } from './lib/ws'

  let wsReady = $state(false)
  let hiroshima = $state(false)
  let hiroshimaW = $state(Number(localStorage.getItem('kalived.hiroshimaW') || 92) || 92)
  let hiroDragging = $state(false)
  let tab = $state('work')
  let hist = $state<Hist[]>(loadHist())
  let histEl: HTMLDivElement | undefined = $state()
  let draft = $state('')
  let stream = $state('')
  let tools = $state<string[]>([])
  let health = $state('…')
  let memory = $state<Record<'sqlite' | 'qdrant' | 'kuzu' | 'redis' | 'minio', boolean> | null>(null)
  const memoryKeys = ['sqlite', 'qdrant', 'kuzu', 'redis', 'minio'] as const
  let agents = $state<{ id: string; name: string; description: string; provider: string; model: string; desk?: string }[]>([])
  let providers = $state<{ id: string; label: string; models: string[] }[]>([])
  let agentId = $state('build')
  let providerId = $state('xai')
  let modelId = $state('grok-4.6')
  let splitH = $state(74)
  let splitV = $state(72)
  let splitCode = $state(58)
  let runMode = $state<'agent' | 'plan'>(
    localStorage.getItem('kalived.ui.run') === 'plan' ? 'plan' : 'agent',
  )
  let canvasUi = $state(getCanvas())
  let details = $state(false)
  let ptyOpen = $state(false)
  let running = $state(false)
  let liveOut = $state('')
  let liveCmd = $state('')
  let diskPath = $state('README.md')
  let previewPath = $state('')
  let previewUrl = $state('')
  let previewDraft = $state('')
  let treeTick = $state(0)
  let fileRev = $state(0)
  let dirty = $state<Record<string, boolean>>({})
  let wsName = $state('kalived')
  let wsRoot = $state('')
  let wsKind = $state<'kalived' | 'external'>('kalived')
  let wsDlg = $state<null | 'open' | 'new'>(null)
  let mkdirOpen = $state(false)
  let mkdirName = $state('')
  let recents = $state<{ path: string; name: string }[]>([])
  let menu = $state<null | 'fil' | 'rediger' | 'term' | 'innstillinger'>(null)
  let sessMenu = $state(false)
  let treeOpen = $state(localStorage.getItem('kalived.ui.tree') !== '0')
  let editorOpen = $state(localStorage.getItem('kalived.ui.editor') !== '0')
  let previewOpen = $state(localStorage.getItem('kalived.ui.preview') !== '0')
  let sideTab = $state<'filer' | 'git' | 'ext'>(
    localStorage.getItem('kalived.ui.sidetab') === 'git'
      ? 'git'
      : localStorage.getItem('kalived.ui.sidetab') === 'ext'
        ? 'ext'
        : 'filer',
  )
  let ptyTabs = $state<{ id: number }[]>([{ id: 1 }])
  let ptyTab = $state(1)
  let ptySeq = 1
  let saveAs = $state(false)
  let saveAsPath = $state('')
  let saveNote = $state('')
  let newFile = $state(false)
  let newFilePath = $state('')
  let revealLine = $state(0)
  let models = $derived(providers.find((p) => p.id === providerId)?.models ?? [])
  let team = $derived(agents.filter((a) => a.id === 'build'))
  let project = $state('')
  let sessionId = $state('')
  let sessList = $state<SessMeta[]>([])
  let sessGroups = $state<SessGroup[]>([])
  let sessSwitching = $state(false)
  let pendingProject: string | null = null
  let saveTimer: number | undefined

  let groupsToShow = $derived.by(() => {
    const seen = new Set(sessGroups.map((g) => g.project))
    const rows = sessGroups.map((g) =>
      g.project === project ? { ...g, sessions: sessList.length ? sessList : g.sessions } : g,
    )
    if (project && !seen.has(project)) {
      rows.unshift({ project, used: '', sessions: sessList })
    }
    return rows
  })

  let sessTitle = $derived.by(() => {
    for (const g of groupsToShow) {
      const s = g.sessions.find((x) => x.id === sessionId)
      if (s) return s.title || 'samtale'
    }
    if (project) {
      const g = groupsToShow.find((x) => x.project === project)
      if (!g || !g.sessions.length) return 'ingen samtaler'
      return 'samtale'
    }
    return 'samtaler'
  })

  function persistPane(key: 'tree' | 'editor' | 'preview', on: boolean) {
    try {
      localStorage.setItem('kalived.ui.' + key, on ? '1' : '0')
    } catch {
      /* ignore */
    }
  }

  function setTree(on: boolean) {
    treeOpen = on
    persistPane('tree', on)
  }

  function setEditor(on: boolean) {
    editorOpen = on
    persistPane('editor', on)
  }

  function setPreview(on: boolean) {
    previewOpen = on
    persistPane('preview', on)
  }

  function setSideTab(next: 'filer' | 'git' | 'ext') {
    sideTab = next
    try {
      localStorage.setItem('kalived.ui.sidetab', next)
    } catch {
      /* ignore */
    }
  }

  function toggleMenu(id: 'fil' | 'rediger' | 'term' | 'innstillinger') {
    menu = menu === id ? null : id
    sessMenu = false
  }

  function closeMenus() {
    menu = null
    sessMenu = false
  }

  function goWork() {
    tab = 'work'
    closeMenus()
  }

  function setRunMode(m: 'agent' | 'plan') {
    runMode = m
    try {
      localStorage.setItem('kalived.ui.run', m)
    } catch {
      /* ignore */
    }
  }

  function addPtyTab() {
    ptySeq += 1
    const id = ptySeq
    ptyTabs = [...ptyTabs, { id }]
    ptyTab = id
    ptyOpen = true
    splitV = 72
    menu = null
  }

  function closePtyTab(id: number) {
    if (ptyTabs.length <= 1) {
      ptyOpen = false
      return
    }
    const next = ptyTabs.filter((t) => t.id !== id)
    ptyTabs = next
    if (ptyTab === id) ptyTab = next[next.length - 1].id
  }

  function isHtml(p: string) {
    return /\.html?$/i.test(p)
  }

  function markDirty(p: string) {
    if (!p || dirty[p]) return
    dirty = { ...dirty, [p]: true }
  }

  function clearDirty(p: string) {
    if (!p || !dirty[p]) return
    const next = { ...dirty }
    delete next[p]
    dirty = next
  }

  function bumpCanvas(path: string) {
    setCanvas({
      path,
      mode: 'monaco',
      rev: (getCanvas().rev || 0) + 1,
    })
  }

  function onWrote(path: string) {
    diskPath = path
    markDirty(path)
    treeTick += 1
    fileRev += 1
    bumpCanvas(path)
    if (isHtml(path)) {
      previewPath = path
      previewUrl = ''
    }
  }

  function setHiroshimaW(w: number) {
    hiroshimaW = Math.min(100, Math.max(12, w))
    try {
      localStorage.setItem('kalived.hiroshimaW', String(Math.round(hiroshimaW)))
    } catch {
      /* ignore */
    }
  }

  function startHiroDrag(e: MouseEvent) {
    e.preventDefault()
    e.stopPropagation()
    hiroDragging = true
    const startX = e.clientX
    const startW = hiroshimaW
    const move = (ev: MouseEvent) => {
      const dx = startX - ev.clientX
      setHiroshimaW(startW + (dx / window.innerWidth) * 100)
    }
    const up = () => {
      hiroDragging = false
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
  }

  function onFrame(f: Frame) {
    if (f.ch === 'chat' && f.type === 'token') {
      stream += String(f.payload.text ?? '')
    }
    if (f.ch === 'chat' && f.type === 'done') {
      hist = [
        ...hist,
        { role: 'bot', name: String(f.payload.agent ?? agentId), text: stream },
      ]
      stream = ''
      running = false
    }
    if (f.ch === 'chat' && f.type === 'error') {
      hist = [...hist, { role: 'sys', text: 'error: ' + String(f.payload.error ?? 'ukjent') }]
      stream = ''
      running = false
      liveCmd = ''
    }
    if (f.ch === 'run' && f.type === 'stopped') {
      running = false
      liveCmd = ''
      hist = [...hist, { role: 'sys', text: 'stoppet — logger og diff beholdt' }]
      stream = ''
    }
    if (f.ch === 'run' && f.type === 'pulse') {
      const s = Number(f.payload.s ?? 0)
      liveCmd = s > 0 ? 'modell ' + s + 's' : 'modell'
    }
    if (f.ch === 'tools' && f.type === 'list') {
      const list = f.payload.tools as { name: string }[] | undefined
      tools = (list ?? []).map((t) => t.name)
    }
    if (f.ch === 'tools' && f.type === 'call') {
      liveOut = ''
      const a = f.payload.args as { argv?: string[]; line?: string } | undefined
      liveCmd = Array.isArray(a?.argv) ? a.argv.join(' ') : String(a?.line || f.payload.name || '')
      hist = [...hist, { role: 'tool', name: String(f.payload.name || ''), text: `runde ${f.payload.round ?? '?'}` }]
    }
    if (f.ch === 'tools' && f.type === 'out') {
      liveOut += String(f.payload.text ?? '')
      if (liveOut.length > 80_000) liveOut = liveOut.slice(-60_000)
    }
    if (f.ch === 'tools' && f.type === 'result') {
      const r = f.payload.result as Record<string, unknown> | undefined
      applyToolResult(r)
      if (r?.need_pty === true || r?.open_hiroshima === true) hiroshima = true
      const prev = typeof r?.preview === 'string' ? r.preview : typeof r?.url === 'string' ? r.url : ''
      if (prev && isLoopbackUrl(prev)) {
        previewUrl = prev
        previewDraft = prev
      }
      if (r?.wrote === true && typeof r.path === 'string') {
        onWrote(r.path)
      }
      const diff = typeof r?.diff === 'string' ? r.diff : ''
      const rawHits = Array.isArray(r?.hits) ? r.hits : []
      const hits = rawHits
        .map((h) => {
          if (!h || typeof h !== 'object') return null
          const o = h as { path?: unknown; line?: unknown; text?: unknown }
          if (typeof o.path !== 'string') return null
          return { path: o.path, line: Number(o.line) || 1, text: String(o.text || '') }
        })
        .filter((h): h is { path: string; line: number; text: string } => h !== null)
        .slice(0, 16)
      let text = ''
      if (r && 'exit_code' in r) {
        text = `exit ${r.exit_code}${r.timeout ? ' timeout' : ''}${r.cancelled ? ' stoppet' : ''}\n${String(r.stdout_tail || r.stderr_tail || '').slice(-1200)}`
      } else if (hits.length) {
        text = `${hits.length} treff`
      } else if (typeof r?.summary === 'string' && r.summary) {
        text = r.summary
      } else {
        const bit = r && (r.error || r.path || r.n || r.agent)
        text = String(bit ?? JSON.stringify(r ?? {}).slice(0, 280))
      }
      hist = [
        ...hist,
        {
          role: 'tool',
          name: String(f.payload.name || ''),
          path: typeof r?.path === 'string' ? r.path : undefined,
          line: typeof r?.line === 'number' ? r.line : hits[0]?.line,
          hits: hits.length ? hits : undefined,
          diff,
          text,
        },
      ]
    }
    if (f.ch === 'log' && f.type === 'line') {
      hist = [...hist, { role: 'sys', text: String(f.payload.text ?? '') }]
    }
    if (f.ch === 'hiroshima' && f.type === 'open') hiroshima = true
    if (f.ch === 'agents' && f.type === 'list') {
      const list = f.payload.agents as typeof agents
      if (Array.isArray(list)) agents = list
      const plist = f.payload.providers as typeof providers
      if (Array.isArray(plist) && plist.length) providers = plist
      const sel = String(f.payload.selected ?? '')
      if (sel) agentId = sel
    }
    if (f.ch === 'agents' && f.type === 'selected') {
      const id = String(f.payload.id ?? '')
      if (id) agentId = id
    }
  }

  $effect(() => {
    hist.length
    stream
    persistHist(hist)
    queueMicrotask(() => {
      if (histEl) histEl.scrollTop = histEl.scrollHeight
    })
    if (sessSwitching || !sessionId || !project) return
    const snap = hist
    const sid = sessionId
    const proj = project
    const aid = agentId
    if (saveTimer) window.clearTimeout(saveTimer)
    saveTimer = window.setTimeout(() => {
      saveSession(proj, sid, snap, aid).then((meta) => {
        if (meta) {
          sessList = [meta, ...sessList.filter((s) => s.id !== meta.id)]
          void refreshGroups()
        }
      })
    }, 450)
  })

  $effect(() => {
    const p = projectOf(diskPath, wsName, wsKind)
    if (!p || p === project) return
    void switchProject(p)
  })

  async function refreshGroups() {
    sessGroups = await listAllSessions(agentId)
  }

  async function switchProject(p: string) {
    if (!p) return
    if (sessSwitching) {
      pendingProject = p
      return
    }
    sessSwitching = true
    const prev = project
    try {
      if (sessionId && prev) {
        await saveSession(prev, sessionId, hist, agentId)
      }
      project = p
      sessionId = ''
      sessList = []
      const rows = await listSessions(p, agentId)
      sessList = rows
      if (rows[0]) {
        await loadSession(rows[0].id, p)
        if (!sessionId) hist = []
      } else if (hist.length && !prev) {
        const row = await createSession(p, hist, '', agentId)
        if (row) {
          sessionId = row.id
          sessList = [row]
        }
      } else {
        hist = []
      }
      await refreshGroups()
    } finally {
      sessSwitching = false
      const next = pendingProject
      pendingProject = null
      if (next && next !== project) void switchProject(next)
    }
  }

  async function loadSession(id: string, proj = project) {
    const body = await getSession(proj, id, agentId)
    if (!body) return
    const hold = sessSwitching
    sessSwitching = true
    sessionId = body.id
    hist = body.hist
    persistHist(hist)
    sessSwitching = hold
  }

  async function openSess(s: SessMeta) {
    if (!s?.id || !s.project) return
    if (s.id === sessionId && s.project === project) return
    if (sessionId && project && !(sessSwitching)) {
      await saveSession(project, sessionId, hist, agentId)
    }
    sessSwitching = true
    try {
      project = s.project
      sessList = sessGroups.find((g) => g.project === s.project)?.sessions || sessList
      await loadSession(s.id, s.project)
      const html = s.project + '/index.html'
      openDisk(html)
    } finally {
      sessSwitching = false
    }
  }

  async function newSession() {
    if (!project) return
    if (sessionId) await saveSession(project, sessionId, hist, agentId)
    const row = await createSession(project, [], 'samtale', agentId)
    if (!row) return
    sessSwitching = true
    sessionId = row.id
    hist = []
    sessList = [row, ...sessList.filter((s) => s.id !== row.id)]
    persistHist(hist)
    sessSwitching = false
    void refreshGroups()
  }

  onMount(() => {
    fetch('/v1/health')
      .then((r) => r.json())
      .then((j) => {
        health = j.ok ? 'cockpit :8788' : 'health fail'
      })
      .catch(() => {
        health = 'backend nede — kjør cockpit/scripts/dev.sh'
      })
    void refreshGroups()
    const offCanvas = subscribeCanvas((c) => {
      canvasUi = c
    })
    const offHiro = onOpenHiroshima(() => {
      hiroshima = true
    })
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault()
        saveDisk()
      }
      if (e.key === 'Escape') {
        if (wsDlg) {
          wsDlg = null
          return
        }
        if (tab === 'settings') {
          goWork()
          return
        }
        closeMenus()
      }
    }
    const onDoc = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null
      if (t?.closest('[data-menu]')) return
      closeMenus()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onDoc)
    fetch('/v1/workspace')
      .then((r) => r.json())
      .then((j) => applyWorkspace(j, false))
      .catch(() => {})
    fetch('/v1/agents')
      .then((r) => r.json())
      .then((j) => {
        if (Array.isArray(j.agents)) agents = j.agents
        if (Array.isArray(j.providers) && j.providers.length) providers = j.providers
      })
      .catch(() => {})
    fetch('/v1/memory')
      .then((r) => r.json())
      .then((j) => {
        const b = (j && j.backends) || {}
        memory = {
          sqlite: !!b.sqlite,
          qdrant: !!b.qdrant,
          kuzu: !!b.kuzu,
          redis: !!b.redis,
          minio: !!b.minio,
        }
      })
      .catch(() => {
        memory = { sqlite: false, qdrant: false, kuzu: false, redis: false, minio: false }
      })
    const unsub = connect(onFrame, (s) => {
      wsReady = s === 'open'
      if (s === 'open') hist = [...hist, { role: 'sys', text: 'cockpit ws up' }]
      if (s === 'close' && running) {
        running = false
        liveCmd = ''
        hist = [
          ...hist,
          {
            role: 'sys',
            text: 'ws brutt — runden kan fortsette på server. Histikk ligger i sqlite.',
          },
        ]
      }
    })
    return () => {
      unsub()
      offCanvas()
      offHiro()
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onDoc)
    }
  })

  function stopAll() {
    send('run', 'stop', {})
    running = false
    liveCmd = ''
  }

  async function saveDisk() {
    const c = getCanvas()
    if (!diskPath) return
    if (c.path && c.path !== diskPath) {
      hist = [
        ...hist,
        {
          role: 'sys',
          text: `lagre avvist: buffer er ${c.path}, valgt fil er ${diskPath} — åpne fila på nytt`,
        },
      ]
      return
    }
    const r = await fetch('/v1/workspace/file', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: diskPath, text: c.text }),
    })
    saveNote = r.ok ? 'lagret ' + diskPath : 'lagre feilet'
    if (r.ok) {
      clearDirty(diskPath)
      setCanvas({ path: diskPath, mode: 'monaco', rev: (getCanvas().rev || 0) + 1 })
      if (isHtml(diskPath)) {
        previewPath = diskPath
        previewUrl = ''
      }
    }
    window.setTimeout(() => {
      if (saveNote.startsWith('lagret')) saveNote = ''
    }, 2000)
  }

  async function saveDiskAs() {
    const dest = saveAsPath.trim().replace(/^\/+/, '')
    if (!dest || dest.includes('..')) return
    const c = getCanvas()
    const r = await fetch('/v1/workspace/file', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: dest, text: c.text }),
    })
    if (r.ok) {
      diskPath = dest
      fileRev += 1
      treeTick += 1
      clearDirty(dest)
      setCanvas({
        path: dest,
        mode: 'monaco',
        rev: (getCanvas().rev || 0) + 1,
      })
      if (isHtml(dest)) {
        previewPath = dest
        previewUrl = ''
      }
      saveAs = false
      saveNote = 'lagret som ' + dest
    } else saveNote = 'lagre som feilet'
  }

  function openDisk(p: string, line?: number) {
    const same = diskPath === p
    diskPath = p
    revealLine = line && line > 0 ? line : 0
    if (!same) {
      fileRev += 1
      bumpCanvas(p)
      if (isHtml(p)) {
        previewPath = p
        previewUrl = ''
      }
    }
  }

  function applyWorkspace(j: Record<string, unknown>, reset = true) {
    if (typeof j.name === 'string' && j.name) wsName = j.name
    if (typeof j.root === 'string') wsRoot = j.root
    wsKind = j.kind === 'external' ? 'external' : 'kalived'
    recents = Array.isArray(j.recents)
      ? (j.recents as { path: string; name: string }[]).filter((r) => r && r.path)
      : recents
    if (reset) {
      dirty = {}
      diskPath = typeof j.hint === 'string' ? j.hint : ''
      previewPath = isHtml(diskPath) ? diskPath : ''
      previewUrl = ''
      previewDraft = ''
      sessionId = ''
      project = typeof j.project === 'string' ? j.project : projectOf(diskPath, wsName, wsKind)
      hist = []
      stream = ''
      treeTick += 1
      fileRev += 1
      void refreshGroups()
    }
    wsDlg = null
    menu = null
  }

  async function openRecent(path: string) {
    menu = null
    const r = await fetch('/v1/workspace/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
    const j = await r.json().catch(() => ({}))
    if (!r.ok) {
      saveNote = String((j as { detail?: string }).detail || 'kunne ikke åpne workspace')
      return
    }
    applyWorkspace(j as Record<string, unknown>)
  }

  function startNewFile() {
    const dir = diskPath.includes('/') ? diskPath.slice(0, diskPath.lastIndexOf('/') + 1) : ''
    newFilePath = dir
    newFile = true
    menu = null
  }

  async function createDir() {
    const dest = mkdirName.trim()
    if (!dest) return
    const r = await fetch('/v1/workspace/mkdir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: dest }),
    })
    const j = await r.json().catch(() => ({}))
    if (!r.ok) {
      saveNote = String((j as { detail?: string }).detail || 'kunne ikke lage mappe')
      return
    }
    mkdirOpen = false
    mkdirName = ''
    treeTick += 1
  }

  async function createFile() {
    const dest = newFilePath.trim().replace(/^\/+/, '')
    if (!dest || dest.includes('..')) return
    const r = await fetch('/v1/workspace/file', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: dest, text: '\n' }),
    })
    if (r.ok) {
      newFile = false
      treeTick += 1
      openDisk(dest)
      saveNote = 'ny fil ' + dest
    } else saveNote = 'ny fil feilet'
  }

  function showInPreview() {
    if (!diskPath) return
    previewPath = diskPath
    previewUrl = ''
    setCanvas({ path: diskPath, preview: '', mode: 'monaco', rev: (getCanvas().rev || 0) + 1 })
  }

  function showLoopback() {
    const u = previewDraft.trim()
    if (!isLoopbackUrl(u)) {
      saveNote = 'preview: bare 127.0.0.1 / localhost'
      return
    }
    previewUrl = u
    setCanvas({ preview: u, mode: 'iframe', rev: (getCanvas().rev || 0) + 1 })
  }

  function reloadPreview() {
    setCanvas({ rev: (getCanvas().rev || 0) + 1 })
  }

  async function stopPreviewServe() {
    await fetch('/v1/preview/stop', { method: 'POST' }).catch(() => {})
    previewUrl = ''
    previewDraft = ''
    setCanvas({ preview: '', rev: (getCanvas().rev || 0) + 1 })
  }

  async function say() {
    const t = draft.trim()
    if (!t) return
    running = true
    hist = [...hist, { role: 'you', text: t }]
    draft = ''
    let sid = sessionId
    const proj = project || projectOf(diskPath, wsName, wsKind)
    if (proj && !sid) {
      const row = await createSession(proj, hist, t, agentId)
      if (row) {
        sid = row.id
        sessionId = row.id
        project = proj
        sessList = [row, ...sessList.filter((s) => s.id !== row.id)]
        void refreshGroups()
      }
    }
    send('chat', 'user', {
      text: t,
      agent: agentId,
      provider: providerId,
      model: modelId,
      allow_mutate: runMode === 'agent',
      project: proj,
      session: sid,
    })
  }
</script>

<div class="flex h-full min-h-screen flex-col">
  <header class="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-white/10 px-3 py-1.5">
    <div class="font-serif text-xl tracking-wide">cockpit</div>
    <button
      type="button"
      class="rounded-full border border-white/15 px-2 py-0.5 text-xs text-clean/80 hover:bg-white/10"
      title={wsRoot || 'bytt workspace'}
      onclick={() => {
        tab = 'work'
        menu = null
        wsDlg = 'open'
      }}
    >{wsName}</button>
    <span class="text-xs text-paper/40">{health}</span>
    <nav class="ml-1 flex items-center text-sm" data-menu>
      <div class="relative">
        <button
          type="button"
          class="rounded px-2 py-1 hover:bg-white/10 {menu === 'fil' ? 'bg-white/10' : ''}"
          onclick={() => toggleMenu('fil')}
        >Fil</button>
        {#if menu === 'fil'}
          <div class="absolute left-0 z-30 mt-1 min-w-[14rem] rounded-md border border-white/15 bg-ink py-1 text-xs shadow-lg">
            {#if tab === 'settings'}
              <button type="button" class="block w-full px-3 py-1.5 text-left hover:bg-white/10" onclick={goWork}>tilbake til arbeid</button>
              <div class="my-1 border-t border-white/10"></div>
            {/if}
            <button type="button" class="block w-full px-3 py-1.5 text-left hover:bg-white/10" onclick={startNewFile}>ny fil…</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                mkdirName = ''
                mkdirOpen = true
              }}
            >ny mappe…</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                wsDlg = 'new'
              }}
            >ny workspace…</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                wsDlg = 'open'
              }}
            >åpne mappe…</button>
            {#if recents.length}
              <div class="my-1 border-t border-white/10"></div>
              {#each recents.slice(0, 6) as r}
                <button
                  type="button"
                  class="block w-full truncate px-3 py-1.5 text-left hover:bg-white/10 {r.name === wsName ? 'text-clean' : ''}"
                  title={r.path}
                  onclick={() => openRecent(r.path)}
                >{r.name}</button>
              {/each}
            {/if}
            <div class="my-1 border-t border-white/10"></div>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                saveDisk()
              }}
            >lagre <span class="text-paper/40">Ctrl+S</span></button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                saveAsPath = diskPath
                saveAs = true
              }}
            >lagre som…</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                treeTick += 1
              }}
            >oppdater</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                showInPreview()
                setPreview(true)
              }}
            >vis i preview</button>
            {#if !treeOpen}
              <button
                type="button"
                class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
                onclick={() => {
                  menu = null
                  setTree(true)
                }}
              >vis tre</button>
            {/if}
            <div class="my-1 border-t border-white/10"></div>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                tab = 'settings'
              }}
            >innstillinger</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                window.close()
              }}
            >avslutt</button>
          </div>
        {/if}
      </div>
      <div class="relative">
        <button
          type="button"
          class="rounded px-2 py-1 hover:bg-white/10 {menu === 'rediger' ? 'bg-white/10' : ''}"
          onclick={() => toggleMenu('rediger')}
        >Rediger</button>
        {#if menu === 'rediger'}
          <div class="absolute left-0 z-30 mt-1 min-w-[12rem] rounded-md border border-white/15 bg-ink py-1 text-xs shadow-lg">
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                showInPreview()
                setPreview(true)
              }}
            >vis i preview</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                setEditor(!editorOpen)
              }}
            >{editorOpen ? 'skjul kode' : 'vis kode'}</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                setPreview(!previewOpen)
              }}
            >{previewOpen ? 'skjul preview' : 'vis preview'}</button>
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                setTree(!treeOpen)
              }}
            >{treeOpen ? 'skjul tre' : 'vis tre'}</button>
          </div>
        {/if}
      </div>
      <div class="relative">
        <button
          type="button"
          class="rounded px-2 py-1 hover:bg-white/10 {menu === 'term' ? 'bg-white/10' : ''}"
          onclick={() => toggleMenu('term')}
        >Terminal</button>
        {#if menu === 'term'}
          <div class="absolute left-0 z-30 mt-1 min-w-[12rem] rounded-md border border-white/15 bg-ink py-1 text-xs shadow-lg">
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                ptyOpen = !ptyOpen
                if (ptyOpen) splitV = 72
              }}
            >{ptyOpen ? 'skjul PTY' : 'vis PTY'}</button>
            <button type="button" class="block w-full px-3 py-1.5 text-left hover:bg-white/10" onclick={addPtyTab}>ny fane</button>
            {#each ptyTabs as t (t.id)}
              <button
                type="button"
                class="block w-full px-3 py-1.5 text-left hover:bg-white/10 {ptyTab === t.id && ptyOpen ? 'text-clean' : ''}"
                onclick={() => {
                  menu = null
                  ptyTab = t.id
                  ptyOpen = true
                  splitV = 72
                }}
              >term {t.id}</button>
            {/each}
          </div>
        {/if}
      </div>
      <div class="relative">
        <button
          type="button"
          class="rounded px-2 py-1 hover:bg-white/10 {menu === 'innstillinger' ? 'bg-white/10' : ''}"
          onclick={() => toggleMenu('innstillinger')}
        >Innstillinger</button>
        {#if menu === 'innstillinger'}
          <div class="absolute left-0 z-30 mt-1 min-w-[12rem] rounded-md border border-white/15 bg-ink py-1 text-xs shadow-lg">
            {#if tab === 'settings'}
              <button type="button" class="block w-full px-3 py-1.5 text-left hover:bg-white/10" onclick={goWork}>tilbake til arbeid</button>
            {:else}
              <button
                type="button"
                class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
                onclick={() => {
                  menu = null
                  tab = 'settings'
                }}
              >maskin og nøkler</button>
            {/if}
            <button
              type="button"
              class="block w-full px-3 py-1.5 text-left hover:bg-white/10"
              onclick={() => {
                menu = null
                details = !details
              }}
            >{details ? 'skjul kjøredetaljer' : 'kjøredetaljer'}</button>
          </div>
        {/if}
      </div>
    </nav>
    <div class="ml-auto flex flex-wrap items-center gap-2">
      <button
        class="rounded-full border border-white/15 px-3 py-1 text-sm hover:bg-white/10"
        class:bg-paper={tab === 'work' || tab === 'settings'}
        class:text-ink={tab === 'work' || tab === 'settings'}
        onclick={goWork}
      >
        {tab === 'settings' ? '← Arbeid' : 'Arbeid'}
      </button>
      <div class="flex rounded-full border border-white/15 p-0.5 text-sm" title="agent skriver og kjører. planlegg leser og foreslår.">
        <button
          type="button"
          class="rounded-full px-3 py-0.5 {runMode === 'agent' ? 'bg-paper text-ink' : 'text-paper/60 hover:text-paper'}"
          onclick={() => setRunMode('agent')}
        >agent</button>
        <button
          type="button"
          class="rounded-full px-3 py-0.5 {runMode === 'plan' ? 'bg-paper text-ink' : 'text-paper/60 hover:text-paper'}"
          onclick={() => setRunMode('plan')}
        >planlegg</button>
      </div>
      <button
        type="button"
        class="rounded-full border border-alert/50 px-3 py-1 text-sm text-alert"
        onclick={stopAll}
      >
        Stopp all agentaktivitet
      </button>
      <button
        class="rounded-full bg-alert px-3 py-1 text-sm font-semibold text-ink"
        onclick={() => (hiroshima = !hiroshima)}
      >
        Hiroshima
      </button>
    </div>
  </header>

  {#if saveAs || newFile || mkdirOpen || saveNote}
    <div class="flex flex-wrap items-center gap-2 border-b border-white/10 px-3 py-1 text-xs">
      {#if saveAs}
        <form
          class="flex items-center gap-1"
          onsubmit={(e) => {
            e.preventDefault()
            saveDiskAs()
          }}
        >
          <span class="text-paper/50">lagre som</span>
          <input class="w-56 rounded border border-white/15 bg-ink px-2 py-0.5" bind:value={saveAsPath} />
          <button type="submit" class="text-clean">ok</button>
          <button type="button" class="text-paper/50" onclick={() => (saveAs = false)}>avbryt</button>
        </form>
      {/if}
      {#if newFile}
        <form
          class="flex items-center gap-1"
          onsubmit={(e) => {
            e.preventDefault()
            createFile()
          }}
        >
          <span class="text-paper/50">ny fil</span>
          <input
            class="w-56 rounded border border-white/15 bg-ink px-2 py-0.5"
            bind:value={newFilePath}
            placeholder="docs/ny.html"
          />
          <button type="submit" class="text-clean">ok</button>
          <button type="button" class="text-paper/50" onclick={() => (newFile = false)}>avbryt</button>
        </form>
      {/if}
      {#if mkdirOpen}
        <form
          class="flex items-center gap-1"
          onsubmit={(e) => {
            e.preventDefault()
            createDir()
          }}
        >
          <span class="text-paper/50">ny mappe</span>
          <input class="w-40 rounded border border-white/15 bg-ink px-2 py-0.5" bind:value={mkdirName} placeholder="navn" />
          <button type="submit" class="text-clean">ok</button>
          <button type="button" class="text-paper/50" onclick={() => (mkdirOpen = false)}>avbryt</button>
        </form>
      {/if}
      {#if saveNote}
        <span class="text-clean/80">{saveNote}</span>
      {/if}
    </div>
  {/if}

  {#if details}
    <div class="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-2 text-xs">
      <span class="text-paper/40" title="GET /v1/memory">
        Minne
        {#each memoryKeys as k}
          <span class="ml-1.5">{k} {memory ? (memory[k] ? 'oppe' : 'nede') : '…'}</span>
        {/each}
      </span>
      <label class="flex items-center gap-1 text-paper/60">
        provider
        <select
          class="rounded-full border border-white/15 bg-ink px-2 py-1 text-paper"
          bind:value={providerId}
          onchange={() => {
            const m = providers.find((p) => p.id === providerId)?.models
            if (m?.length && !m.includes(modelId)) modelId = m[0]
          }}
        >
          {#each providers as p}
            <option value={p.id}>{p.label}</option>
          {/each}
        </select>
      </label>
      <label class="flex items-center gap-1 text-paper/60">
        modell
        <select class="rounded-full border border-white/15 bg-ink px-2 py-1 text-paper" bind:value={modelId}>
          {#each models as m}
            <option value={m}>{m}</option>
          {/each}
        </select>
      </label>
      <label class="flex items-center gap-1 text-paper/60">
        agent
        <select
          class="rounded-full border border-white/15 bg-ink px-2 py-1 text-paper"
          bind:value={agentId}
          onchange={() => send('agents', 'select', { id: agentId })}
        >
          {#each agents as a}
            <option value={a.id}>{a.name}</option>
          {/each}
        </select>
      </label>
    </div>
  {/if}

  {#if tab === 'settings'}
    <div class="min-h-0 flex-1 overflow-y-auto">
      <Settings onback={goWork} />
    </div>
  {:else}
    {#snippet editorPane()}
      <div class="flex h-full min-h-0 flex-col">
        <div class="flex items-center gap-2 border-b border-white/10 px-2 py-1 text-xs text-paper/50">
          <span class="truncate">
            {diskPath || 'ingen fil åpen'}{#if diskPath && dirty[diskPath]}<span class="text-warn"> ●</span>{/if}
          </span>
          <button
            type="button"
            class="ml-auto shrink-0 px-1 text-paper/40 hover:text-paper"
            title="skjul kode"
            aria-label="skjul kode"
            onclick={() => setEditor(false)}
          >‹</button>
        </div>
        <div class="min-h-0 flex-1">
          {#if diskPath}
            <Editor {diskPath} {fileRev} {revealLine} ondirty={markDirty} />
          {:else}
            <div class="flex h-full items-center justify-center p-6 text-sm text-paper/50">
              <div class="max-w-xs text-center">
                <p>Ingen fil åpen.</p>
                <p class="mt-1 text-xs text-paper/40">Velg i treet til venstre, eller Fil → ny fil.</p>
              </div>
            </div>
          {/if}
        </div>
      </div>
    {/snippet}

    {#snippet previewPane()}
      <div class="flex h-full min-h-0 flex-col">
        <div class="flex flex-wrap items-center gap-1 border-b border-white/10 px-2 py-1 text-xs">
          <span class="text-paper/50">preview</span>
          <form
            class="flex min-w-0 flex-1 items-center gap-1"
            onsubmit={(e) => {
              e.preventDefault()
              showLoopback()
            }}
          >
            <input
              class="min-w-0 flex-1 rounded border border-white/15 bg-ink px-2 py-0.5"
              bind:value={previewDraft}
              placeholder="http://127.0.0.1:8765/"
              spellcheck="false"
            />
            <button type="submit" class="rounded-full border border-white/15 px-2 py-0.5">vis url</button>
          </form>
          <button type="button" class="rounded-full border border-white/15 px-2 py-0.5" onclick={reloadPreview}>last på nytt</button>
          {#if previewUrl}
            <button type="button" class="rounded-full border border-white/15 px-2 py-0.5" onclick={stopPreviewServe}>stopp tjener</button>
          {/if}
          <button
            type="button"
            class="shrink-0 px-1 text-paper/40 hover:text-paper"
            title="skjul preview"
            aria-label="skjul preview"
            onclick={() => setPreview(false)}
          >›</button>
        </div>
        <div class="min-h-0 flex-1">
          <Preview path={previewPath} url={previewUrl} rev={canvasUi.rev ?? 0} />
        </div>
      </div>
    {/snippet}

    {#snippet editorPreview()}
      <div class="flex h-full min-h-0">
        {#if editorOpen && previewOpen}
          <Split direction="horizontal" bind:value={splitCode} min={28} max={78}>
            {#snippet a()}
              {@render editorPane()}
            {/snippet}
            {#snippet b()}
              {@render previewPane()}
            {/snippet}
          </Split>
        {:else if editorOpen}
          <div class="flex h-full min-h-0 w-full">
            <div class="min-h-0 min-w-0 flex-1">{@render editorPane()}</div>
            <button
              type="button"
              class="w-6 shrink-0 border-l border-white/10 text-paper/40 hover:bg-white/5 hover:text-paper"
              title="vis preview"
              aria-label="vis preview"
              onclick={() => setPreview(true)}
            >‹</button>
          </div>
        {:else if previewOpen}
          <div class="flex h-full min-h-0 w-full">
            <button
              type="button"
              class="w-6 shrink-0 border-r border-white/10 text-paper/40 hover:bg-white/5 hover:text-paper"
              title="vis kode"
              aria-label="vis kode"
              onclick={() => setEditor(true)}
            >›</button>
            <div class="min-h-0 min-w-0 flex-1">{@render previewPane()}</div>
          </div>
        {:else}
          <div class="flex h-full w-full items-center justify-center gap-3 text-xs text-paper/40">
            <button type="button" class="rounded-full border border-white/15 px-3 py-1 hover:bg-white/10" onclick={() => setEditor(true)}>vis kode</button>
            <button type="button" class="rounded-full border border-white/15 px-3 py-1 hover:bg-white/10" onclick={() => setPreview(true)}>vis preview</button>
          </div>
        {/if}
      </div>
    {/snippet}

    {#snippet ptyPane()}
      <div class="flex h-full min-h-0 flex-col">
        <div class="flex items-center gap-1 border-b border-white/10 px-2 py-0.5 text-xs">
          <span class="mr-1 text-paper/50">PTY</span>
          {#each ptyTabs as t (t.id)}
            <button
              type="button"
              class="rounded px-2 py-0.5 hover:bg-white/10 {ptyTab === t.id ? 'bg-white/10 text-clean' : 'text-paper/70'}"
              onclick={() => (ptyTab = t.id)}
            >term {t.id}</button>
            {#if ptyTabs.length > 1}
              <button
                type="button"
                class="-ml-1 px-1 text-paper/35 hover:text-paper"
                title="lukk fane"
                onclick={() => closePtyTab(t.id)}
              >×</button>
            {/if}
          {/each}
          <button type="button" class="px-1.5 text-paper/50 hover:text-paper" title="ny fane" onclick={addPtyTab}>+</button>
          <span class="ml-2 text-paper/35">passord her</span>
          <button type="button" class="ml-auto px-1 text-paper/40 hover:text-paper" onclick={() => (ptyOpen = false)}>skjul</button>
        </div>
        <div class="relative min-h-0 flex-1 p-1">
          {#each ptyTabs as t (t.id)}
            <div class="absolute inset-1" class:hidden={ptyTab !== t.id}>
              <Term />
            </div>
          {/each}
        </div>
      </div>
    {/snippet}

    {#snippet chatPane()}
      <section class="flex h-full min-h-0 flex-col">
        <div class="flex items-center gap-1 border-b border-white/10 px-2 py-1">
          <div class="relative min-w-0 flex-1" data-menu>
            <button
              type="button"
              class="flex w-full items-center gap-1 truncate rounded px-2 py-0.5 text-left text-xs hover:bg-white/10"
              onclick={() => {
                sessMenu = !sessMenu
                menu = null
              }}
            >
              <span class="truncate">
                {sessTitle}{#if project}<span class="text-paper/40"> · {project}</span>{/if}
              </span>
              <span class="ml-auto shrink-0 text-paper/40">▾</span>
            </button>
            {#if sessMenu}
              <div class="absolute left-0 right-0 z-30 mt-1 max-h-72 overflow-auto rounded-md border border-white/15 bg-ink py-1 text-xs shadow-lg">
                {#if groupsToShow.length}
                  {#each groupsToShow as g}
                    <div class="px-3 pt-1.5 text-[0.65rem] uppercase tracking-wide text-paper/40">{g.project}</div>
                    {#if g.sessions.length}
                      {#each g.sessions as s}
                        <button
                          type="button"
                          class="block w-full truncate px-3 py-1.5 text-left hover:bg-white/10 {sessionId === s.id ? 'text-clean' : ''}"
                          onclick={() => {
                            sessMenu = false
                            openSess(s)
                          }}
                          title={s.used || ''}
                        >{s.title || 'samtale'}</button>
                      {/each}
                    {:else}
                      <p class="px-3 pb-1 text-paper/35">ingen samtaler i denne mappa ennå</p>
                    {/if}
                  {/each}
                {:else}
                  <p class="px-3 py-2 text-paper/80">ingen samtaler i {wsName} ennå</p>
                  <p class="px-3 pb-2 text-paper/40">skriv under — første melding lagres her</p>
                {/if}
              </div>
            {/if}
          </div>
          {#if project}
            <button type="button" class="shrink-0 px-2 text-xs text-clean/80 hover:text-clean" onclick={newSession}>ny</button>
          {/if}
        </div>
        {#if agents.length}
          {@const cur = agents.find((x) => x.id === agentId)}
          {#if cur}
            <p class="px-3 pt-1 text-[0.7rem] text-paper/40">{cur.description}</p>
          {/if}
        {/if}
        {#if team.length}
          <div class="flex flex-wrap gap-1 px-2 pt-1">
            {#each team as a}
              <button
                type="button"
                class="rounded-full border border-white/15 px-2 py-0.5 text-xs"
                class:bg-paper={agentId === a.id}
                class:text-ink={agentId === a.id}
                onclick={() => {
                  agentId = a.id
                  send('agents', 'select', { id: a.id })
                }}>{a.name}</button>
            {/each}
          </div>
        {/if}
        <div class="mx-2 mt-1 flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-white/10 bg-black/40">
          <div class="flex items-center justify-between border-b border-white/10 px-3 py-1.5 text-xs text-paper/50">
            <span class="truncate">{running ? (liveCmd ? 'kjører: ' + liveCmd : 'kjører…') : runMode === 'plan' ? 'plan — skriver ikke' : 'klar'}</span>
            <span>{hist.length}</span>
          </div>
          {#if running && (liveOut || liveCmd)}
            <pre class="max-h-40 overflow-auto border-b border-white/10 bg-black/50 p-2 font-mono text-[0.7rem] text-clean/90">{liveOut || '… venter på output'}</pre>
          {/if}
          <div bind:this={histEl} class="chat-hist min-h-0 flex-1 space-y-2 overflow-y-scroll p-3 text-sm">
            {#each hist as m}
              {#if m.role === 'tool'}
                <div class="bubble sys">
                  <div class="who">
                    {m.name || 'tool'}{#if m.path}
                      ·
                      <button
                        type="button"
                        class="normal-case tracking-normal text-clean underline decoration-clean/40 hover:decoration-clean"
                        onclick={() => openDisk(m.path || '', m.line)}
                      >{m.path}{#if m.line}:{m.line}{/if}</button>
                    {/if}
                  </div>
                  <div>{m.text}</div>
                  {#if m.hits?.length}
                    <div class="mt-1 max-h-40 space-y-0.5 overflow-auto font-mono text-[0.7rem]">
                      {#each m.hits as h}
                        <button
                          type="button"
                          class="block w-full truncate text-left text-clean/80 hover:text-clean"
                          onclick={() => openDisk(h.path, h.line)}
                        >{h.path}:{h.line} {h.text}</button>
                      {/each}
                    </div>
                  {/if}
                  {#if m.diff}
                    <pre class="mt-1 max-h-40 overflow-auto text-[0.7rem] text-clean/80">{m.diff}</pre>
                  {/if}
                </div>
              {:else}
                <div class="bubble {m.role}">
                  <div class="who">{m.role === 'you' ? 'du' : m.role === 'bot' ? (m.name || agentId) : 'sys'}</div>
                  {m.text}
                </div>
              {/if}
            {/each}
            {#if stream}
              <div class="bubble bot">
                <div class="who">{agentId}</div>
                <span class="text-clean">{stream}</span>
              </div>
            {/if}
          </div>
        </div>
        <form
          class="m-2 flex gap-2"
          onsubmit={(e) => {
            e.preventDefault()
            say()
          }}
        >
          <input
            class="flex-1 rounded-lg border border-white/15 bg-ink px-3 py-2"
            bind:value={draft}
            placeholder={runMode === 'plan'
              ? 'planlegg med ' + agentId + ' — skriver ikke'
              : 'oppgave til ' + agentId}
          />
          <button class="rounded-lg bg-paper px-3 py-2 text-ink">{runMode === 'plan' ? 'planlegg' : 'send'}</button>
        </form>
      </section>
    {/snippet}

    <div class="flex min-h-0 flex-1">
      {#if treeOpen}
        <div class="flex w-72 shrink-0 flex-col border-r border-white/10">
          <div class="flex items-center gap-0.5 border-b border-white/10 px-1 py-0.5 text-[0.7rem]">
            <button
              type="button"
              class="rounded px-1.5 py-0.5 {sideTab === 'filer' ? 'bg-white/10 text-paper' : 'text-paper/50 hover:text-paper'}"
              onclick={() => setSideTab('filer')}
            >Filer</button>
            <button
              type="button"
              class="rounded px-1.5 py-0.5 {sideTab === 'git' ? 'bg-white/10 text-paper' : 'text-paper/50 hover:text-paper'}"
              onclick={() => setSideTab('git')}
            >Git</button>
            <button
              type="button"
              class="rounded px-1.5 py-0.5 {sideTab === 'ext' ? 'bg-white/10 text-paper' : 'text-paper/50 hover:text-paper'}"
              onclick={() => setSideTab('ext')}
            >Utvidelser</button>
            <button
              type="button"
              class="ml-auto shrink-0 px-1 text-paper/40 hover:text-paper"
              title="skjul tre"
              aria-label="skjul tre"
              onclick={() => setTree(false)}
            >‹</button>
          </div>
          <div class="min-h-0 flex-1">
            {#if sideTab === 'filer'}
              <Tree bind:current={diskPath} reveal={diskPath} {dirty} tick={treeTick} onopen={openDisk} />
            {:else if sideTab === 'git'}
              <GitPane onopen={openDisk} ondone={() => (treeTick += 1)} tick={treeTick} />
            {:else}
              <ExtensionsPane />
            {/if}
          </div>
        </div>
      {:else}
        <button
          type="button"
          class="w-6 shrink-0 border-r border-white/10 text-paper/40 hover:bg-white/5 hover:text-paper"
          title="vis tre"
          aria-label="vis tre"
          onclick={() => setTree(true)}
        >›</button>
      {/if}
      <div class="min-h-0 min-w-0 flex-1">
        <Split direction="horizontal" bind:value={splitH} min={48} max={88}>
          {#snippet a()}
            {#if ptyOpen}
              <Split direction="vertical" bind:value={splitV} min={40} max={88}>
                {#snippet a()}
                  {@render editorPreview()}
                {/snippet}
                {#snippet b()}
                  {@render ptyPane()}
                {/snippet}
              </Split>
            {:else}
              {@render editorPreview()}
            {/if}
          {/snippet}
          {#snippet b()}
            {@render chatPane()}
          {/snippet}
        </Split>
      </div>
    </div>
  {/if}
</div>

{#if wsDlg}
  <WorkspacePicker
    mode={wsDlg}
    oncancel={() => (wsDlg = null)}
    ondone={(j) => applyWorkspace(j as Record<string, unknown>)}
  />
{/if}

{#if hiroshima}
  {#if hiroshimaW < 100}
    <div
      class="fixed inset-y-0 left-0 z-40 bg-black/45"
      style="width: {100 - hiroshimaW}vw"
      onclick={() => {
        if (!hiroDragging) hiroshima = false
      }}
      role="presentation"
    ></div>
  {/if}
  <aside
    class="fixed inset-y-0 right-0 z-50 flex flex-col border-l border-alert/40 bg-ink shadow-2xl"
    style="width: {hiroshimaW}vw"
  >
    <button
      type="button"
      class="absolute inset-y-0 left-0 z-20 w-2 cursor-ew-resize bg-alert/50 hover:bg-clean"
      aria-label="endre Hiroshima-bredde"
      onmousedown={startHiroDrag}
    ></button>
    <div class="flex items-center gap-3 border-b border-white/10 px-4 py-2 pl-6">
      <strong class="text-alert">Hiroshima</strong>
      <span class="text-xs text-paper/50">dra venstre kant · {Math.round(hiroshimaW)}vw</span>
      <button class="ml-auto text-sm" onclick={() => setHiroshimaW(100)}>full</button>
      <button class="text-sm" onclick={() => setHiroshimaW(56)}>halv</button>
      <button class="text-sm" onclick={() => (hiroshima = false)}>lukk</button>
    </div>
    <div class="min-h-0 flex-1" class:pointer-events-none={hiroDragging}>
      <Hiroshima />
    </div>
  </aside>
{/if}
{#if hiroDragging}
  <div class="fixed inset-0 z-[60] cursor-ew-resize" role="presentation"></div>
{/if}
