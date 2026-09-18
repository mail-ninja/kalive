(() => {
  const $ = (id) => document.getElementById(id);
  const tokenKey = "kalived_token";
  const ENUMS = {
    aide_init_policy: ["clean_only", "allow_known_warn", "always_prompt"],
    scan_sudo_mode: ["prompt", "helper", "never"],
  };
  const BOOLS = new Set([
    "docker_stop_idle", "timer_enabled", "ai_enabled", "ai_after_scan",
    "apparmor_enforce_selected", "verbose", "notify_on_alert", "skip_hunt",
    "skip_rootkit", "defs_auto_update", "nmap_localhost", "helper_stale_check",
    "aide_watch_helper", "proc_inventory", "proc_hidden_check", "proc_ioc_check",
    "pcap_localhost", "nmap_svc_probe", "ufw_digest", "web_terminal",
  ]);
  const NUMS = new Set(["listen_port", "pcap_duration_s", "pcap_max_packets"]);

  function token() {
    return localStorage.getItem(tokenKey) || $("token").value.trim();
  }
  function headers() {
    const t = token();
    return t ? { Authorization: "Bearer " + t, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
  }
  async function api(path, opt) {
    const r = await fetch(path, Object.assign({ headers: headers() }, opt || {}));
    const text = await r.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = { raw: text }; }
    if (!r.ok) {
      const err = (body && (body.error || body.hint)) || r.statusText;
      throw new Error(r.status + " " + err);
    }
    return body;
  }

  function showTab(name) {
    document.querySelectorAll(".tab").forEach((el) => el.classList.toggle("on", el.id === "tab-" + name));
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  }

  function paintVerdict(doc) {
    const v = (doc && doc.verdict) || "—";
    $("verdict-word").textContent = v;
    document.body.className = "v-" + v;
    const bits = [];
    if (doc && doc.stamp) bits.push(doc.stamp);
    if (doc && doc.exit_code != null) bits.push("exit " + doc.exit_code);
    if (doc && doc.sudo != null) bits.push(doc.sudo ? "sudo" : "uten root");
    $("verdict-sub").textContent = bits.join(" · ") || "Ingen snapshot ennå.";
    const box = $("findings");
    box.innerHTML = "";
    (doc && doc.findings ? doc.findings : []).forEach((f) => {
      const el = document.createElement("article");
      el.className = "card sev-" + (f.severity || "INFO");
      el.innerHTML = "<div class=\"id\">" + esc(f.severity) + " · " + esc(f.id) + "</div>" +
        "<h3>" + esc(f.title || "") + "</h3>" +
        (f.detail ? "<pre>" + esc(String(f.detail).slice(0, 1200)) + "</pre>" : "");
      box.appendChild(el);
    });
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  async function loadStatus() {
    try {
      const h = await fetch("/v1/health").then((r) => r.json());
      $("health").textContent = h.root ? "API root" : "API uten root (scan/playbooks 403)";
    } catch {
      $("health").textContent = "API nede";
    }
    if (!token()) {
      $("gate").hidden = false;
      $("gate-msg").textContent = "Token mangler.";
      return;
    }
    $("gate").hidden = true;
    try {
      const v = await api("/v1/verdict/latest");
      paintVerdict(v);
    } catch (e) {
      if (String(e.message).startsWith("404")) {
        paintVerdict(null);
        $("verdict-sub").textContent = "Ingen scan ennå.";
      } else {
        $("gate").hidden = false;
        $("gate-msg").textContent = e.message;
      }
    }
    try {
      const s = await api("/v1/snapshots");
      const ul = $("snap-list");
      ul.innerHTML = "";
      (s.snapshots || []).forEach((x) => {
        const li = document.createElement("li");
        li.innerHTML = "<span>" + esc(x.stamp) + "</span><span>" + esc(x.verdict || "") + "</span>";
        li.onclick = async () => {
          const d = await api("/v1/snapshots/" + encodeURIComponent(x.stamp));
          paintVerdict(d.verdict || d);
        };
        ul.appendChild(li);
      });
    } catch { /* ignore */ }
  }

  function renderConfig(cfg) {
    const form = $("cfg-form");
    form.innerHTML = "";
    Object.keys(cfg).sort().forEach((k) => {
      const lab = document.createElement("label");
      lab.appendChild(document.createTextNode(k));
      let input;
      if (ENUMS[k]) {
        input = document.createElement("select");
        ENUMS[k].forEach((opt) => {
          const o = document.createElement("option");
          o.value = opt; o.textContent = opt;
          if (cfg[k] === opt) o.selected = true;
          input.appendChild(o);
        });
      } else if (BOOLS.has(k)) {
        input = document.createElement("select");
        ["true", "false"].forEach((opt) => {
          const o = document.createElement("option");
          o.value = opt; o.textContent = opt;
          if (String(cfg[k]) === opt) o.selected = true;
          input.appendChild(o);
        });
      } else {
        input = document.createElement("input");
        input.type = NUMS.has(k) ? "number" : "text";
        input.value = cfg[k] == null ? "" : cfg[k];
      }
      input.name = k;
      if (k === "listen_bind") input.setAttribute("pattern", "127\\.0\\.0\\.1|::1|localhost");
      lab.appendChild(input);
      form.appendChild(lab);
    });
  }

  async function loadConfig() {
    const doc = await api("/v1/config");
    renderConfig(doc.config || {});
  }

  function readConfigForm() {
    const out = {};
    $("cfg-form").querySelectorAll("input,select").forEach((el) => {
      const k = el.name;
      let v = el.value;
      if (BOOLS.has(k)) v = v === "true";
      else if (NUMS.has(k)) v = Number(v);
      out[k] = v;
    });
    return out;
  }

  async function loadPlaybooks() {
    const doc = await api("/v1/playbooks");
    const box = $("pb-list");
    box.innerHTML = "";
    (doc.playbooks || []).forEach((name) => {
      const row = document.createElement("div");
      row.className = "pb";
      const left = document.createElement("div");
      left.textContent = name;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Kjør";
      btn.onclick = () => runPlaybook(name);
      row.appendChild(left);
      row.appendChild(btn);
      box.appendChild(row);
    });
  }

  async function runPlaybook(name) {
    if (!$("pb-confirm").checked) {
      $("pb-log").hidden = false;
      $("pb-log").textContent = "Kryss av confirm først.";
      return;
    }
    const args = [];
    if (name === "docker-hygiene") args.push("--prune");
    if (name === "aide-init") args.push("--force");
    $("pb-log").hidden = false;
    $("pb-log").textContent = "kjører " + name + "…";
    try {
      const r = await api("/v1/playbooks/" + encodeURIComponent(name), {
        method: "POST",
        body: JSON.stringify({ confirm: true, args }),
      });
      $("pb-log").textContent = JSON.stringify(r, null, 2);
    } catch (e) {
      $("pb-log").textContent = e.message;
    }
  }

  $("save-token").onclick = () => {
    localStorage.setItem(tokenKey, $("token").value.trim());
    loadStatus();
  };
  $("token").value = localStorage.getItem(tokenKey) || "";

  document.querySelectorAll(".tabs button").forEach((b) => {
    b.onclick = () => {
      showTab(b.dataset.tab);
      if (b.dataset.tab === "settings") loadConfig().catch((e) => { $("cfg-msg").textContent = e.message; });
      if (b.dataset.tab === "playbooks") loadPlaybooks().catch((e) => { $("pb-log").hidden = false; $("pb-log").textContent = e.message; });
      if (b.dataset.tab === "advise") setTimeout(fitTerm, 50);
    };
  });

  let term = null;
  let termWs = null;

  function fitTerm() {
    if (!term || !window.FitAddon) return;
    try {
      const Fit = window.FitAddon.FitAddon || window.FitAddon;
      if (term._fit) term._fit.fit();
    } catch { /* ignore */ }
  }

  function attachTerm() {
    if (term) {
      fitTerm();
      return;
    }
    const Term = window.Terminal;
    if (!Term) {
      $("term-who").textContent = "xterm.js mangler (helper-kopi)";
      return;
    }
    term = new Term({
      cursorBlink: true,
      fontSize: 15,
      fontFamily: 'ui-monospace, "Cascadia Code", "Fira Code", Menlo, Consolas, monospace',
      theme: {
        background: "#020804",
        foreground: "#7CFFB2",
        cursor: "#C8FF6A",
        selectionBackground: "#2dd4bf66",
        black: "#0b1020",
        red: "#ff5d73",
        green: "#5ee0b5",
        yellow: "#e8a85c",
        blue: "#7eb6ff",
        magenta: "#b9a7ff",
        cyan: "#2dd4bf",
        white: "#f4efe4",
      },
      scrollback: 4000,
    });
    if (window.FitAddon) {
      const Fit = window.FitAddon.FitAddon || window.FitAddon;
      term._fit = new Fit();
      term.loadAddon(term._fit);
    }
    term.open($("term"));
    fitTerm();
    window.addEventListener("resize", fitTerm);
  }

  function connectTerm() {
    if (!token()) {
      $("term-who").textContent = "token mangler";
      return;
    }
    attachTerm();
    if (termWs && termWs.readyState === 1) return;
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const url = proto + "://" + location.host + "/v1/term/ws?token=" + encodeURIComponent(token());
    termWs = new WebSocket(url);
    termWs.binaryType = "arraybuffer";
    $("term-who").textContent = "kobler…";
    termWs.onopen = () => {
      $("term-led").classList.add("on");
      $("btn-term").textContent = "Tilkoblet";
      if (term && term._fit) {
        term._fit.fit();
        termWs.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
      }
      api("/v1/term").then((info) => {
        $("term-who").textContent = info.root ? "root @ host (sudo API)" : "uid " + info.uid + " (start API med sudo for root)";
        $("term-led").classList.toggle("root", !!info.root);
      }).catch(() => { $("term-who").textContent = "PTY oppe"; });
    };
    termWs.onmessage = (ev) => {
      if (!term) return;
      let chunk = "";
      if (typeof ev.data === "string") chunk = ev.data;
      else chunk = new TextDecoder().decode(ev.data);
      term.write(typeof ev.data === "string" ? ev.data : new Uint8Array(ev.data));
      window.__termBuf = ((window.__termBuf || "") + chunk).slice(-8000);
    };
    termWs.onclose = () => {
      $("term-led").classList.remove("on", "root");
      $("btn-term").textContent = "Koble til";
      $("term-who").textContent = "frakoblet";
    };
    termWs.onerror = () => { $("term-who").textContent = "ws-feil"; };
    if (term && !term._dataBound) {
      term._dataBound = true;
      term.onData((d) => {
        if (termWs && termWs.readyState === 1) termWs.send(d);
      });
    }
  }

  $("btn-term").onclick = connectTerm;

  (function splitAdvise() {
    const g = $("advise-gutter");
    const panes = document.querySelector(".advise-panes");
    const top = $("advise-top");
    const bot = $("advise-bot");
    if (!g || !panes || !top || !bot) return;
    g.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const rect = panes.getBoundingClientRect();
      const move = (ev) => {
        const y = ev.clientY - rect.top;
        const pct = Math.min(82, Math.max(18, (y / rect.height) * 100));
        top.style.flex = pct + " 1 0";
        bot.style.flex = (100 - pct) + " 1 0";
        if (typeof fitTerm === "function") fitTerm();
      };
      const up = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    });
  })();

  $("btn-scan").onclick = async () => {
    $("btn-scan").disabled = true;
    $("scan-msg").textContent = "Scan kjører (kan ta et minutt)…";
    try {
      const r = await api("/v1/scan", {
        method: "POST",
        body: JSON.stringify({ skip_hunt: $("skip-hunt").checked }),
      });
      $("scan-msg").textContent = "exit " + r.exit_code;
      if (r.verdict) paintVerdict(r.verdict);
      else await loadStatus();
    } catch (e) {
      $("scan-msg").textContent = e.message;
    }
    $("btn-scan").disabled = false;
  };

  $("btn-save-cfg").onclick = async () => {
    $("cfg-msg").textContent = "lagrer…";
    try {
      await api("/v1/config", { method: "PUT", body: JSON.stringify(readConfigForm()) });
      $("cfg-msg").textContent = "lagret";
    } catch (e) {
      $("cfg-msg").textContent = e.message;
    }
  };

  function extractCmds(text) {
    const out = [];
    const fences = text.matchAll(/```(?:bash|sh|zsh)?\n([\s\S]*?)```/g);
    for (const m of fences) {
      m[1].split("\n").forEach((line) => {
        const s = line.trim();
        if (s && !s.startsWith("#")) out.push(s);
      });
    }
    const next = text.match(/sudo [^\n`]+/g) || [];
    next.forEach((s) => {
      const t = s.trim();
      if (t && !out.includes(t)) out.push(t);
    });
    return out.slice(0, 8);
  }

  function sendToTerm(cmd) {
    if (!termWs || termWs.readyState !== 1) {
      $("term-who").textContent = "koble til xterm først";
      return;
    }
    if (!$("signal-term").checked) {
      $("term-who").textContent = "huk av «Signal får skrive i xterm»";
      return;
    }
    termWs.send(cmd + "\n");
  }

  function renderTermCmds(advice) {
    const box = $("term-cmds");
    if (!box) return;
    box.innerHTML = "";
    const cmds = extractCmds(advice || "");
    cmds.forEach((cmd) => {
      const row = document.createElement("div");
      row.className = "pb";
      const left = document.createElement("code");
      left.textContent = cmd;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "→ xterm";
      btn.onclick = () => sendToTerm(cmd);
      row.appendChild(left);
      row.appendChild(btn);
      box.appendChild(row);
    });
  }

  function histEl() {
    return $("chat-hist");
  }
  function addBubble(role, text) {
    const box = histEl();
    if (!box) return;
    const div = document.createElement("div");
    div.className = "bubble " + (role === "user" ? "user" : "bot");
    const who = document.createElement("div");
    who.className = "who";
    who.textContent = role === "user" ? "du" : ($("ask-pb").value === "signal" ? "signal" : "ops");
    const body = document.createElement("div");
    body.textContent = text;
    div.appendChild(who);
    div.appendChild(body);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return body;
  }

  $("btn-advise").onclick = async () => {
    const shown = $("ask").value.trim() || "(scan)";
    addBubble("user", shown);
    const wait = addBubble("bot", "tenker…");
    $("term-cmds").innerHTML = "";
    try {
      let ask = $("ask").value;
      const buf = window.__termBuf || "";
      if (($("ask-pb").value || "signal") === "signal" && buf.trim()) {
        ask = (ask ? ask + "\n\n" : "") + "Siste xterm-utskrift:\n```\n" + buf.slice(-2500) + "\n```";
      }
      const r = await api("/v1/ai/advise", {
        method: "POST",
        body: JSON.stringify({ ask: ask, playbook: $("ask-pb").value || "signal" }),
      });
      const text = r.advice || JSON.stringify(r);
      if (wait) wait.textContent = text;
      renderTermCmds(text);
      const box = histEl();
      if (box) box.scrollTop = box.scrollHeight;
    } catch (e) {
      if (wait) wait.textContent = e.message;
    }
  };

  loadStatus();
})();
