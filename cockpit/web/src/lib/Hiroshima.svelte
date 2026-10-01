<script lang="ts">
  import { onMount } from 'svelte'
  import Split from './Split.svelte'
  import Term from './Term.svelte'

  type Finding = { severity?: string; id?: string; title?: string; detail?: string }
  type RingItem = {
    kind?: string
    sil?: string
    exe?: string | null
    dst_family?: string | null
    port?: number | null
    seen?: boolean
    severity?: string
  }
  type Protocol = {
    class?: string
    src?: string
    playbook?: string
    ours?: number
    dual?: number
    sensor_gaps?: string[]
    env?: { class?: string; ssid?: string | null; iface?: string | null }
    ring?: RingItem[]
    mercury?: { family?: string; why?: string; playbook?: string; src?: string } | null
    rollback?: boolean
    isolatable?: boolean
    watch_unknown?: number
    watch?: {
      ts?: string
      class?: string
      n?: number
      unique?: number
      unknown?: number
      unmapped?: number
      audit?: string
      suspect?: string[]
      iface?: string | null
      flows?: { exe?: string | null; dst_family?: string | null; n?: number }[]
    } | null
  }
  type Verdict = {
    verdict?: string
    stamp?: string
    exit_code?: number
    findings?: Finding[]
    protocol?: Protocol
  }

  let doc = $state<Verdict | null>(null)
  let err = $state('')
  let scanning = $state(false)
  let jobNote = $state('')
  let split = $state(42)
  let envClass = $state('tether')
  let pending = $state('')

  async function load() {
    err = ''
    try {
      const r = await fetch('/v1/hiroshima/verdict')
      const j = await r.json()
      if (!r.ok) {
        err = j.detail || j.error || r.statusText
        doc = null
        return
      }
      doc = j
      const c = j?.protocol?.env?.class
      if (c) envClass = c
    } catch (e) {
      err = String(e)
    }
  }

  async function pollJob(id: string) {
    const t0 = Date.now()
    while (Date.now() - t0 < 16 * 60 * 1000) {
      const r = await fetch('/v1/hiroshima/jobs/' + encodeURIComponent(id))
      const j = await r.json()
      jobNote = `${j.status} ${j.elapsed_s ?? 0}s`
      if (j.hint) err = j.hint
      if (j.error) err = j.error
      if (j.status && j.status !== 'running') {
        jobNote = j.status === 'done' ? 'ferdig — stoppet' : String(j.status)
        await load()
        return
      }
      await new Promise((res) => setTimeout(res, 2000))
    }
    err = 'poll timeout — jobben kan fortsatt kjøre, sjekk /v1/hiroshima/jobs'
  }

  async function startRun(name: string, extra: Record<string, unknown> = {}) {
    scanning = true
    err = ''
    jobNote = 'starter ' + name
    pending = ''
    try {
      const r = await fetch('/v1/hiroshima/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, confirm: true, ...extra }),
      })
      const j = await r.json()
      if (j.error && !j.job_id) {
        err = j.error
      } else if (j.job_id) {
        jobNote = j.note || name + ' kjører'
        await pollJob(j.job_id)
      }
    } catch (e) {
      err = String(e)
    }
    scanning = false
  }

  async function scan() {
    await startRun('scan')
  }

  async function retag() {
    err = ''
    try {
      const r = await fetch('/v1/hiroshima/env', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ class: envClass }),
      })
      const j = await r.json()
      if (!r.ok) {
        err = j.detail || j.error || r.statusText
        return
      }
      jobNote = 'retag ' + (j.env?.ssid || '') + ' → ' + (j.env?.class || envClass)
      await load()
    } catch (e) {
      err = String(e)
    }
  }

  function confirmRun(name: string, extra: Record<string, unknown> = {}) {
    if (pending !== name) {
      pending = name
      jobNote = 'Confirm ' + name + ' — trykk igjen'
      return
    }
    startRun(name, extra)
  }

  onMount(() => {
    load()
    fetch('/v1/hiroshima/jobs')
      .then((r) => r.json())
      .then((j) => {
        const run = (j.jobs || []).find((x: { status: string }) => x.status === 'running')
        if (run?.job_id) {
          scanning = true
          jobNote = 'gjenopptar jobb'
          pollJob(run.job_id).finally(() => {
            scanning = false
          })
        }
      })
      .catch(() => {})
  })

  const word = $derived(doc?.verdict || '—')
  const proto = $derived(doc?.protocol)
