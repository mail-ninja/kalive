<script lang="ts">
  import { onMount } from 'svelte'
  import Editor from './lib/Editor.svelte'
  import Hiroshima from './lib/Hiroshima.svelte'
  import Settings from './lib/Settings.svelte'
  import Split from './lib/Split.svelte'
  import Term from './lib/Term.svelte'
  import Tree from './lib/Tree.svelte'
  import { applyToolResult, getCanvas, setCanvas, subscribeCanvas } from './lib/desk'
  import { connect, send, type Frame } from './lib/ws'

  type Hist = { role: 'you' | 'bot' | 'sys' | 'tool'; text: string; name?: string; diff?: string; path?: string }

  let ws: WebSocket | null = null
  let hiroshima = $state(false)
  let hiroshimaW = $state(Number(localStorage.getItem('kalived.hiroshimaW') || 92) || 92)
  let hiroDragging = $state(false)
  let tab = $state('work')
  let hist = $state<Hist[]>([])
  let histEl: HTMLDivElement | undefined = $state()
  let draft = $state('')
  let stream = $state('')
  let tools = $state<string[]>([])
  let health = $state('…')
  let agents = $state<{ id: string; name: string; description: string; provider: string; model: string; desk?: string }[]>([])
  let providers = $state<{ id: string; label: string; models: string[] }[]>([])
  let agentId = $state('build')
  let providerId = $state('xai')
  let modelId = $state('grok-4.6')
  let splitH = $state(36)
  let splitV = $state(94)
  let splitTree = $state(22)
  let allowMutate = $state(false)
  let canvasUi = $state(getCanvas())
  let details = $state(false)
  let ptyOpen = $state(false)
  let running = $state(false)
  let diskPath = $state('README.md')
  let wsName = $state('kalived')
  let models = $derived(providers.find((p) => p.id === providerId)?.models ?? [])
  let team = $derived(agents.filter((a) => ['build', 'review', 'forge', 'term', 'crew'].includes(a.id)))

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
    }
    if (f.ch === 'run' && f.type === 'stopped') {
      running = false
      hist = [...hist, { role: 'sys', text: 'stoppet — logger og diff beholdt' }]
      stream = ''
    }
    if (f.ch === 'tools' && f.type === 'list') {
      const list = f.payload.tools as { name: string }[] | undefined
      tools = (list ?? []).map((t) => t.name)
    }
    if (f.ch === 'tools' && f.type === 'call') {
      hist = [...hist, { role: 'tool', name: String(f.payload.name || ''), text: `runde ${f.payload.round ?? '?'}` }]
    }
    if (f.ch === 'tools' && f.type === 'result') {
      const r = f.payload.result as Record<string, unknown> | undefined
      applyToolResult(r)
      if (typeof r?.path === 'string' && r.wrote) diskPath = r.path
      const diff = typeof r?.diff === 'string' ? r.diff : ''
      const bit = r && (r.error || r.path || r.n || r.agent)
      hist = [
        ...hist,
        {
          role: 'tool',
          name: String(f.payload.name || ''),
          path: typeof r?.path === 'string' ? r.path : undefined,
          diff,
          text: String(bit ?? JSON.stringify(r ?? {}).slice(0, 280)),
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
    queueMicrotask(() => {
      if (histEl) histEl.scrollTop = histEl.scrollHeight
    })
  })

  onMount(() => {
    fetch('/v1/health')
      .then((r) => r.json())
      .then((j) => {
        health = j.ok ? 'cockpit :8788' : 'health fail'
      })
      .catch(() => {
        health = 'backend nede — kjør cockpit/scripts/dev.sh'
      })
    const offCanvas = subscribeCanvas((c) => {
      canvasUi = c
    })
    fetch('/v1/workspace')
      .then((r) => r.json())
      .then((j) => {
        if (j.name) wsName = j.name
      })
      .catch(() => {})
    fetch('/v1/agents')
      .then((r) => r.json())
      .then((j) => {
        if (Array.isArray(j.agents)) agents = j.agents
        if (Array.isArray(j.providers) && j.providers.length) providers = j.providers
      })
      .catch(() => {})
    let stop = false
    const boot = () => {
      if (stop) return
      const s = connect(onFrame)
      ws = s
      s.addEventListener('close', () => {
        if (!stop) setTimeout(boot, 1500)
      })
    }
    boot()
    return () => {
      stop = true
      offCanvas()
      ws?.close()
    }
  })

  function stopAll() {
    if (ws) send(ws, 'run', 'stop', {})
    running = false
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
    await fetch('/v1/workspace/file', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: diskPath, text: c.text }),
    })
  }

  async function openDisk(p: string) {
    diskPath = p
    setCanvas({ path: p, mode: 'monaco' })
  }

  function say() {
    const t = draft.trim()
    if (!t || !ws) return
    running = true
    hist = [...hist, { role: 'you', text: t }]
    send(ws, 'chat', 'user', {
      text: t,
      agent: agentId,
      provider: providerId,
      model: modelId,
      allow_mutate: allowMutate,
    })
    draft = ''
  }
</script>

