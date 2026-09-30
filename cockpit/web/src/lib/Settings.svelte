<script lang="ts">
  import { onMount } from 'svelte'

  type KeyInfo = { set: boolean; secret: boolean; hint: string | null }
  type Field = { name: string; secret: boolean; label?: string; placeholder?: string }
  type Provider = { id: string; label: string; docs: string; keys: Field[] }
  type CfgField = {
    name: string
    type: string
    group: string
    label: string
    help?: string
    choices?: string[]
    readonly?: boolean
    danger?: boolean
    min?: number
    max?: number
  }
  type CfgGroup = { id: string; label: string }

  let path = $state('')
  let mode = $state<string | null>(null)
  let keys = $state<Record<string, KeyInfo>>({})
  let providers = $state<Provider[]>([])
  let drafts = $state<Record<string, string>>({})
  let extraName = $state('')
  let extraVal = $state('')
  let msg = $state('')
  let err = $state('')
  let cfgPath = $state('')
  let cfgMode = $state<string | null>(null)
  let cfgValues = $state<Record<string, unknown>>({})
  let cfgSchema = $state<CfgField[]>([])
  let cfgGroups = $state<CfgGroup[]>([])
  let cfgLive = $state<Record<string, { enabled?: string; active?: string }>>({})
  let cfgMsg = $state('')
  let cfgErr = $state('')
  let cfgSaving = $state(false)

  async function loadConfig() {
    cfgErr = ''
    const r = await fetch('/v1/config')
    if (!r.ok) {
      cfgErr = 'kunne ikke lese /v1/config (' + r.status + ')'
      return
    }
    const j = await r.json()
    cfgPath = j.path || ''
    cfgMode = j.mode || null
    cfgValues = { ...(j.values || {}) }
    cfgSchema = j.schema || []
    cfgGroups = j.groups || []
    cfgLive = j.live || {}
  }

  function fieldsIn(group: string): CfgField[] {
    return cfgSchema.filter((f) => f.group === group)
  }

  async function saveConfig() {
    cfgSaving = true
    cfgMsg = 'lagrer…'
    cfgErr = ''
    const body: Record<string, unknown> = {}
    for (const f of cfgSchema) {
      if (f.readonly) continue
      if (f.name in cfgValues) body[f.name] = cfgValues[f.name]
    }
    try {
      const r = await fetch('/v1/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values: body }),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        cfgMsg = ''
        cfgErr = errText(j, r.status)
        return
      }
      cfgValues = { ...(j.values || cfgValues) }
      cfgLive = j.live || cfgLive
      cfgPath = j.path || cfgPath
      cfgMode = j.mode || cfgMode
      const ctl = (j.ctl || []) as { verb?: string; ok?: boolean; hint?: string }[]
      const fail = ctl.filter((c) => c.ok === false)
      cfgMsg =
        'lagret config' +
        (ctl.length ? ' · ' + ctl.map((c) => c.verb + (c.ok ? ' ok' : ' feilet')).join(', ') : '')
      if (fail.length) {
        cfgErr = fail.map((c) => c.hint || c.verb).join(' · ')
      }
    } catch (e) {
      cfgMsg = ''
      cfgErr = String(e)
    } finally {
      cfgSaving = false
    }
  }

  async function load() {
    err = ''
    await loadConfig()
    const r = await fetch('/v1/secrets')
    if (!r.ok) {
      err = 'kunne ikke lese /v1/secrets (' + r.status + ') — restart bash cockpit/scripts/dev.sh'
      return
    }
    const j = await r.json()
    path = j.path
    mode = j.mode
    keys = j.keys || {}
    providers = j.providers || []
    drafts = Object.fromEntries(Object.keys(keys).map((k) => [k, '']))
  }

  function errText(j: unknown, status: number): string {
    if (j && typeof j === 'object' && 'detail' in j) {
      const d = (j as { detail: unknown }).detail
      if (typeof d === 'string') return d
      try {
        return JSON.stringify(d)
      } catch {
        /* ignore */
      }
    }
    return 'lagring feilet (' + status + ')'
  }

  async function save() {
    const body: Record<string, string | null> = {}
    for (const [k, v] of Object.entries(drafts)) {
      if ((v || '').trim() !== '') body[k] = v.trim()
    }
    if (extraName.trim() && extraVal.trim()) body[extraName.trim()] = extraVal.trim()
    if (Object.keys(body).length === 0) {
      err = 'ingenting å lagre — skriv i et felt først (tomt felt betyr uendret)'
      return
    }
    msg = 'lagrer…'
    err = ''
    const r = await fetch('/v1/secrets', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keys: body }),
    })
    const j = await r.json().catch(() => ({}))
    if (!r.ok) {
      msg = ''
      err = errText(j, r.status)
      return
    }
    extraName = ''
    extraVal = ''
    keys = j.keys || keys
    providers = j.providers || providers
    drafts = Object.fromEntries(Object.keys(keys).map((k) => [k, '']))
    path = j.path
    mode = j.mode
    msg = 'lagret ' + Object.keys(body).join(', ') + (mode ? ' · ' + mode : '')
  }

  function leftovers(): string[] {
    const named = new Set(providers.flatMap((p) => p.keys.map((k) => k.name)))
    return Object.keys(keys).filter((k) => !named.has(k))
  }

  onMount(load)
