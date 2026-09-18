<script lang="ts">
  import { onMount } from 'svelte'

  type KeyInfo = { set: boolean; secret: boolean; hint: string | null }
  type Field = { name: string; secret: boolean; label?: string; placeholder?: string }
  type Provider = { id: string; label: string; docs: string; keys: Field[] }

  let path = $state('')
  let mode = $state<string | null>(null)
  let keys = $state<Record<string, KeyInfo>>({})
  let providers = $state<Provider[]>([])
  let drafts = $state<Record<string, string>>({})
  let extraName = $state('')
  let extraVal = $state('')
  let msg = $state('')
  let err = $state('')

  async function load() {
    err = ''
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
