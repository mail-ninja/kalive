<script lang="ts">
  import { onMount } from 'svelte'

  let {
    onopen,
    ondone,
    tick = 0,
  }: {
    onopen: (path: string) => void
    ondone?: () => void
    tick?: number
  } = $props()

  type FileRow = { xy: string; path: string }
  type Remote = { name: string; fetch: string; push: string; ssh?: boolean; github?: boolean; blocked?: boolean }
  type Commit = { sha: string; subject: string; author: string }

  let loading = $state(true)
  let isRepo = $state(true)
  let err = $state('')
  let note = $state('')
  let branch = $state('')
  let upstream = $state('')
  let ahead = $state(0)
  let behind = $state(0)
  let files = $state<FileRow[]>([])
  let remotes = $state<Remote[]>([])
  let commits = $state<Commit[]>([])
  let msg = $state('')
  let remote = $state('kalive')
  let ghLogin = $state<string | null>(null)
  let ghSet = $state(false)
  let ghHint = $state('')
  let token = $state('')
  let busy = $state('')
  let remoteName = $state('')
  let remoteUrl = $state('')

  let staged = $derived(files.filter((f) => f.xy[0] !== ' ' && f.xy !== '??'))
  let selected = $derived(remotes.find((r) => r.name === remote) || null)

  function destHint(r: Remote): string {
    const url = r.push || r.fetch || ''
    const m = url.match(/github\.com[:/]([^/]+\/[^/.]+?)(?:\.git)?$/i)
    if (m) return m[1]
    return url
  }

  function xyLabel(xy: string) {
    const x = xy[0] || ' '
    const y = xy[1] || ' '
    if (xy.trim() === '??') return 'ny'
    if (x !== ' ' && y !== ' ') return 'staged+endret'
    if (x !== ' ') return 'staged'
    return 'endret'
  }

  async function load() {
    loading = true
    err = ''
    try {
      const [st, lg, gh] = await Promise.all([
        fetch('/v1/git/status').then((r) => r.json()),
        fetch('/v1/git/log?n=8').then((r) => r.json()),
        fetch('/v1/git/github').then((r) => r.json()),
      ])
      isRepo = st.repo !== false
      if (isRepo && (st.error || st.detail)) err = String(st.error || st.detail)
      else err = ''
      branch = st.branch || ''
      upstream = st.upstream || ''
      ahead = Number(st.ahead || 0)
      behind = Number(st.behind || 0)
      files = Array.isArray(st.files) ? st.files : []
      remotes = Array.isArray(st.remotes) ? st.remotes : []
      const saved = localStorage.getItem('kalived.ui.git.remote') || ''
      if (saved && remotes.some((r) => r.name === saved)) remote = saved
      else if (!remotes.some((r) => r.name === remote)) {
        remote = remotes.some((r) => r.name === 'kalive') ? 'kalive' : remotes[0]?.name || remote
      }
      commits = Array.isArray(lg.commits) ? lg.commits : []
      ghLogin = gh.login || null
      ghSet = !!gh.set
      ghHint = gh.hint || ''
    } catch {
      err = 'git-status nådde ikke :8788'
    } finally {
      loading = false
    }
  }

  async function call(path: string, method: string, body?: unknown) {
    busy = path
    err = ''
    note = ''
    try {
      const r = await fetch(path, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        err = String(j.detail || j.error || r.status)
        return
      }
      if (j.repo === false) isRepo = false
      else if (j.repo === true) isRepo = true
      if (j.action === 'remote-add' && j.remote) {
        remote = String(j.remote)
        try {
          localStorage.setItem('kalived.ui.git.remote', remote)
        } catch {
          /* ignore */
        }
      }
      note = String(j.summary || j.sha || 'ok')
      ondone?.()
      await load()
    } finally {
      busy = ''
    }
  }

  async function login(e: Event) {
    e.preventDefault()
    await call('/v1/git/github', 'PUT', { token })
    token = ''
  }

  let lastTick = -1
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
</script>