<div class="flex h-full min-h-screen flex-col">
  <header class="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-3">
    <div class="font-serif text-xl tracking-wide">cockpit</div>
    <span class="text-xs text-clean/80">{wsName}</span>
    <span class="text-xs text-paper/40">{health}</span>
    <div class="ml-auto flex flex-wrap items-center gap-2">
      <button
        class="rounded-full border border-white/15 px-3 py-1 text-sm hover:bg-white/10"
        class:bg-paper={tab === 'work'}
        class:text-ink={tab === 'work'}
        onclick={() => (tab = 'work')}
      >
        Arbeid
      </button>
      <button
        class="rounded-full border border-white/15 px-3 py-1 text-sm hover:bg-white/10"
        class:bg-paper={tab === 'settings'}
        class:text-ink={tab === 'settings'}
        onclick={() => (tab = 'settings')}
      >
        Settings
      </button>
      <button type="button" class="text-xs text-paper/50 underline" onclick={() => (details = !details)}>
        kjøredetaljer
      </button>
      <label class="flex items-center gap-1 text-xs text-paper/60">
        <input type="checkbox" bind:checked={allowMutate} />
        agent får kjøre
      </label>
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
  {#if details}
    <div class="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-2 text-xs">
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
          onchange={() => ws && send(ws, 'agents', 'select', { id: agentId })}
        >
          {#each agents as a}
            <option value={a.id}>{a.name}</option>
          {/each}
        </select>
      </label>
    </div>
  {/if}

  {#if tab === 'settings'}
    <Settings />
  {:else}
  <div class="min-h-0 flex-1 p-2">
    <Split direction="horizontal" bind:value={splitH}>
      {#snippet a()}
        <section class="flex h-full min-h-0 flex-col p-2">
          <h2 class="mb-1 font-serif text-lg">agentkonsoll</h2>
          {#if agents.length}
            {@const cur = agents.find((x) => x.id === agentId)}
            {#if cur}
              <p class="mb-2 text-xs text-paper/50">{cur.description}</p>
            {/if}
          {/if}
          {#if team.length}
            <div class="mb-2 flex flex-wrap gap-1">
              {#each team as a}
                <button
                  type="button"
                  class="rounded-full border border-white/15 px-2 py-0.5 text-xs"
                  class:bg-paper={agentId === a.id}
                  class:text-ink={agentId === a.id}
                  onclick={() => {
                    agentId = a.id
                    ws && send(ws, 'agents', 'select', { id: a.id })
                  }}>{a.name}</button>
              {/each}
            </div>
          {/if}
          <div class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-white/10 bg-black/40">
            <div class="flex items-center justify-between border-b border-white/10 px-3 py-1.5 text-xs text-paper/50">
              <span>{running ? 'kjører…' : 'klar'}</span>
              <span>{hist.length}</span>
            </div>
            <div bind:this={histEl} class="chat-hist min-h-0 flex-1 space-y-2 overflow-y-scroll p-3 text-sm">
              {#each hist as m}
                {#if m.role === 'tool'}
                  <div class="bubble sys">
                    <div class="who">{m.name || 'tool'}{#if m.path} · {m.path}{/if}</div>
                    <div>{m.text}</div>
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
            class="mt-2 flex gap-2"
            onsubmit={(e) => {
              e.preventDefault()
              say()
            }}
          >
            <input
              class="flex-1 rounded-lg border border-white/15 bg-ink px-3 py-2"
              bind:value={draft}
              placeholder="oppgave til {agentId}"
            />
            <button class="rounded-lg bg-paper px-3 py-2 text-ink">send</button>
          </form>
        </section>
      {/snippet}
      {#snippet b()}
        <Split direction="vertical" bind:value={splitV}>
          {#snippet a()}
            <div class="flex h-full min-h-0 flex-col p-2">
              <div class="mb-1 flex flex-wrap items-center gap-2">
                <h2 class="font-serif text-lg">workspace</h2>
                <button
                  class="rounded-full border border-white/15 px-2 py-0.5 text-xs"
                  class:bg-paper={canvasUi.mode === 'monaco'}
                  class:text-ink={canvasUi.mode === 'monaco'}
                  onclick={() => setCanvas({ mode: 'monaco' })}
                >kode</button>
                <button
                  class="rounded-full border border-white/15 px-2 py-0.5 text-xs"
                  class:bg-paper={canvasUi.mode === 'iframe'}
                  class:text-ink={canvasUi.mode === 'iframe'}
                  onclick={() => setCanvas({ mode: 'iframe' })}
                >preview</button>
                <button type="button" class="rounded-full border border-white/15 px-2 py-0.5 text-xs" onclick={saveDisk}
                  >lagre</button>
                <button
                  type="button"
                  class="rounded-full bg-clean px-2 py-0.5 text-xs text-ink"
                  onclick={() => {
                    setCanvas({ mode: 'iframe', path: diskPath, rev: (getCanvas().rev || 0) + 1 })
                  }}>preview fil</button>
                <button
                  type="button"
                  class="rounded-full border border-white/15 px-2 py-0.5 text-xs"
                  onclick={() => {
                    ptyOpen = !ptyOpen
                    splitV = ptyOpen ? 70 : 94
                  }}
                >{ptyOpen ? 'skjul PTY' : 'PTY (ikke agent)'}</button>
                <span class="text-xs text-paper/40">{diskPath}</span>
              </div>
              <div class="min-h-0 flex-1">
                <Split direction="horizontal" bind:value={splitTree}>
                  {#snippet a()}
                    <Tree bind:current={diskPath} onopen={openDisk} />
                  {/snippet}
                  {#snippet b()}
                    <Editor diskPath={diskPath} />
                  {/snippet}
                </Split>
              </div>
            </div>
          {/snippet}
          {#snippet b()}
            {#if ptyOpen}
              <div class="flex h-full min-h-0 flex-col p-2">
                <h2 class="mb-1 font-serif text-lg">PTY <span class="text-xs font-sans text-paper/40">ikke agent</span></h2>
                <div class="min-h-0 flex-1">
                  <Term />
                </div>
              </div>
            {:else}
              <div class="flex h-full items-center justify-center text-xs text-paper/40">
                <button type="button" class="underline" onclick={() => (ptyOpen = true)}>åpne PTY (passord her)</button>
              </div>
            {/if}
          {/snippet}
        </Split>
      {/snippet}
    </Split>
  </div>
  {/if}
</div>

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
