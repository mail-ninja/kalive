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

  let here = $state('')
  let parent = $state('')
  let home = $state('')
  let dirs = $state<Dir[]>([])
  let typed = $state('')
  let name = $state('')
  let gitInit = $state(true)
  let err = $state('')
  let busy = $state(false)

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

  onMount(() => {
    void load()
  })
</script>

<div class="fixed inset-0 z-40 flex items-center justify-center bg-black/50" role="presentation" onclick={oncancel}>
  <div
    class="flex max-h-[80vh] w-[28rem] max-w-[92vw] flex-col rounded-lg border border-white/15 bg-ink shadow-2xl"
    role="dialog"
    aria-label={mode === 'new' ? 'ny workspace' : 'åpne mappe'}
    onclick={(e) => e.stopPropagation()}
  >
    <div class="flex items-center border-b border-white/10 px-3 py-2 text-sm">
      <strong>{mode === 'new' ? 'Ny workspace' : 'Åpne mappe'}</strong>
      <button type="button" class="ml-auto text-paper/50 hover:text-paper" onclick={oncancel}>lukk</button>
    </div>
    <div class="min-h-0 flex-1 overflow-y-auto px-3 py-2 text-xs">
      <div class="mb-2 flex items-center gap-1 text-paper/50">
        {#if parent}
          <button type="button" class="hover:text-paper" onclick={() => load(parent)}>…</button>
        {/if}
        <span class="truncate" title={here}>{here}</span>
      </div>
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
          class="flex gap-1"
          onsubmit={(e) => {
            e.preventDefault()
            openPath(typed.trim())
          }}
        >
          <input class="min-w-0 flex-1 rounded border border-white/15 bg-ink px-2 py-1" bind:value={typed} spellcheck="false" />
          <button type="submit" class="rounded border border-white/15 px-2 py-1" disabled={busy}>åpne</button>
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