</script>

<div class="flex h-full min-h-0 flex-col bg-ink">
  <Split direction="vertical" bind:value={split}>
    {#snippet a()}
      <section class="flex h-full min-h-0 flex-col overflow-hidden p-4">
        <p class="kicker">siste scan · cockpit :8788</p>
        <h1 class="verdict" class:CLEAN={word === 'CLEAN'} class:WARN={word === 'WARN'} class:ALERT={word === 'ALERT'} class:ERROR={word === 'ERROR'}>
          {word}
        </h1>
        <p class="mb-3 text-xs text-paper/50">
          {doc?.stamp || 'ingen snapshot'}{#if doc?.exit_code != null}
            · exit {doc.exit_code}{/if}
        </p>
        {#if proto}
          <p class="mb-3 text-xs text-paper/70">
            port {proto.class || '—'}{proto.env?.class ? ` · ${proto.env.class}` : ''}{proto.env?.ssid ? ` · ${proto.env.ssid}` : ''} · src={proto.src || '—'}{proto.playbook ? ` · ${proto.playbook}` : ''}
          </p>
          {#if proto.sensor_gaps?.length}
            <p class="mb-3 text-xs text-warn">{proto.sensor_gaps.join(' · ')}</p>
          {/if}
          {#if proto.ring?.length}
            <p class="mb-3 text-xs text-paper/55">
              ring {proto.ring.length} · {proto.ring
                .map((r) => (r.exe && r.dst_family ? `${r.exe}→${r.dst_family}` : r.sil || r.kind || ''))
                .filter(Boolean)
                .slice(0, 8)
                .join(' · ')}
            </p>
          {/if}
          {#if proto.mercury}
            <p class="mb-3 text-xs text-paper/70">
              mercury {proto.mercury.family || '—'}{proto.mercury.why ? ` · ${proto.mercury.why}` : ''} · src={proto.mercury.src || '—'}
            </p>
          {/if}
          {#if proto.watch}
            <p class="mb-3 text-xs text-paper/55">
              watch {proto.watch.n ?? 0} · unknown {proto.watch.unknown ?? 0} · unmapped {proto.watch.unmapped ?? 0}{proto.watch.class ? ` · ${proto.watch.class}` : ''}{proto.watch.audit ? ` · audit=${proto.watch.audit}` : ''}{proto.watch.ts ? ` · ${proto.watch.ts}` : ''}
            </p>
            {#if proto.watch.unknown && !proto.isolatable}
              <p class="mb-3 text-xs text-warn">watch unknown — kjør scan for isolate (snapshot eier dest)</p>
            {/if}
          {/if}
        {/if}
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <button class="rounded-full bg-paper px-3 py-1 text-sm text-ink disabled:opacity-50" disabled={scanning} onclick={scan}>
            {scanning ? 'scanner…' : 'Kjør scan'}
          </button>
          <button class="rounded-full border border-white/15 px-3 py-1 text-sm" onclick={load}>oppdater</button>
          {#if proto?.env?.ssid}
            <label class="flex items-center gap-1 text-xs text-paper/60">
              env
              <select class="rounded-full border border-white/15 bg-ink px-2 py-1 text-paper" bind:value={envClass}>
                <option value="home">home</option>
                <option value="travel">travel</option>
                <option value="tether">tether</option>
              </select>
            </label>
            <button class="rounded-full border border-white/15 px-3 py-1 text-sm" disabled={scanning} onclick={retag}>
              retag
            </button>
          {/if}
          {#if proto?.playbook === 'aide-init'}
            <button
              class="rounded-full border border-warn/50 px-3 py-1 text-sm text-warn disabled:opacity-50"
              disabled={scanning}
              onclick={() => confirmRun('aide-init')}
            >
              {pending === 'aide-init' ? 'Confirm aide-init' : 'aide-init'}
            </button>
            <span class="text-xs text-paper/55">fryser kalived-filer, ikke Proton</span>
          {/if}
          {#if proto?.sensor_gaps?.some((g) => g.includes('ROOT-RKH') || g.includes('rkhunter') || g.includes('chkrootkit'))}
            <button
              class="rounded-full border border-warn/50 px-3 py-1 text-sm text-warn disabled:opacity-50"
              disabled={scanning}
              onclick={() => confirmRun('rkhunter-setup')}
            >
              {pending === 'rkhunter-setup' ? 'Confirm rkhunter-setup' : 'rkhunter-setup'}
            </button>
          {/if}
          {#if proto?.isolatable}
            <button
              class="rounded-full border border-alert/50 px-3 py-1 text-sm text-alert disabled:opacity-50"
              disabled={scanning}
              onclick={() => confirmRun('isolate-dst', { family: 'unknown' })}
            >
              {pending === 'isolate-dst' ? 'Confirm isolate unknown' : 'isolate unknown'}
            </button>
          {/if}
          {#if proto?.rollback}
            <button
              class="rounded-full border border-white/15 px-3 py-1 text-sm disabled:opacity-50"
              disabled={scanning}
              onclick={() => confirmRun('isolate-undo')}
            >
              {pending === 'isolate-undo' ? 'Confirm undo isolate' : 'undo isolate'}
            </button>
          {/if}
          <button
            class="rounded-full border border-white/15 px-3 py-1 text-sm disabled:opacity-50"
            disabled={scanning}
            onclick={() => confirmRun('watch')}
          >
            {pending === 'watch' ? 'Confirm watch' : 'watch'}
          </button>
          <button
            class="rounded-full border border-white/15 px-3 py-1 text-sm disabled:opacity-50"
            disabled={scanning}
            onclick={() => confirmRun('uplink-burst')}
          >
            {pending === 'uplink-burst' ? 'Confirm uplink 30s' : 'uplink 30s'}
          </button>
          <button
            class="rounded-full border border-white/15 px-3 py-1 text-sm disabled:opacity-50"
            disabled={scanning}
            onclick={() => confirmRun('falco-burst')}
          >
            {pending === 'falco-burst' ? 'Confirm falco 8s' : 'falco 8s'}
          </button>
          {#if jobNote}
            <span class="text-xs text-clean">{jobNote}</span>
          {/if}
          {#if err}
            <span class="text-xs text-alert">{err}</span>
          {/if}
        </div>
        <div class="min-h-0 flex-1 space-y-2 overflow-y-scroll pr-1">
          {#each doc?.findings || [] as f}
            <article class={"rounded-lg border border-white/10 p-2 text-sm sev-" + (f.severity || 'INFO')}>
              <div class="text-[0.7rem] tracking-wide text-paper/45">{f.severity} · {f.id}</div>
              <div>{f.title}</div>
            </article>
          {/each}
        </div>
      </section>
    {/snippet}
    {#snippet b()}
      <div class="h-full min-h-0 p-2">
        <Term />
      </div>
    {/snippet}
  </Split>
</div>

<style>
  .kicker {
    margin: 0;
    font-size: 0.72rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: rgba(244, 239, 228, 0.45);
  }
  .verdict {
    font-family: var(--font-serif, Palatino, Georgia, serif);
    font-size: clamp(2.4rem, 8vw, 5.5rem);
    line-height: 0.9;
    margin: 0.15rem 0 0.35rem;
  }
  .verdict.CLEAN {
    color: #5ee0b5;
    text-shadow: 0 0 36px rgba(94, 224, 181, 0.35);
  }
  .verdict.WARN {
    color: #e8a85c;
  }
  .verdict.ALERT {
    color: #ff5d73;
    text-shadow: 0 0 40px rgba(255, 93, 115, 0.35);
  }
  .verdict.ERROR {
    color: #b9a7ff;
  }
  :global(.sev-ALERT) {
    border-left: 3px solid #ff5d73;
  }
  :global(.sev-WARN) {
    border-left: 3px solid #e8a85c;
  }
  :global(.sev-ERROR) {
    border-left: 3px solid #b9a7ff;
  }
  :global(.sev-INFO) {
    border-left: 3px solid #7eb6ff;
  }
</style>
