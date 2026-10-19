<script lang="ts">
  let {
    path = '',
    url = '',
    rev = 0,
  }: {
    path?: string
    url?: string
    rev?: number
  } = $props()

  function loopback(u: string) {
    return (
      u.startsWith('http://127.0.0.1') ||
      u.startsWith('https://127.0.0.1') ||
      u.startsWith('http://localhost') ||
      u.startsWith('https://localhost')
    )
  }

  let src = $derived.by(() => {
    const u = (url || '').trim()
    if (u && loopback(u)) return u
    if (path && /\.html?$/i.test(path)) {
      return '/v1/workspace/raw?path=' + encodeURIComponent(path) + '&r=' + rev
    }
    if (u) return '/v1/desk/preview?r=' + rev
    return ''
  })

  let label = $derived(loopback(url) ? url : path || '')
</script>

<div class="wrap">
  {#if src}
    <iframe title="preview" class="frame" src={src}></iframe>
  {:else}
    <div class="empty">
      <p>Ingenting å se ennå.</p>
      <p class="hint">Åpne en .html i treet, eller la build skrive en.</p>
    </div>
  {/if}
  {#if label}
    <span class="sr">{label}</span>
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
  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }
</style>
