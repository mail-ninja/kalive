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
  let box: HTMLDivElement | undefined = $state()
  let full = $state(false)

  function onfs() {
    full = !!box && document.fullscreenElement === box
  }

  async function toggleFull() {
    if (!box) return
    try {
      if (document.fullscreenElement === box) await document.exitFullscreen()
      else await box.requestFullscreen()
    } catch {
      /* browser blocked or no gesture */
    }
  }

  $effect(() => {
    document.addEventListener('fullscreenchange', onfs)
    return () => document.removeEventListener('fullscreenchange', onfs)
  })

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

<div class="wrap" bind:this={box}>
  {#if ready}
    {#key ready + ':' + rev}
      <iframe title="preview" class="frame" src={ready} allowfullscreen></iframe>
    {/key}
    <button type="button" class="fs" onclick={toggleFull} title={full ? 'Esc lukker' : 'Fullskjerm'}>
      {full ? 'lukk' : 'fullskjerm'}
    </button>
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
  .fs {
    position: absolute;
    top: 0.4rem;
    right: 0.4rem;
    z-index: 2;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.18);
    background: rgba(13, 17, 23, 0.72);
    color: rgba(244, 239, 228, 0.9);
    font-size: 0.7rem;
    letter-spacing: 0.02em;
    padding: 0.15rem 0.55rem;
    cursor: pointer;
  }
  .fs:hover {
    background: rgba(13, 17, 23, 0.9);
  }
  .wrap:fullscreen {
    background: #010409;
    border-radius: 0;
  }
</style>
