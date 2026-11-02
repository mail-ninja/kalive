export const KEY = "kanban-v1";
export const COLS = ["todo", "doing", "done"];
export const PRIORITIES = ["lav", "mid", "høy"];

export function emptyState() {
  return { todo: [], doing: [], done: [] };
}

export function normalizeCard(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = raw.id != null ? String(raw.id) : "";
  if (!id) return null;
  const priority = PRIORITIES.includes(raw.priority) ? raw.priority : "mid";
  let tags = [];
  if (Array.isArray(raw.tags)) {
    tags = raw.tags.map((t) => String(t).trim()).filter(Boolean);
  } else if (typeof raw.tags === "string") {
    tags = raw.tags.split(/[\s,]+/).map((t) => t.trim()).filter(Boolean);
  }
  return {
    id,
    text: raw.text != null ? String(raw.text) : "",
    priority,
    due: raw.due != null ? String(raw.due) : "",
    tags,
  };
}

export function normalizeState(data) {
  const out = emptyState();
  if (!data || typeof data !== "object") return out;
  for (const col of COLS) {
    const arr = Array.isArray(data[col]) ? data[col] : [];
    out[col] = arr.map(normalizeCard).filter(Boolean);
  }
  return out;
}

export function load(storage) {
  try {
    const raw = storage.getItem(KEY);
    if (!raw) return emptyState();
    return normalizeState(JSON.parse(raw));
  } catch {
    return emptyState();
  }
}

export function save(storage, state) {
  storage.setItem(KEY, JSON.stringify(normalizeState(state)));
}

export function createCard(text, extras = {}) {
  const id =
    extras.id ||
    (typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : String(Date.now()) + Math.random());
  return normalizeCard({
    id,
    text: String(text || "").trim(),
    priority: extras.priority,
    due: extras.due,
    tags: extras.tags,
  });
}

export function addCard(state, text, extras = {}) {
  const card = createCard(text, extras);
  if (!card || !card.text) return state;
  const next = normalizeState(state);
  next.todo.push(card);
  return next;
}

export function moveCard(state, id, from, to) {
  const next = normalizeState(state);
  if (!COLS.includes(from) || !COLS.includes(to)) return next;
  const i = next[from].findIndex((c) => c.id === id);
  if (i < 0) return next;
  const [card] = next[from].splice(i, 1);
  next[to].push(card);
  return next;
}

export function removeCard(state, id, col) {
  const next = normalizeState(state);
  if (!COLS.includes(col)) return next;
  next[col] = next[col].filter((c) => c.id !== id);
  return next;
}

export function findCard(state, id) {
  for (const col of COLS) {
    const card = state[col].find((c) => c.id === id);
    if (card) return { card, col };
  }
  return null;
}

export function cardMatches(card, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return true;
  const hay = [card.text, card.priority, card.due, ...(card.tags || [])]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

export function counts(state) {
  return {
    todo: state.todo.length,
    doing: state.doing.length,
    done: state.done.length,
  };
}

export function exportJson(state) {
  return JSON.stringify(normalizeState(state), null, 2);
}

export function importJson(raw) {
  if (typeof raw !== "string") return emptyState();
  try {
    return normalizeState(JSON.parse(raw));
  } catch {
    return emptyState();
  }
}
