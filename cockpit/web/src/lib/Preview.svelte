<script lang="ts">
  import { isLoopbackUrl } from './desk'

  let {
    path = '',
    url = '',
    rev = 0,
  }: {
    path?: string
    url?: string
    rev?: number
  } = $props()

  let ready = $state('')
  let wait = $state('')
  let err = $state('')

  function fileSrc(p: string, r: number) {
    if (!p) return ''
    if (/\.html?$/i.test(p)) {
      return '/v1/workspace/raw?path=' + encodeURIComponent(p) + '&r=' + r
    }
    return ''
  }

  let target = $derived.by(() => {
    const u = (url || '').trim()
    if (u && isLoopbackUrl(u)) return u
    const f = fileSrc(path, rev)
    if (f) return f
    if (u && !u.startsWith('http')) return '/v1/desk/preview?r=' + rev
    return ''
  })

  let loop = $derived(isLoopbackUrl(url))

  $effect(() => {
    const t = target
    const r = rev
    err = ''
    ready = ''
    wait = ''
    if (!t) return
    if (!loop) {
      ready = t
      return
    }
    let stop = false
    wait = 'venter på ' + t
    const started = Date.now()
    async function tick() {
      while (!stop) {
        try {
          const res = await fetch('/v1/preview/probe?url=' + encodeURIComponent(t))
          const j = await res.json()
          if (stop) return
          if (j.ok) {
            wait = ''
            ready = t
            return
          }
          wait = (j.error || 'nede') + ' · ' + t
        } catch {
          if (stop) return
          wait = 'probe feilet · ' + t
        }
        if (Date.now() - started > 20000) {
          err = 'ingen svar på ' + t
          wait = ''
          return
        }
        await new Promise((ok) => setTimeout(ok, 400))
      }
    }
    tick()
    return () => {
      stop = true
    }
  })
</script>

<div class="wrap">
  {#if ready}
    {#key ready + ':' + rev}
      <iframe title="preview" class="frame" src={ready}></iframe>
    {/key}
  {:else if wait}
    <div class="empty">
      <p>{wait}</p>
      <p class="hint">Loopback-preview venter til porten svarer.</p>
    </div>
  {:else if err}
    <div class="empty">
      <p>{err}</p>
      <p class="hint">Start tjeneren på 127.0.0.1, eller vis en .html i treet.</p>
    </div>
  {:else}
    <div class="empty">
      <p>Ingenting å se ennå.</p>
      <p class="hint">Åpne en .html, lim en loopback-URL, eller la build kjøre preview_serve.</p>
    </div>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
    height: 100%;
    min-height: 8rem;
    width: 100%;
    background: #111;
    border-radius: 0.5rem;
    overflow: hidden;
  }
  .frame {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: 0;
    background: #111;
  }
  .empty {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
    color: rgba(244, 239, 228, 0.55);
    font-size: 0.85rem;
    padding: 1rem;
    text-align: center;
  }
  .hint {
    color: rgba(244, 239, 228, 0.35);
    font-size: 0.75rem;
  }
</style>
