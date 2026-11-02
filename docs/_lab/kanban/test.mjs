import {
  KEY,
  emptyState,
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
  normalizeState,
} from "./store.mjs";

function mem() {
  const m = new Map();
  return {
    getItem(k) {
      return m.has(k) ? m.get(k) : null;
    },
    setItem(k, v) {
      m.set(k, String(v));
    },
    removeItem(k) {
      m.delete(k);
    },
  };
}

let failed = 0;
function assert(cond, msg) {
  if (!cond) {
    failed += 1;
    console.error("FAIL:", msg);
  } else {
    console.log("ok:", msg);
  }
}

const storage = mem();
assert(JSON.stringify(load(storage)) === JSON.stringify(emptyState()), "load empty");

let state = addCard(emptyState(), "første", {
  id: "c1",
  priority: "høy",
  due: "2026-04-01",
  tags: ["lab", "ui"],
});
assert(state.todo.length === 1 && state.todo[0].text === "første", "addCard");
assert(state.todo[0].priority === "høy", "priority");
assert(state.todo[0].due === "2026-04-01", "due");
assert(state.todo[0].tags.join(",") === "lab,ui", "tags");

save(storage, state);
assert(storage.getItem(KEY), "save writes key");

const reloaded = load(storage);
assert(reloaded.todo[0].id === "c1", "load after save");
assert(reloaded.todo[0].priority === "høy", "load keeps priority");
assert(reloaded.todo[0].due === "2026-04-01", "load keeps due");
assert(JSON.stringify(reloaded.todo[0].tags) === JSON.stringify(["lab", "ui"]), "load keeps tags");

state = moveCard(reloaded, "c1", "todo", "doing");
assert(state.todo.length === 0 && state.doing.length === 1, "moveCard");
save(storage, state);
assert(load(storage).doing[0].id === "c1", "save after move");

const found = findCard(state, "c1");
assert(found && found.col === "doing", "findCard");

assert(cardMatches(found.card, "første"), "search text");
assert(cardMatches(found.card, "lab"), "search tag");
assert(!cardMatches(found.card, "xyz"), "search miss");

const c = counts(state);
assert(c.todo === 0 && c.doing === 1 && c.done === 0, "counts");

const json = exportJson(state);
const imported = importJson(json);
assert(imported.doing[0].id === "c1", "export/import roundtrip");

assert(importJson("not-json").todo.length === 0, "import invalid");
assert(normalizeState({ todo: [{ id: "x", text: "t" }] }).todo[0].priority === "mid", "default priority");

state = removeCard(state, "c1", "doing");
save(storage, state);
assert(load(storage).doing.length === 0, "save after remove");

if (failed) {
  console.error(failed, "failed");
  process.exit(1);
}
console.log("all tests passed");
