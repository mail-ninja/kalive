<script lang="ts">
  import { onMount } from 'svelte'

  let {
    current = $bindable(''),
    onopen,
  }: {
    current?: string
    onopen: (path: string) => void
  } = $props()

  type Node = { path: string; name: string; dir: boolean }
  let nodes = $state<Node[]>([])
  let root = $state('kalived')

  async function load() {
    const r = await fetch('/v1/workspace/tree?depth=3')
    const j = await r.json()
    root = String(j.root || '').split('/').pop() || 'kalived'
    nodes = j.nodes || []
  }

  onMount(() => {
    load()
  })

  const files = $derived(nodes.filter((n) => !n.dir))
  const dirs = $derived(nodes.filter((n) => n.dir))
</script>

<div class="flex h-full min-h-0 flex-col text-xs">
  <div class="flex items-center justify-between border-b border-white/10 px-2 py-1 text-paper/50">
    <span>{root}</span>
    <button type="button" class="text-paper/40 hover:text-paper" onclick={load}>oppdater</button>
  </div>
  <div class="min-h-0 flex-1 overflow-y-auto py-1">
    {#each dirs as d}
      <div class="truncate px-2 py-0.5 text-paper/35">{d.path}/</div>
    {/each}
    {#each files as f}
      <button
        type="button"
        class="block w-full truncate px-2 py-0.5 text-left hover:bg-white/10"
        class:bg-white/10={current === f.path}
        class:text-clean={current === f.path}
        onclick={() => onopen(f.path)}
      >
        {f.path}
      </button>
    {/each}
  </div>
</div>
