<script lang="ts">
  import { onMount } from 'svelte'
  import Tree from './Tree.svelte'

  let {
    rel = '',
    current = $bindable(''),
    onopen,
    depth = 0,
  }: {
    rel?: string
    current?: string
    onopen: (path: string) => void
    depth?: number
  } = $props()

  type Entry = { path: string; name: string; dir: boolean }
  let entries = $state<Entry[]>([])
  let rootName = $state('kalived')
  let expanded = $state<Record<string, boolean>>({})

  async function load() {
    const q = rel ? '?path=' + encodeURIComponent(rel) : ''
    const r = await fetch('/v1/workspace/tree' + q)
    const j = await r.json()
    if (!rel) rootName = String(j.root || '').split('/').pop() || 'kalived'
    entries = j.entries || []
  }

  onMount(() => {
    load()
  })

  function toggle(p: string) {
    expanded = { ...expanded, [p]: !expanded[p] }
  }
</script>

<div class="h-full min-h-0 text-xs" class:root={!rel}>
  {#if !rel}
    <div class="flex items-center justify-between border-b border-white/10 px-2 py-1 text-paper/50">
      <span>{rootName}</span>
      <button type="button" class="text-paper/40 hover:text-paper" onclick={load}>oppdater</button>
    </div>
  {/if}
  <div class={rel ? '' : 'min-h-0 flex-1 overflow-y-auto py-1'} style={!rel ? 'height: calc(100% - 1.75rem)' : ''}>
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
            <Tree rel={e.path} bind:current {onopen} depth={depth + 1} />
          {/if}
        </div>
      {:else}
        <button
          type="button"
          class="flex w-full truncate py-0.5 pr-2 text-left hover:bg-white/10 {current === e.path
            ? 'bg-paper/10 text-clean'
            : 'text-paper/90'}"
          style="padding-left: {1.15 + depth * 0.75}rem"
          onclick={() => onopen(e.path)}
        >
          {e.name}
        </button>
      {/if}
    {/each}
  </div>
</div>