<div class="flex h-full min-h-0 flex-col text-xs">
  <div class="min-h-0 flex-1 overflow-y-auto px-2 py-2">
    <div class="mb-2 text-paper/50">
      {#if loading}
        laster…
      {:else if !isRepo}
        <span class="text-paper/80">ikke et git-repo</span>
      {:else}
        <span class="text-paper/80">{branch || 'HEAD'}</span>
        {#if upstream}<span class="text-paper/40"> · {upstream}</span>{/if}
        {#if ahead}<span class="text-clean"> +{ahead}</span>{/if}
        {#if behind}<span class="text-warn"> −{behind}</span>{/if}
      {/if}
    </div>

    {#if !loading && !isRepo}
      <div class="mb-3 rounded border border-white/10 p-2">
        <p class="mb-2 text-paper/70">Denne workspacen har ikke .git enda. Commit og push trenger et repo.</p>
        <button
          type="button"
          class="rounded border border-clean/40 px-2 py-1 text-clean hover:bg-white/10"
          disabled={!!busy}
          onclick={() => call('/v1/git/init', 'POST')}
        >git init</button>
      </div>
    {/if}

    <div class="mb-3 rounded border border-white/10 p-2">
      <div class="mb-1 text-[0.65rem] uppercase tracking-wide text-paper/40">GitHub</div>
      {#if ghLogin}
        <div class="flex items-center gap-2">
          <span class="text-clean">innlogget som {ghLogin}</span>
          <button type="button" class="ml-auto text-paper/40 hover:text-paper" onclick={() => call('/v1/git/github', 'DELETE')}>logg ut</button>
        </div>
      {:else}
        <p class="mb-1 text-paper/45">
          {ghSet ? 'token satt' + (ghHint ? ' (' + ghHint + ')' : '') + ' — ugyldig eller uten user' : 'lim inn PAT (repo)'}
        </p>
        <form class="flex gap-1" onsubmit={login}>
          <input
            class="min-w-0 flex-1 rounded border border-white/15 bg-ink px-2 py-0.5"
            type="password"
            autocomplete="off"
            bind:value={token}
            placeholder="ghp_…"
          />
          <button type="submit" class="rounded border border-white/15 px-2 py-0.5 hover:bg-white/10">logg inn</button>
        </form>
      {/if}
    </div>

    {#if isRepo}
    <form
      class="mb-3"
      onsubmit={(e) => {
        e.preventDefault()
        call('/v1/git/commit', 'POST', { message: msg, paths: [] })
        msg = ''
      }}
    >
      <textarea
        class="mb-1 h-16 w-full resize-none rounded border border-white/15 bg-ink px-2 py-1"
        bind:value={msg}
        placeholder="commit-melding"
      ></textarea>
      <div class="flex flex-wrap gap-1">
        <button
          type="submit"
          class="rounded border border-white/15 px-2 py-0.5 hover:bg-white/10"
          disabled={!!busy || !staged.length}
          title={staged.length ? 'bare filer merket staged' : 'stage noe først, eller bruk commit alle'}
        >commit staged{staged.length ? ' (' + staged.length + ')' : ''}</button>
        <button
          type="button"
          class="rounded border border-white/15 px-2 py-0.5 hover:bg-white/10"
          disabled={!!busy || !files.length}
          title="git add -A, så commit"
          onclick={() => {
            call('/v1/git/commit', 'POST', { message: msg, all_files: true })
            msg = ''
          }}
        >commit alle{files.length ? ' (' + files.length + ')' : ''}</button>
      </div>
    </form>

    <div class="mb-3">
      <div class="mb-1 text-[0.65rem] uppercase tracking-wide text-paper/40">endringer {files.length ? '(' + files.length + ')' : ''}</div>
      {#if !files.length}
        <p class="text-paper/35">rent tre</p>
      {:else}
        {#each files as f}
          <div class="flex items-center gap-1 py-0.5">
            <span class="w-16 shrink-0 text-paper/40">{xyLabel(f.xy)}</span>
            <button type="button" class="min-w-0 flex-1 truncate text-left hover:text-clean" onclick={() => onopen(f.path)}>{f.path}</button>
            <button
              type="button"
              class="shrink-0 text-paper/40 hover:text-paper"
              onclick={() => call(f.xy[0] !== ' ' && f.xy !== '??' ? '/v1/git/unstage' : '/v1/git/stage', 'POST', { paths: [f.path] })}
            >{f.xy[0] !== ' ' && f.xy !== '??' ? 'unstage' : 'stage'}</button>
          </div>
        {/each}
      {/if}
    </div>

    <div class="mb-3">
      <div class="mb-1 text-[0.65rem] uppercase tracking-wide text-paper/40">push til</div>
      <select
        class="mb-1 w-full rounded border border-white/15 bg-ink px-2 py-0.5"
        bind:value={remote}
        onchange={() => {
          try {
            localStorage.setItem('kalived.ui.git.remote', remote)
          } catch {
            /* ignore */
          }
        }}
      >
        {#each remotes as r}
          <option value={r.name}>{r.name}{r.blocked ? ' (blokkert)' : ''} — {destHint(r)}</option>
        {/each}
      </select>
      {#if selected}
        <p class="mb-0.5 break-all text-paper/85" title={selected.push || selected.fetch}>
          {selected.name} → {destHint(selected)}
        </p>
        <p class="mb-1 break-all font-mono text-[0.65rem] text-paper/45">{selected.push || selected.fetch}</p>
        {#if selected.blocked}
          <p class="mb-1 text-alert">blokkert — origin/wallE pusher ikke herfra</p>
        {:else}
          <p class="mb-1 text-paper/50">
            {branch || 'HEAD'}{selected.github ? (selected.ssh ? ' · GitHub SSH' : ' · GitHub HTTPS') : ''}
          </p>
        {/if}
      {/if}
      <div class="flex gap-1">
        <button
          type="button"
          class="rounded border border-white/15 px-2 py-0.5 hover:bg-white/10"
          disabled={!!busy}
          onclick={() => call('/v1/git/pull', 'POST', { remote, branch })}
        >pull</button>
        <button
          type="button"
          class="rounded border border-white/15 px-2 py-0.5 hover:bg-white/10"
          disabled={!!busy || !!selected?.blocked}
          onclick={() => call('/v1/git/push', 'POST', { remote, branch })}
        >push til {remote}</button>
      </div>
      <form
        class="mt-2 flex flex-col gap-1"
        onsubmit={(e) => {
          e.preventDefault()
          call('/v1/git/remote', 'POST', { name: remoteName.trim(), url: remoteUrl.trim() })
          remoteName = ''
          remoteUrl = ''
        }}
      >
        <div class="text-[0.65rem] uppercase tracking-wide text-paper/40">ny remote</div>
        <input
          class="rounded border border-white/15 bg-ink px-2 py-0.5"
          bind:value={remoteName}
          placeholder="navn (hiroshima)"
          spellcheck="false"
        />
        <input
          class="rounded border border-white/15 bg-ink px-2 py-0.5"
          bind:value={remoteUrl}
          placeholder="git@github.com:org/repo.git"
          spellcheck="false"
        />
        <button type="submit" class="self-start rounded border border-white/15 px-2 py-0.5 hover:bg-white/10" disabled={!!busy || !remoteName.trim() || !remoteUrl.trim()}>legg til</button>
      </form>
    </div>

    <div>
      <div class="mb-1 text-[0.65rem] uppercase tracking-wide text-paper/40">logg</div>
      {#each commits as c}
        <div class="truncate text-paper/60">
          <span class="text-clean/80">{c.sha}</span>
          {c.subject}
        </div>
      {/each}
    </div>
    {/if}
  </div>
  {#if err}
    <div class="border-t border-alert/30 px-2 py-1 text-alert/90">{err}</div>
  {:else if note}
    <div class="border-t border-white/10 px-2 py-1 text-clean/80">{note}</div>
  {:else if busy}
    <div class="border-t border-white/10 px-2 py-1 text-paper/40">{busy}</div>
  {/if}
</div>
