import {
  COLS,
  load,
  save,
  addCard,
  moveCard,
  removeCard,
  findCard,
  cardMatches,
  counts,
  exportJson,
  importJson,
} from "./store.mjs";

const THEME_KEY = "kanban-theme";
const EMPTY_TEXT = {
  todo: "Ingen oppgaver her ennå",
  doing: "Ingenting pågår",
  done: "Ingenting ferdig",
};

const storage = window.localStorage;
let state = load(storage);
let selectedId = null;
let query = "";

function persist() {
  save(storage, state);
}

function applyTheme(theme) {
  const t = theme === "light" ? "light" : "dark";
  document.documentElement.dataset.theme = t;
  localStorage.setItem(THEME_KEY, t);
  const btn = document.getElementById("theme-toggle");
  if (btn) btn.textContent = t === "light" ? "Lys" : "Mørk";
}

function initTheme() {
  applyTheme(localStorage.getItem(THEME_KEY) || "dark");
}

function render() {
  const n = counts(state);
  const stats = document.getElementById("stats");
  stats.textContent = `Todo: ${n.todo} · Doing: ${n.doing} · Done: ${n.done}`;

  for (const col of COLS) {
    const host = document.querySelector(`[data-col="${col}"] .cards`);
    host.replaceChildren();
    const visible = state[col].filter((c) => cardMatches(c, query));
    if (visible.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = query.trim()
        ? "Ingen treff i denne kolonnen"
        : EMPTY_TEXT[col];
      host.appendChild(empty);
    }
    for (const card of visible) {
      host.appendChild(makeCard(card, col));
    }
  }
}

function makeCard(card, col) {
  const el = document.createElement("article");
  el.className = "card";
  el.dataset.id = card.id;
  el.draggable = true;
  if (selectedId === card.id) el.classList.add("selected");

  el.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    selectedId = card.id;
    render();
  });

  el.addEventListener("dragstart", (e) => {
    selectedId = card.id;
    e.dataTransfer.setData("text/plain", JSON.stringify({ id: card.id, from: col }));
    e.dataTransfer.effectAllowed = "move";
  });

  const p = document.createElement("p");
  p.textContent = card.text;
  el.appendChild(p);

  const meta = document.createElement("div");
  meta.className = "meta";

  const prio = document.createElement("span");
  const prioClass = card.priority === "høy" ? "hoy" : card.priority;
  prio.className = `prio prio-${prioClass}`;
  prio.textContent = card.priority;
  meta.appendChild(prio);

  if (card.due) {
    const due = document.createElement("span");
    due.className = "due";
    due.textContent = `forfall ${card.due}`;
    meta.appendChild(due);
  }

  for (const t of card.tags || []) {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = t;
    meta.appendChild(tag);
  }
  el.appendChild(meta);

  const actions = document.createElement("div");
  actions.className = "card-actions";

  const i = COLS.indexOf(col);
  if (i > 0) {
    const left = document.createElement("button");
    left.type = "button";
    left.textContent = "←";
    left.addEventListener("click", () => move(card.id, col, COLS[i - 1]));
    actions.appendChild(left);
  }
  if (i < COLS.length - 1) {
    const right = document.createElement("button");
    right.type = "button";
    right.textContent = "→";
    right.addEventListener("click", () => move(card.id, col, COLS[i + 1]));
    actions.appendChild(right);
  }

  const del = document.createElement("button");
  del.type = "button";
  del.className = "del";
  del.textContent = "Slett";
  del.addEventListener("click", () => remove(card.id, col));
  actions.appendChild(del);

  el.appendChild(actions);
  return el;
}

function add(text, extras) {
  state = addCard(state, text, extras);
  persist();
  render();
}

function move(id, from, to) {
  state = moveCard(state, id, from, to);
  selectedId = id;
  persist();
  render();
}

function remove(id, col) {
  if (!confirm("Slette dette kortet?")) return;
  state = removeCard(state, id, col);
  if (selectedId === id) selectedId = null;
  persist();
  render();
}

function parseTags(raw) {
  return String(raw || "")
    .split(/[\s,]+/)
    .map((t) => t.trim())
    .filter(Boolean);
}

function typingTarget(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

document.getElementById("add-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("new-card");
  add(input.value, {
    priority: document.getElementById("new-priority").value,
    due: document.getElementById("new-due").value,
    tags: parseTags(document.getElementById("new-tags").value),
  });
  input.value = "";
  document.getElementById("new-tags").value = "";
  document.getElementById("new-due").value = "";
  input.focus();
});

document.getElementById("search").addEventListener("input", (e) => {
  query = e.target.value;
  render();
});

document.getElementById("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(next);
});

document.getElementById("export-btn").addEventListener("click", () => {
  const blob = new Blob([exportJson(state)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "kanban.json";
  a.click();
  URL.revokeObjectURL(a.href);
});

document.getElementById("import-btn").addEventListener("click", () => {
  document.getElementById("import-file").click();
});

document.getElementById("import-file").addEventListener("change", (e) => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    state = importJson(String(reader.result || ""));
    selectedId = null;
    persist();
    render();
  };
  reader.readAsText(file);
});

for (const col of COLS) {
  const section = document.querySelector(`[data-col="${col}"]`);
  section.addEventListener("dragover", (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    section.classList.add("drag-over");
  });
  section.addEventListener("dragleave", () => {
    section.classList.remove("drag-over");
  });
  section.addEventListener("drop", (e) => {
    e.preventDefault();
    section.classList.remove("drag-over");
    let payload;
    try {
      payload = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
    } catch {
      return;
    }
    if (!payload.id || !payload.from) return;
    if (payload.from === col) return;
    move(payload.id, payload.from, col);
  });
}

document.addEventListener("keydown", (e) => {
  if (typingTarget(e.target)) return;
  if (e.key === "n" || e.key === "N") {
    e.preventDefault();
    document.getElementById("new-card").focus();
    return;
  }
  const map = { 1: "todo", 2: "doing", 3: "done" };
  if (map[e.key] && selectedId) {
    const found = findCard(state, selectedId);
    if (!found) return;
    e.preventDefault();
    move(selectedId, found.col, map[e.key]);
  }
});

initTheme();
render();
