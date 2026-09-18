<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import 'monaco-editor-css'

  let host: HTMLDivElement
  let editor: { dispose: () => void; layout: () => void } | null = null
  let ro: ResizeObserver | null = null

  onMount(async () => {
    const monaco = await import('monaco-editor')
    editor = monaco.editor.create(host, {
      value: '// cockpit editor — monaco\n',
      language: 'markdown',
      theme: 'vs-dark',
      automaticLayout: false,
      minimap: { enabled: false },
      fontSize: 14,
      fontFamily: 'ui-monospace, "Cascadia Code", Menlo, Consolas, monospace',
      scrollBeyondLastLine: false,
      padding: { top: 8 },
    })
    ro = new ResizeObserver(() => editor?.layout())
    ro.observe(host)
    editor.layout()
  })

  onDestroy(() => {
    ro?.disconnect()
    editor?.dispose()
  })
</script>

<div class="editor-shell">
  <div bind:this={host} class="editor-canvas"></div>
</div>

<style>
  .editor-shell {
    position: relative;
    height: 100%;
    min-height: 12rem;
    width: 100%;
    overflow: hidden;
    border-radius: 0.5rem;
    background: #1e1e1e;
  }
  .editor-canvas {
    position: absolute;
    inset: 0;
  }
</style>
