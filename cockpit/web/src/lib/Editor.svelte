<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import 'monaco-editor-css'
  import { getCanvas, setCanvas, subscribeCanvas, type Canvas } from './desk'

  let { diskPath = '' }: { diskPath?: string } = $props()

  let host: HTMLDivElement
  let editor: {
    dispose: () => void
    layout: () => void
    getValue: () => string
    setValue: (v: string) => void
    getModel: () => unknown
    onDidChangeModelContent: (cb: () => void) => void
  } | null = null
  let monacoMod: typeof import('monaco-editor') | null = null
  let ro: ResizeObserver | null = null
  let unsub: (() => void) | null = null
  let skip = false
  let canvas = $state<Canvas>(getCanvas())

  export function getValue() {
    return editor?.getValue() ?? canvas.text
  }

  async function loadDisk(p: string) {
    if (!p) return
    const r = await fetch('/v1/workspace/file?path=' + encodeURIComponent(p))
    const j = await r.json()
    if (!r.ok || j.error || j.dir) return
    skip = true
    setCanvas({
      path: j.path,
      language: j.language || 'plaintext',
      text: j.text || '',
      mode: 'monaco',
    })
    if (editor && j.text != null) editor.setValue(j.text)
    skip = false
  }

  let loaded = ''
  $effect(() => {
    const p = diskPath
    if (p && p !== loaded) {
      loaded = p
      loadDisk(p)
    }
  })

  onMount(async () => {
    const monaco = await import('monaco-editor')
    monacoMod = monaco
    editor = monaco.editor.create(host, {
      value: canvas.text,
      language: canvas.language,
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
    editor.onDidChangeModelContent?.(() => {
      if (skip) return
      const v = editor?.getValue()
      if (typeof v === 'string') setCanvas({ text: v, mode: 'monaco' })
    })
    unsub = subscribeCanvas((c) => {
      canvas = c
      if (!editor || c.mode !== 'monaco') return
      skip = true
      const cur = editor.getValue()
      if (c.text !== cur) editor.setValue(c.text)
      const model = editor.getModel()
      if (model && monacoMod) {
        monacoMod.editor.setModelLanguage(model as never, c.language || 'markdown')
      }
      skip = false
    })
  })

  onDestroy(() => {
    unsub?.()
    ro?.disconnect()
    editor?.dispose()
  })
</script>

<div class="wrap">
  <div class="editor-shell" class:off={canvas.mode === 'iframe'}>
    <div bind:this={host} class="editor-canvas"></div>
  </div>
  <div class="editor-shell" class:off={canvas.mode !== 'iframe'}>
    {#if canvas.preview.startsWith('http://127.0.0.1') || canvas.preview.startsWith('https://127.0.0.1') || canvas.preview.startsWith('http://localhost')}
      <iframe title="preview" class="preview" src={canvas.preview}></iframe>
    {:else}
      <iframe
        title="preview"
        class="preview"
        src={diskPath && (diskPath.endsWith('.html') || diskPath.endsWith('.htm'))
          ? '/v1/workspace/raw?path=' + encodeURIComponent(diskPath) + '&r=' + (canvas.rev ?? 0)
          : '/v1/desk/preview?r=' + (canvas.rev ?? 0)}
      ></iframe>
    {/if}
  </div>
</div>

<style>
  .wrap {
    position: relative;
    height: 100%;
    min-height: 12rem;
    width: 100%;
  }
  .editor-shell {
    position: relative;
    height: 100%;
    min-height: 12rem;
    width: 100%;
    overflow: hidden;
    border-radius: 0.5rem;
    background: #1e1e1e;
  }
  .off {
    display: none;
  }
  .editor-canvas,
  .preview {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    border: 0;
    background: #111;
  }
</style>
