<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import 'monaco-editor-css'
  import { getCanvas, setCanvas, subscribeCanvas, type Canvas } from './desk'

  let {
    diskPath = '',
    fileRev = 0,
    revealLine = 0,
    ondirty,
  }: {
    diskPath?: string
    fileRev?: number
    revealLine?: number
    ondirty?: (path: string) => void
  } = $props()

  let host: HTMLDivElement
  let editor: {
    dispose: () => void
    layout: () => void
    getValue: () => string
    setValue: (v: string) => void
    getModel: () => unknown
    onDidChangeModelContent: (cb: () => void) => void
    revealLineInCenter?: (n: number) => void
    setPosition?: (p: { lineNumber: number; column: number }) => void
    focus?: () => void
  } | null = null
  let pendingLine = 0

  function goLine(n: number) {
    if (!editor || n < 1) return
    editor.revealLineInCenter?.(n)
    editor.setPosition?.({ lineNumber: n, column: 1 })
    editor.focus?.()
  }
  let monacoMod: typeof import('monaco-editor') | null = null
  let ro: ResizeObserver | null = null
  let unsub: (() => void) | null = null
  let skip = false
  let canvas = $state<Canvas>(getCanvas())

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
    if (pendingLine > 0) goLine(pendingLine)
  }

  let loaded = ''
  let loadedRev = -1
  $effect(() => {
    const p = diskPath
    const r = fileRev
    const ln = revealLine
    pendingLine = ln
    if (p && (p !== loaded || r !== loadedRev)) {
      loaded = p
      loadedRev = r
      void loadDisk(p)
    } else if (ln > 0) {
      goLine(ln)
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
    if (pendingLine > 0) goLine(pendingLine)
    editor.onDidChangeModelContent?.(() => {
      if (skip) return
      const v = editor?.getValue()
      if (typeof v === 'string') setCanvas({ text: v, mode: 'monaco' })
      if (diskPath) ondirty?.(diskPath)
    })
    unsub = subscribeCanvas((c) => {
      canvas = c
      if (!editor) return
      if (diskPath && c.path && c.path !== diskPath) return
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
  <div bind:this={host} class="editor-canvas"></div>
</div>

<style>
  .wrap {
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
    width: 100%;
    height: 100%;
  }
</style>
