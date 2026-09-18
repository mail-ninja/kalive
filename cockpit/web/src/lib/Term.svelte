<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import { Terminal } from '@xterm/xterm'
  import { FitAddon } from '@xterm/addon-fit'
  import '@xterm/xterm/css/xterm.css'

  let host: HTMLDivElement
  let term: Terminal | null = null
  let fit: FitAddon | null = null
  let sock: WebSocket | null = null
  let alive = true
  let led = $state('off')
  let who = $state('frakoblet')

  function connect() {
    if (sock && sock.readyState === WebSocket.OPEN) return
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    sock = new WebSocket(`${proto}://${location.host}/v1/term`)
    sock.binaryType = 'arraybuffer'
    who = 'kobler cockpit PTY…'
    sock.onopen = () => {
      led = 'on'
      who = 'cockpit PTY (denne uid — sudo-passord her)'
      fit?.fit()
      if (term) {
        sock?.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
      }
    }
    sock.onmessage = (ev) => {
      if (!term) return
      if (typeof ev.data === 'string') term.write(ev.data)
      else term.write(new Uint8Array(ev.data))
    }
    sock.onclose = () => {
      led = 'off'
      sock = null
      who = 'frakoblet'
    }
    sock.onerror = () => {
      who = 'ws-feil — er :8788 oppe?'
    }
  }

  onMount(() => {
    term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: 'ui-monospace, "Cascadia Code", Menlo, Consolas, monospace',
      theme: {
        background: '#020804',
        foreground: '#7CFFB2',
        cursor: '#C8FF6A',
        selectionBackground: '#2dd4bf66',
      },
      scrollback: 4000,
    })
    fit = new FitAddon()
    term.loadAddon(fit)
    term.open(host)
    fit.fit()
    term.onData((d) => {
      if (sock?.readyState === WebSocket.OPEN) sock.send(d)
    })
    const ro = new ResizeObserver(() => {
      fit?.fit()
      if (term && sock?.readyState === WebSocket.OPEN) {
        sock.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }))
      }
    })
    ro.observe(host)
    connect()
    return () => ro.disconnect()
  })

  onDestroy(() => {
    alive = false
    sock?.close()
    term?.dispose()
  })
</script>

<div class="term-wrap">
  <div class="term-bar">
    <span class="led" class:on={led === 'on'}></span>
    <strong>xterm</strong>
    <em>{who}</em>
    <button type="button" onclick={connect}>koble til</button>
  </div>
  <div bind:this={host} class="term-screen"></div>
</div>

<style>
  .term-wrap {
    display: flex;
    height: 100%;
    min-height: 10rem;
    flex-direction: column;
    overflow: hidden;
    border-radius: 0.7rem;
    background: linear-gradient(160deg, #3a342c, #1a1612 45%, #0d0b09);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  }
  .term-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.7rem;
    font-size: 0.75rem;
    color: #c8c2b4;
  }
  .term-bar em {
    font-style: normal;
    opacity: 0.7;
  }
  .term-bar button {
    margin-left: auto;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: transparent;
    color: inherit;
    padding: 0.15rem 0.6rem;
    cursor: pointer;
  }
  .led {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: #3a3f4d;
  }
  .led.on {
    background: #5ee0b5;
    box-shadow: 0 0 8px #5ee0b5;
  }
  .term-screen {
    flex: 1;
    min-height: 0;
    margin: 0 0.45rem 0.5rem;
    overflow: hidden;
    border-radius: 0.3rem;
    background: #020804;
    padding: 4px;
  }
</style>
