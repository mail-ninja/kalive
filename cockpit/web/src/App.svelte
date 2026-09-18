<script lang="ts">
  import { onMount } from 'svelte'
  import Editor from './lib/Editor.svelte'
  import Hiroshima from './lib/Hiroshima.svelte'
  import Settings from './lib/Settings.svelte'
  import Split from './lib/Split.svelte'
  import Term from './lib/Term.svelte'
  import { connect, send, type Frame } from './lib/ws'

  type Hist = { role: 'you' | 'bot' | 'sys'; text: string }

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
  let agents = $state<{ id: string; name: string; description: string; provider: string; model: string }[]>([])
  let providers = $state<{ id: string; label: string; models: string[] }[]>([])
  let agentId = $state('dummy')
  let providerId = $state('xai')
  let modelId = $state('grok-4.6')
  let splitH = $state(42)
  let splitV = $state(62)
  let allowMutate = $state(false)
  let models = $derived(providers.find((p) => p.id === providerId)?.models ?? [])

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
      hist = [...hist, { role: 'bot', text: stream }]
      stream = ''
    }
    if (f.ch === 'chat' && f.type === 'error') {
      hist = [...hist, { role: 'sys', text: 'error: ' + String(f.payload.error ?? 'ukjent') }]
      stream = ''
    }
    if (f.ch === 'tools' && f.type === 'list') {
      const list = f.payload.tools as { name: string }[] | undefined
      tools = (list ?? []).map((t) => t.name)
    }
    if (f.ch === 'tools' && f.type === 'call') {
      hist = [...hist, { role: 'sys', text: `runde ${f.payload.round ?? '?'} → ${f.payload.name}` }]
    }
    if (f.ch === 'tools' && f.type === 'result') {
      const r = f.payload.result as Record<string, unknown> | undefined
      const bit = r && (r.verdict || r.error || r.pong)
      hist = [
        ...hist,
        {
          role: 'sys',
          text: `${f.payload.name}: ${typeof bit === 'object' ? JSON.stringify(bit) : String(bit ?? JSON.stringify(r ?? {}).slice(0, 240))}`,
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
      ws?.close()
    }
  })

  function say() {
    const t = draft.trim()
    if (!t || !ws) return
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
    <span class="text-xs text-clean/80">{health}</span>
    <label class="flex items-center gap-1 text-xs text-paper/60">
      provider
      <select
        class="rounded-full border border-white/15 bg-ink px-2 py-1 text-sm text-paper"
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
    <label class="flex items-center gap-1 text-xs text-paper/60">
      modell
      <select class="rounded-full border border-white/15 bg-ink px-2 py-1 text-sm text-paper" bind:value={modelId}>
        {#each models as m}
          <option value={m}>{m}</option>
        {/each}
      </select>
    </label>
    <label class="flex items-center gap-1 text-xs text-paper/60">
      type
      <select
        class="rounded-full border border-white/15 bg-ink px-2 py-1 text-sm text-paper"
        bind:value={agentId}
        onchange={() => ws && send(ws, 'agents', 'select', { id: agentId })}
      >
        {#each agents as a}
          <option value={a.id}>{a.name}</option>
        {/each}
      </select>
    </label>
    <div class="ml-auto flex gap-2">
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
      <button
        class="rounded-full border border-white/15 px-3 py-1 text-sm hover:bg-white/10"
        onclick={() => ws && send(ws, 'tools', 'call', { name: 'ping', args: { n: 1 } })}
      >
        ping {tools.join(',')}
      </button>
      <label class="flex items-center gap-1 text-xs text-paper/60">
        <input type="checkbox" bind:checked={allowMutate} />
        agent får kjøre
      </label>
      <button
        class="rounded-full bg-alert px-3 py-1 text-sm font-semibold text-ink"
        onclick={() => (hiroshima = !hiroshima)}
      >
        Hiroshima
      </button>
    </div>
  </header>

  {#if tab === 'settings'}
    <Settings />
  {:else}
  <div class="min-h-0 flex-1 p-2">
    <Split direction="horizontal" bind:value={splitH}>
      {#snippet a()}
        <section class="flex h-full min-h-0 flex-col p-2">
          <h2 class="mb-1 font-serif text-lg">chat</h2>
          {#if agents.length}
            {@const cur = agents.find((x) => x.id === agentId)}
            {#if cur}
              <p class="mb-2 text-xs text-paper/50">{cur.description}</p>
            {/if}
          {/if}
          <div class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-white/10 bg-black/40">
            <div class="flex items-center justify-between border-b border-white/10 px-3 py-1.5 text-xs text-paper/50">
              <span>historikk</span>
              <span>{hist.length} meldinger</span>
            </div>
            <div bind:this={histEl} class="chat-hist min-h-0 flex-1 space-y-2 overflow-y-scroll p-3 text-sm">
              {#each hist as m}
                <div class="bubble {m.role}">
                  <div class="who">{m.role === 'you' ? 'du' : m.role === 'bot' ? agentId : 'sys'}</div>
                  {m.text}
                </div>
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
              placeholder="si noe — {providerId}/{modelId}/{agentId}"
            />
            <button class="rounded-lg bg-paper px-3 py-2 text-ink">send</button>
          </form>
        </section>
      {/snippet}
      {#snippet b()}
        <Split direction="vertical" bind:value={splitV}>
          {#snippet a()}
            <div class="flex h-full min-h-0 flex-col p-2">
              <h2 class="mb-1 font-serif text-lg">monaco</h2>
              <div class="min-h-0 flex-1">
                <Editor />
              </div>
            </div>
          {/snippet}
          {#snippet b()}
            <div class="flex h-full min-h-0 flex-col p-2">
              <h2 class="mb-1 font-serif text-lg">terminal</h2>
              <div class="min-h-0 flex-1">
                <Term />
              </div>
            </div>
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
