<script lang="ts">
  import { onDestroy, onMount } from 'svelte'

  let el: HTMLDivElement
  let editor: { dispose: () => void } | null = null

  onMount(async () => {
    const monaco = await import('monaco-editor')
    editor = monaco.editor.create(el, {
      value: '# untitled\n// Monaco er wired. Theia er IDE-modus senere, ikke nå.\n',
      language: 'markdown',
      theme: 'vs-dark',
      automaticLayout: true,
      minimap: { enabled: false },
      fontSize: 14,
      fontFamily: 'ui-monospace, "Cascadia Code", Menlo, monospace',
    })
  })

  onDestroy(() => editor?.dispose())
</script>

<div bind:this={el} class="h-full min-h-[16rem] w-full overflow-hidden rounded-lg"></div>
