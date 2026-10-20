<script lang="ts">
  import { onMount } from 'svelte'
  import Tree from './Tree.svelte'

  let {
    rel = '',
    current = $bindable(''),
    reveal = '',
    dirty = {},
    tick = 0,
    onopen,
    onnew,
    depth = 0,
  }: {
    rel?: string
    current?: string
    reveal?: string
    dirty?: Record<string, boolean>
    tick?: number
    onopen: (path: string) => void
    onnew?: () => void
    depth?: number
  } = $props()

  type Entry = { path: string; name: string; dir: boolean }
  let entries = $state<Entry[]>([])
  let rootName = $state('kalived')
  let expanded = $state<Record<string, boolean>>({})
  let status = $state<'loading' | 'ok' | 'err'>('loading')

  async function load() {
    status = 'loading'
    try {
      const q = rel ? '?path=' + encodeURIComponent(rel) : ''
      const r = await fetch('/v1/workspace/tree' + q)
      const j = await r.json()
      if (!rel) rootName = String(j.root || '').split('/').pop() || 'kalived'
      entries = j.entries || []
      status = 'ok'
    } catch {
      status = 'err'
    }
  }

  function nextDir(from: string, path: string): string | null {
    if (!path) return null
    if (from) {
      if (path === from || !path.startsWith(from + '/')) return null
      const rest = path.slice(from.length + 1)
      const seg = rest.split('/')[0]
      if (!seg || rest === seg) return null
      return from + '/' + seg
    }
    if (!path.includes('/')) return null
    return path.split('/')[0]
  }

  let lastTick = 0
  onMount(() => {
    void load()
  })

  $effect(() => {
    const t = tick
    if (t !== lastTick) {
      lastTick = t
      void load()
    }
  })

  $effect(() => {
    const child = nextDir(rel, reveal)
    if (!child || expanded[child]) return
    expanded = { ...expanded, [child]: true }
  })

  function toggle(p: string) {
    expanded = { ...expanded, [p]: !expanded[p] }
  }
</script>

<div class="h-full min-h-0 text-xs" class:root={!rel}>
  {#if !rel}
    <div class="flex items-center justify-between gap-2 border-b border-white/10 px-2 py-1 text-paper/50">
      <span class="truncate">{rootName}</span>
      <span class="flex shrink-0 gap-2">
        {#if onnew}
          <button type="button" class="text-paper/40 hover:text-paper" onclick={onnew}>ny fil</button>
        {/if}
        <button type="button" class="text-paper/40 hover:text-paper" onclick={load}>oppdater</button>
      </span>
    </div>
  {/if}
  <div class={rel ? '' : 'min-h-0 flex-1 overflow-y-auto py-1'} style={!rel ? 'height: calc(100% - 1.75rem)' : ''}>
    {#if !rel && status === 'loading' && entries.length === 0}
      <div class="px-2 py-1 text-paper/40">laster…</div>
    {:else if !rel && status === 'err' && entries.length === 0}
      <div class="px-2 py-1 text-alert/80">treet fikk ikke lastet</div>
    {/if}
    {#each entries as e}
      {#if e.dir}
        <div>
          <button
            type="button"
            class="flex w-full items-center gap-1 truncate py-0.5 pr-2 text-left text-paper/70 hover:bg-white/10"
            style="padding-left: {0.4 + depth * 0.75}rem"
            onclick={() => toggle(e.path)}
          >
            <span class="w-3 shrink-0 text-paper/40">{expanded[e.path] ? '▾' : '▸'}</span>
            <span class="truncate">{e.name}</span>
          </button>
          {#if expanded[e.path]}
            <Tree rel={e.path} bind:current {reveal} {dirty} {tick} {onopen} {onnew} depth={depth + 1} />
          {/if}
        </div>
      {:else}
        <button
          type="button"
          class="flex w-full items-center gap-1 truncate py-0.5 pr-2 text-left hover:bg-white/10 {current === e.path
            ? 'bg-paper/10 text-clean'
            : 'text-paper/90'}"
          style="padding-left: {1.15 + depth * 0.75}rem"
          onclick={() => onopen(e.path)}
        >
          <span class="truncate">{e.name}</span>
          {#if dirty[e.path]}
            <span class="ml-auto shrink-0 text-warn" title="endret">●</span>
          {/if}
        </button>
      {/if}
    {/each}
  </div>
</div>
