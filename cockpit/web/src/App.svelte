<script lang="ts">
  import { onMount } from 'svelte'
  import Editor from './lib/Editor.svelte'
  import Settings from './lib/Settings.svelte'
  import { connect, send, type Frame } from './lib/ws'

  let ws: WebSocket | null = null
  let hiroshima = $state(false)
  let tab = $state<'work' | 'settings'>('work')
  let log = $state<string[]>([])
  let draft = $state('')
  let stream = $state('')
  let tools = $state<string[]>([])
  let health = $state('…')

  function onFrame(f: Frame) {
    if (f.ch === 'chat' && f.type === 'token') {
      stream += String(f.payload.text ?? '')
    }
    if (f.ch === 'chat' && f.type === 'done') {
      log = [...log, stream]
      stream = ''
    }
    if (f.ch === 'tools' && f.type === 'list') {
      const list = f.payload.tools as { name: string }[] | undefined
      tools = (list ?? []).map((t) => t.name)
    }
    if (f.ch === 'log' && f.type === 'line') {
      log = [...log, String(f.payload.text ?? '')]
    }
    if (f.ch === 'hiroshima' && f.type === 'open') hiroshima = true
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
    ws = connect(onFrame)
    return () => ws?.close()
  })

  function say() {
    const t = draft.trim()
    if (!t || !ws) return
    log = [...log, 'you: ' + t]
    send(ws, 'chat', 'user', { text: t })
    draft = ''
  }
</script>

<div class="flex h-full min-h-screen flex-col">
  <header class="flex flex-wrap items-center gap-3 border-b border-white/10 px-4 py-3">
    <div class="font-serif text-xl tracking-wide">cockpit</div>
    <span class="text-xs text-clean/80">{health}</span>
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
  <div class="grid flex-1 grid-cols-1 gap-0 md:grid-cols-2">
    <section class="flex flex-col border-r border-white/10 p-4">
      <h2 class="mb-2 font-serif text-lg">chat (ws)</h2>
      <div class="min-h-0 flex-1 space-y-2 overflow-auto rounded-lg bg-black/30 p-3 text-sm">
        {#each log as line}
          <p class="whitespace-pre-wrap text-paper/90">{line}</p>
        {/each}
        {#if stream}
          <p class="text-clean">{stream}</p>
        {/if}
      </div>
      <form
        class="mt-3 flex gap-2"
        onsubmit={(e) => {
          e.preventDefault()
          say()
        }}
      >
        <input
          class="flex-1 rounded-lg border border-white/15 bg-ink px-3 py-2"
          bind:value={draft}
          placeholder="si noe — stream kommer over ws"
        />
        <button class="rounded-lg bg-paper px-3 py-2 text-ink">send</button>
      </form>
    </section>
    <section class="flex min-h-[20rem] flex-col p-4">
      <h2 class="mb-2 font-serif text-lg">monaco</h2>
      <div class="min-h-0 flex-1">
        <Editor />
      </div>
    </section>
  </div>
  {/if}
</div>

{#if hiroshima}
  <div class="fixed inset-0 z-40 bg-black/50" onclick={() => (hiroshima = false)} role="presentation"></div>
  <aside
    class="fixed inset-y-0 right-0 z-50 flex w-full max-w-3xl flex-col border-l border-alert/40 bg-ink shadow-2xl"
  >
    <div class="flex items-center justify-between border-b border-white/10 px-4 py-2">
      <strong class="text-alert">Hiroshima</strong>
      <span class="text-xs text-paper/50">iframe → :8787 (urørt SOC)</span>
      <button class="text-sm" onclick={() => (hiroshima = false)}>lukk</button>
    </div>
    <iframe title="hiroshima" class="h-full w-full flex-1 bg-black" src="http://127.0.0.1:8787/"></iframe>
  </aside>
{/if}
