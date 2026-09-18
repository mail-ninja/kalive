<script lang="ts">
  import type { Snippet } from 'svelte'

  let {
    direction = 'horizontal',
    value = $bindable(50),
    a,
    b,
  }: {
    direction?: 'horizontal' | 'vertical'
    value?: number
    a: Snippet
    b: Snippet
  } = $props()

  function down(e: MouseEvent) {
    e.preventDefault()
    const gutter = e.currentTarget as HTMLElement
    const parent = gutter.parentElement
    if (!parent) return
    const rect = parent.getBoundingClientRect()
    const move = (ev: MouseEvent) => {
      const pos = direction === 'horizontal' ? ev.clientX - rect.left : ev.clientY - rect.top
      const size = direction === 'horizontal' ? rect.width : rect.height
      value = Math.min(80, Math.max(18, (pos / size) * 100))
    }
    const up = () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
  }
</script>

<div class="split" class:col={direction === 'vertical'}>
  <div class="pane" style="flex: {value} 1 0">
    {@render a()}
  </div>
  <button
    type="button"
    class="gutter"
    class:col={direction === 'vertical'}
    aria-label="resize"
    onmousedown={down}
  ></button>
  <div class="pane" style="flex: {100 - value} 1 0">
    {@render b()}
  </div>
</div>

<style>
  .split {
    display: flex;
    min-height: 0;
    min-width: 0;
    height: 100%;
    width: 100%;
  }
  .split.col {
    flex-direction: column;
  }
  .pane {
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .gutter {
    flex: 0 0 6px;
    padding: 0;
    border: 0;
    cursor: col-resize;
    background: rgba(244, 239, 228, 0.08);
  }
  .gutter:hover,
  .gutter:focus {
    background: #5ee0b5;
  }
  .gutter.col {
    cursor: row-resize;
    flex-basis: 6px;
  }
</style>
