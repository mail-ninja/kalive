export type Hist = {
  role: 'you' | 'bot' | 'sys' | 'tool'
  text: string
  name?: string
  diff?: string
  path?: string
}

/** Survives Vite HMR of App.svelte (root remount wipes $state). */
let items: Hist[] = []

export function loadHist(): Hist[] {
  return items
}

export function persistHist(h: Hist[]) {
  items = h
}
