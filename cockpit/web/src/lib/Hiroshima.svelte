<script lang="ts">
  import { onMount } from 'svelte'
  import Split from './Split.svelte'
  import Term from './Term.svelte'

  type Finding = { severity?: string; id?: string; title?: string; detail?: string }
  type Verdict = {
    verdict?: string
    stamp?: string
    exit_code?: number
    findings?: Finding[]
  }

  let doc = $state<Verdict | null>(null)
  let err = $state('')
  let scanning = $state(false)
  let jobNote = $state('')
  let split = $state(42)

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

  async function scan() {
    scanning = true
    err = ''
    jobNote = 'starter…'
    try {
      const r = await fetch('/v1/hiroshima/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true }),
      })
      const j = await r.json()
      if (j.error && !j.job_id) {
        err = j.error
      } else if (j.job_id) {
        jobNote = j.note || 'kjører — får bli ferdig'
        await pollJob(j.job_id)
      }
    } catch (e) {
      err = String(e)
    }
    scanning = false
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
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <button class="rounded-full bg-paper px-3 py-1 text-sm text-ink disabled:opacity-50" disabled={scanning} onclick={scan}>
            {scanning ? 'scanner…' : 'Kjør scan'}
          </button>
          <button class="rounded-full border border-white/15 px-3 py-1 text-sm" onclick={load}>oppdater</button>
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
