<script lang="ts">
  import { onMount } from 'svelte'

  let {
    mode = 'open',
    oncancel,
    ondone,
  }: {
    mode?: 'open' | 'new'
    oncancel: () => void
    ondone: (info: { root: string; name: string; kind?: string; project?: string; hint?: string }) => void
  } = $props()

  type Dir = { name: string; path: string; openable: boolean }
  type Crumb = { label: string; path: string }

  let here = $state('')
  let parent = $state('')
  let home = $state('')
  let hereOpenable = $state(false)
  let dirs = $state<Dir[]>([])
  let typed = $state('')
  let name = $state('')
  let gitInit = $state(true)
  let err = $state('')
  let busy = $state(false)

  let crumbs = $derived.by(() => {
    const out: Crumb[] = []
    if (!here) return out
    const parts = here.split('/').filter(Boolean)
    let acc = ''
    for (const part of parts) {
      acc += '/' + part
      out.push({ label: part, path: acc })
    }
    if (home) {
      const hi = out.findIndex((c) => c.path === home)
      if (hi >= 0) return [{ label: '~', path: home }, ...out.slice(hi + 1)]
    }
    return out
  })

  async function load(path = '') {
    err = ''
    const q = path ? '?path=' + encodeURIComponent(path) : ''
    const r = await fetch('/v1/workspace/browse' + q)
    const j = await r.json()
    if (!r.ok) {
      err = String(j.detail || j.error || 'kunne ikke liste')
      return
    }
    here = j.path || ''
    parent = j.parent || ''
    home = j.home || ''
    hereOpenable = !!j.openable
    dirs = Array.isArray(j.dirs) ? j.dirs : []
    if (mode === 'open') typed = here
  }

  async function openPath(path: string) {
    busy = true
    err = ''
    try {
      const r = await fetch('/v1/workspace/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      const j = await r.json()
      if (!r.ok) {
        err = String(j.detail || j.error || 'kunne ikke åpne')
        return
      }
      ondone(j)
    } finally {
      busy = false
    }
  }

  async function create() {
    busy = true
    err = ''
    try {
      const r = await fetch('/v1/workspace/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parent: here, name, git: gitInit }),
      })
      const j = await r.json()
      if (!r.ok) {
        err = String(j.detail || j.error || 'kunne ikke lage')
        return
      }
      ondone(j)
    } finally {
      busy = false
    }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault()
      oncancel()
    }
  }

  onMount(() => {
    void load()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
</script>

<div class="fixed inset-0 z-40 flex items-center justify-center bg-black/50" role="presentation" onclick={oncancel}>
  <div
    class="flex max-h-[80vh] w-[32rem] max-w-[92vw] flex-col rounded-lg border border-white/15 bg-ink shadow-2xl"
    role="dialog"
    aria-label={mode === 'new' ? 'ny workspace' : 'åpne mappe'}
    onclick={(e) => e.stopPropagation()}
  >
    <div class="flex items-center border-b border-white/10 px-3 py-2 text-sm">
      <strong>{mode === 'new' ? 'Ny workspace' : 'Åpne mappe'}</strong>
      <button type="button" class="ml-auto text-paper/50 hover:text-paper" onclick={oncancel}>lukk</button>
    </div>
    <div class="flex flex-wrap items-center gap-1 border-b border-white/10 px-3 py-2 text-xs">
      <button
        type="button"
        class="rounded border border-white/15 px-2 py-1 hover:bg-white/10 disabled:cursor-not-allowed disabled:border-white/10 disabled:text-paper/30 disabled:hover:bg-transparent"
        disabled={!parent}
        title={parent ? parent : 'øverst i hjemmemappa'}
        onclick={() => parent && load(parent)}
      >Mappe opp</button>
      {#if home && here !== home}
        <button
          type="button"
          class="rounded border border-white/15 px-2 py-1 hover:bg-white/10"
          onclick={() => load(home)}
        >Hjem</button>
      {/if}
      <div class="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto text-paper/55">
        {#each crumbs as c, i}
          {#if i > 0}<span class="shrink-0 text-paper/25">/</span>{/if}
          <button
            type="button"
            class="shrink-0 hover:text-paper {c.path === here ? 'text-paper' : ''}"
            onclick={() => load(c.path)}
          >{c.label}</button>
        {/each}
      </div>
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto px-3 py-2 text-xs">
      <p class="mb-2 text-paper/40">
        {mode === 'new'
          ? 'Velg mappa der den nye workspacen skal ligge.'
          : 'Klikk en mappe for å gå inn. Åpne bytter arbeidstreet.'}
      </p>
      {#each dirs as d}
        <div class="flex items-center gap-1 py-0.5">
          <button type="button" class="min-w-0 flex-1 truncate text-left hover:text-clean" onclick={() => load(d.path)}>
            {d.name}/
          </button>
          {#if mode === 'open' && d.openable}
            <button type="button" class="shrink-0 text-clean/80 hover:text-clean" onclick={() => openPath(d.path)}>åpne</button>
          {/if}
        </div>
      {/each}
      {#if !dirs.length}
        <p class="text-paper/35">ingen undermapper</p>
      {/if}
    </div>
    <div class="border-t border-white/10 px-3 py-2 text-xs">
      {#if mode === 'open'}
        <form
          class="flex flex-wrap gap-1"
          onsubmit={(e) => {
            e.preventDefault()
            openPath(typed.trim())
          }}
        >
          <input class="min-w-0 flex-1 rounded border border-white/15 bg-ink px-2 py-1" bind:value={typed} spellcheck="false" />
          <button
            type="button"
            class="rounded border border-clean/40 px-2 py-1 text-clean disabled:cursor-not-allowed disabled:border-white/10 disabled:text-paper/30"
            disabled={busy || !hereOpenable}
            title={hereOpenable ? here : 'kan ikke åpne denne mappa som workspace'}
            onclick={() => openPath(here)}
          >Åpne denne mappa</button>
          <button type="submit" class="rounded border border-white/15 px-2 py-1" disabled={busy}>åpne sti</button>
        </form>
      {:else}
        <form
          class="flex flex-col gap-1"
          onsubmit={(e) => {
            e.preventDefault()
            create()
          }}
        >
          <input class="rounded border border-white/15 bg-ink px-2 py-1" bind:value={name} placeholder="mappenavn" />
          <label class="flex items-center gap-1 text-paper/50">
            <input type="checkbox" bind:checked={gitInit} />
            git init
          </label>
          <button type="submit" class="self-start rounded border border-white/15 px-2 py-1" disabled={busy}>lag og åpne</button>
        </form>
      {/if}
      {#if err}
        <p class="mt-1 text-alert/90">{err}</p>
      {/if}
    </div>
  </div>
</div>
