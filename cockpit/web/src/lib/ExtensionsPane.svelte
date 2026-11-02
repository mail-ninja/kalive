<script lang="ts">
  import { onMount } from 'svelte'

  type Ext = {
    id: string
    namespace?: string
    name?: string
    display?: string
    version?: string
    description?: string
    enabled?: boolean
    source?: string
    kalived?: boolean
    contributes?: string[]
    download?: string
  }

  let q = $state('')
  let hits = $state<Ext[]>([])
  let installed = $state<Ext[]>([])
  let err = $state('')
  let note = $state('')
  let searching = $state(false)
  let busy = $state('')
  let timer: number | undefined

  async function loadInstalled() {
    const r = await fetch('/v1/extensions')
    const j = await r.json()
    installed = Array.isArray(j.extensions) ? j.extensions : []
  }

  async function search() {
    searching = true
    err = ''
    try {
      const r = await fetch('/v1/extensions/search?q=' + encodeURIComponent(q.trim()))
      const j = await r.json()
      if (!r.ok) {
        err = String(j.detail || j.error || 'søk feilet')
        hits = []
        return
      }
      hits = Array.isArray(j.extensions) ? j.extensions : []
    } catch {
      err = 'open-vsx nådde ikke frem'
      hits = []
    } finally {
      searching = false
    }
  }

  function onQuery() {
    if (timer) window.clearTimeout(timer)
    timer = window.setTimeout(() => {
      if (q.trim()) void search()
      else hits = []
    }, 400)
  }

  async function install(ns: string, name: string) {
    busy = ns + '.' + name
    err = ''
    note = ''
    try {
      const r = await fetch('/v1/extensions/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ namespace: ns, name }),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        err = String(j.detail || j.error || 'install feilet')
        return
      }
      note = 'installert ' + (j.id || ns + '.' + name)
      await loadInstalled()
    } finally {
      busy = ''
    }
  }

  async function onVsix(ev: Event) {
    const input = ev.currentTarget as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    err = ''
    note = ''
    busy = file.name
    try {
      const buf = await file.arrayBuffer()
      const bytes = new Uint8Array(buf)
      let bin = ''
      for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i])
      const b64 = btoa(bin)
      const r = await fetch('/v1/extensions/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vsix_b64: b64 }),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        err = String(j.detail || j.error || 'vsix feilet')
        return
      }
      note = 'installert ' + (j.id || file.name)
      await loadInstalled()
    } finally {
      busy = ''
      input.value = ''
    }
  }

  async function toggle(id: string, enabled: boolean) {
    await fetch('/v1/extensions/' + encodeURIComponent(id) + '/enable', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    await loadInstalled()
  }

  async function remove(id: string) {
    await fetch('/v1/extensions/' + encodeURIComponent(id), { method: 'DELETE' })
    await loadInstalled()
  }

  onMount(() => {
    void loadInstalled()
  })
</script>

<div class="flex h-full min-h-0 flex-col text-xs">
  <div class="min-h-0 flex-1 overflow-y-auto px-2 py-2">
    <p class="mb-2 text-paper/40">Open VSX · VSIX — pakker lagres under ~/.config/kalived/extensions. VS Code-API kjører her bare med contributes.kalived.</p>
    <input
      class="mb-2 w-full rounded border border-white/15 bg-ink px-2 py-1"
      bind:value={q}
      oninput={onQuery}
      placeholder="søk utvidelser"
    />
    <label class="mb-3 block text-paper/45">
      installer .vsix
      <input class="mt-1 block w-full text-[0.65rem]" type="file" accept=".vsix,.zip" onchange={onVsix} />
    </label>

    {#if searching}
      <p class="mb-2 text-paper/35">søker…</p>
    {/if}
    {#if hits.length}
      <div class="mb-3">
        <div class="mb-1 text-[0.65rem] uppercase tracking-wide text-paper/40">Open VSX</div>
        {#each hits as h}
          <div class="mb-2 border-b border-white/5 pb-2">
            <div class="flex items-start gap-1">
              <div class="min-w-0 flex-1">
                <div class="truncate text-paper/90">{h.display || h.id}</div>
                <div class="truncate text-paper/40">{h.id} {h.version}</div>
              </div>
              <button
                type="button"
                class="shrink-0 rounded border border-white/15 px-2 py-0.5 hover:bg-white/10"
                disabled={!!busy}
                onclick={() => h.namespace && h.name && install(h.namespace, h.name)}
              >installer</button>
            </div>
            {#if h.description}
              <p class="mt-0.5 line-clamp-2 text-paper/45">{h.description}</p>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <div>
      <div class="mb-1 text-[0.65rem] uppercase tracking-wide text-paper/40">installert {installed.length ? '(' + installed.length + ')' : ''}</div>
      {#if !installed.length}
        <p class="text-paper/35">ingen ennå — søk eller last opp en .vsix</p>
      {:else}
        {#each installed as e}
          <div class="mb-2 border-b border-white/5 pb-2">
            <div class="truncate text-paper/90">{e.display || e.id}</div>
            <div class="text-paper/40">{e.id} · {e.version}{#if e.kalived} · kalived{/if}</div>
            <div class="mt-1 flex gap-2">
              <button type="button" class="text-paper/50 hover:text-paper" onclick={() => toggle(e.id, !e.enabled)}>
                {e.enabled === false ? 'skru på' : 'skru av'}
              </button>
              <button type="button" class="text-paper/50 hover:text-alert" onclick={() => remove(e.id)}>fjern</button>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
  {#if err}
    <div class="border-t border-alert/30 px-2 py-1 text-alert/90">{err}</div>
  {:else if note}
    <div class="border-t border-white/10 px-2 py-1 text-clean/80">{note}</div>
  {:else if busy}
    <div class="border-t border-white/10 px-2 py-1 text-paper/40">{busy}</div>
  {/if}
</div>