</script>

<section class="mx-auto max-w-2xl space-y-6 p-4">
  <div>
    <h2 class="font-serif text-2xl">Maskin</h2>
    <p class="text-sm text-paper/70">
      Runtime-knapper. Disk: <code class="text-clean">{cfgPath || '~/.config/kalived/config.toml'}</code>
      {#if cfgMode}<span> {cfgMode}</span>{/if}. Watch-timer er valgfri. Sensorer av svekker Hiroshima.
    </p>
  </div>

  {#each cfgGroups as g}
    {@const fields = fieldsIn(g.id)}
    {#if fields.length}
      <article class="rounded-xl border border-white/10 bg-black/25 p-4">
        <h3 class="mb-3 font-serif text-lg">{g.label}</h3>
        {#if g.id === 'hiroshima' && cfgLive.watch_timer}
          <p class="mb-3 text-xs text-paper/45">
            systemd watch: {cfgLive.watch_timer.enabled} / {cfgLive.watch_timer.active}
          </p>
        {/if}
        {#if g.id === 'scan' && cfgLive.scan_timer}
          <p class="mb-3 text-xs text-paper/45">
            systemd scan: {cfgLive.scan_timer.enabled} / {cfgLive.scan_timer.active}
          </p>
        {/if}
        <div class="space-y-3">
          {#each fields as f}
            {#if f.type === 'bool'}
              <label class="flex items-start gap-2 text-sm">
                <input
                  class="mt-1"
                  type="checkbox"
                  disabled={f.readonly}
                  checked={Boolean(cfgValues[f.name])}
                  onchange={(e) => {
                    cfgValues = { ...cfgValues, [f.name]: (e.currentTarget as HTMLInputElement).checked }
                  }}
                />
                <span>
                  <span class={f.danger ? 'text-warn' : ''}>{f.label}</span>
                  {#if f.help}
                    <span class="block text-xs text-paper/45">{f.help}</span>
                  {/if}
                </span>
              </label>
            {:else if f.type === 'enum'}
              <label class="block text-sm">
                <span class="text-paper/70">{f.label}</span>
                <select
                  class="mt-1 w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2"
                  disabled={f.readonly}
                  value={String(cfgValues[f.name] ?? '')}
                  onchange={(e) => {
                    cfgValues = { ...cfgValues, [f.name]: (e.currentTarget as HTMLSelectElement).value }
                  }}
                >
                  {#each f.choices || [] as c}
                    <option value={c}>{c}</option>
                  {/each}
                </select>
                {#if f.help}
                  <span class="block text-xs text-paper/45">{f.help}</span>
                {/if}
              </label>
            {:else if f.type === 'int'}
              <label class="block text-sm">
                <span class="text-paper/70">{f.label}</span>
                <input
                  class="mt-1 w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2"
                  type="number"
                  min={f.min}
                  max={f.max}
                  disabled={f.readonly}
                  value={Number(cfgValues[f.name] ?? 0)}
                  oninput={(e) => {
                    cfgValues = { ...cfgValues, [f.name]: Number((e.currentTarget as HTMLInputElement).value) }
                  }}
                />
              </label>
            {:else}
              <p class="text-sm text-paper/50">
                {f.label}: <code>{String(cfgValues[f.name] ?? '')}</code>
                {#if f.help}
                  <span class="block text-xs text-paper/45">{f.help}</span>
                {/if}
              </p>
            {/if}
          {/each}
        </div>
      </article>
    {/if}
  {/each}

  <button class="rounded-full bg-paper px-4 py-2 text-ink disabled:opacity-50" disabled={cfgSaving} onclick={saveConfig}>
    Lagre maskin
  </button>
  {#if cfgMsg}
    <p class="text-sm text-clean">{cfgMsg}</p>
  {/if}
  {#if cfgErr}
    <p class="text-sm text-alert">{cfgErr}</p>
  {/if}

  <div>
    <h2 class="font-serif text-2xl">Nøkler</h2>
    <p class="text-sm text-paper/70">
      Skriv-bare. Disk: <code class="text-clean">{path || '~/.config/kalived/env'}</code>
      {#if mode}<span> {mode}</span>{/if}. Tomt felt = uendret. Ikke git-add.
    </p>
  </div>

  {#each providers as p}
    <article class="rounded-xl border border-white/10 bg-black/25 p-4">
      <div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 class="font-serif text-lg">{p.label}</h3>
        <a class="text-sm text-clean underline decoration-clean/40" href={p.docs} target="_blank" rel="noreferrer"
          >dokumentasjon</a
        >
      </div>
      <div class="space-y-3">
        {#each p.keys as field}
          {@const info = keys[field.name] || { set: false, secret: field.secret, hint: null }}
          <label class="block text-sm">
            <span class="text-paper/70">{field.label || field.name}</span>
            <code class="ml-2 text-xs text-paper/40">{field.name}</code>
            <span class="ml-2 text-xs text-paper/40">
              {#if info.set}satt {info.hint ?? ''}{:else}ikke satt{/if}
            </span>
            <input
              class="mt-1 w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2"
              type={field.secret ? 'password' : field.name.includes('URL') ? 'url' : 'text'}
              autocomplete="off"
              placeholder={info.set && field.secret ? 'uendret hvis tom' : field.placeholder || 'lim inn'}
              bind:value={drafts[field.name]}
            />
          </label>
        {/each}
      </div>
    </article>
  {/each}

  {#if leftovers().length}
    <article class="rounded-xl border border-white/10 p-4">
      <h3 class="mb-2 font-serif">Andre i fila</h3>
      {#each leftovers() as k}
        {@const info = keys[k]}
        <label class="mb-2 block text-sm">
          <code>{k}</code>
          <span class="ml-2 text-xs text-paper/40">{info?.set ? 'satt ' + (info.hint ?? '') : ''}</span>
          <input
            class="mt-1 w-full rounded-lg border border-white/15 bg-black/40 px-3 py-2"
            type={info?.secret ? 'password' : 'text'}
            bind:value={drafts[k]}
          />
        </label>
      {/each}
    </article>
  {/if}

  <div class="grid grid-cols-2 gap-2">
    <input
      class="rounded-lg border border-white/15 bg-black/40 px-3 py-2 text-sm"
      placeholder="NY_NØKKEL"
      bind:value={extraName}
    />
    <input
      class="rounded-lg border border-white/15 bg-black/40 px-3 py-2 text-sm"
      type="password"
      placeholder="verdi"
      bind:value={extraVal}
    />
  </div>

  <button class="rounded-full bg-paper px-4 py-2 text-ink" onclick={save}>Lagre</button>
  {#if msg}
    <p class="text-sm text-clean">{msg}</p>
  {/if}
  {#if err}
    <p class="text-sm text-alert">{err}</p>
  {/if}
</section>
