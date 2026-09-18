"""Hiroshima room on cockpit :8788. Disk verdict + detached jobs. Does not call :8787."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("KALIVED_DATA", REPO))
STATUS = DATA / "logs" / "status"
MAX_ROUNDS = 8
JOB_TTL_S = 900  # let scan finish; watchdog kills after this
JOB_DIR = Path.home() / ".config/kalived/memory/_hiroshima"

RUNS = {
    "scan": ["sudo", "-n", "kalived-ctl", "scan"],
    "defs": ["sudo", "-n", "kalived-ctl", "defs"],
}

router = APIRouter(prefix="/v1/hiroshima", tags=["hiroshima"])

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_watch_started = False


def _ctl() -> str | None:
    for p in ("/usr/sbin/kalived-ctl", "/usr/local/sbin/kalived-ctl"):
        if os.path.isfile(p):
            return p
    return shutil.which("kalived-ctl")


def latest_snapshot() -> Path | None:
    if not STATUS.is_dir():
        return None
    best: Path | None = None
    for d in STATUS.iterdir():
        if not d.is_dir() or not (d / "verdict.json").is_file():
            continue
        meta = d / "meta.txt"
        if meta.is_file() and "kalived_scan=1" not in meta.read_text(encoding="utf-8", errors="replace"):
            continue
        if best is None or d.name > best.name:
            best = d
    return best


def _read_verdict(snap: Path) -> dict:
    verd = snap / "verdict.json"
    try:
        doc = json.loads(verd.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"verdict.json: {e}") from e
    if not isinstance(doc, dict):
        raise HTTPException(500, "verdict.json ikke objekt")
    doc.setdefault("stamp", snap.name)
    doc["path"] = str(snap)
    return doc


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _still_ours(pid: int, name: str) -> bool:
    """False if pid reused — then we must not keep watching."""
    try:
        raw = Path(f"/proc/{int(pid)}/cmdline").read_bytes()
    except OSError:
        return False
    cmd = raw.replace(b"\x00", b" ").decode("utf-8", "replace").lower()
    return "kalived-ctl" in cmd or "kalived-scan" in cmd or name in cmd


def _close_log(j: dict) -> None:
    fh = j.get("log_fh")
    if fh:
        try:
            fh.close()
        except OSError:
            pass
        j["log_fh"] = None


def _kill_group(j: dict, sig: int) -> None:
    pid = j.get("pid")
    pgid = j.get("pgid") or pid
    if not pid:
        return
    try:
        os.killpg(int(pgid), sig)
    except OSError:
        try:
            os.kill(int(pid), sig)
        except OSError:
            pass


def _close_job(j: dict, status: str, *, code: int | None = None, error: str | None = None) -> None:
    """Terminal state. Never restart. Routine scans belong on cron/timer."""
    if j.get("status") != "running":
        return
    proc = j.get("proc")
    if proc is not None:
        try:
            proc.poll()
            if proc.returncode is None and status != "done":
                _kill_group(j, signal.SIGTERM)
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    _kill_group(j, signal.SIGKILL)
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
        except Exception:
            pass
        if code is None:
            code = proc.returncode
    elif status != "done" and j.get("pid") and _alive(int(j["pid"])) and _still_ours(int(j["pid"]), j.get("name") or ""):
        _kill_group(j, signal.SIGTERM)
        time.sleep(0.4)
        if _alive(int(j["pid"])):
            _kill_group(j, signal.SIGKILL)
    j["exit_code"] = code
    j["status"] = status
    j["stopped"] = True
    if error:
        j["error"] = error
    _close_log(j)


def _public(j: dict) -> dict:
    out = {
        "job_id": j["id"],
        "name": j["name"],
        "status": j["status"],
        "pid": j.get("pid"),
        "started": j.get("started"),
        "elapsed_s": int(time.time() - j["t0"]) if j.get("t0") else None,
        "deadline_s": JOB_TTL_S,
        "exit_code": j.get("exit_code"),
        "hint": j.get("hint"),
        "error": j.get("error"),
        "mode": "oneshot",
        "stopped": j.get("status") != "running",
    }
    if j["status"] in ("done", "timeout", "error"):
        snap = latest_snapshot()
        if snap:
            try:
                verd = json.loads((snap / "verdict.json").read_text(encoding="utf-8"))
                out["verdict"] = {
                    "stamp": snap.name,
                    "verdict": verd.get("verdict"),
                    "exit_code": verd.get("exit_code"),
                }
            except json.JSONDecodeError:
                pass
        log = Path(j.get("log") or "")
        if log.is_file():
            try:
                out["log_tail"] = log.read_text(encoding="utf-8", errors="replace")[-3000:]
            except OSError:
                pass
    return out


def _reap(j: dict) -> None:
    pid = j.get("pid")
    if j["status"] != "running" or not pid:
        return
    now = time.time()
    alive = _alive(int(pid)) and _still_ours(int(pid), j.get("name") or "")
    if not alive:
        proc = j.get("proc")
        code = proc.poll() if proc is not None else None
        _close_job(j, "done", code=code)
        log = Path(j.get("log") or "")
        text = ""
        if log.is_file():
            try:
                text = log.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                pass
        if code not in (0, None) and ("password" in text or "a password is required" in text):
            j["hint"] = "sudo -n nektet — passord i xterm: sudo kalived-ctl " + j["name"]
        return
    if now - j["t0"] > JOB_TTL_S:
        _close_job(j, "timeout", code=-9, error=f"watchdog {JOB_TTL_S}s — ferdig-vindu slutt, stoppet. Rutine er cron.")


def _watch_loop() -> None:
    while True:
        time.sleep(2)
        with _lock:
            for j in list(_jobs.values()):
                try:
                    _reap(j)
                except Exception:
                    continue
            try:
                _persist()
            except OSError:
                pass


def _persist() -> None:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    slim = []
    kept = [j for j in _jobs.values() if j.get("status") == "running"]
    done = [j for j in _jobs.values() if j.get("status") != "running"]
    done.sort(key=lambda x: x.get("t0") or 0, reverse=True)
    for j in [*kept, *done[:8]]:
        slim.append(
            {
                "id": j["id"],
                "name": j["name"],
                "pid": j.get("pid"),
                "pgid": j.get("pgid"),
                "log": j.get("log"),
                "status": j["status"],
                "t0": j.get("t0"),
                "started": j.get("started"),
                "exit_code": j.get("exit_code"),
                "hint": j.get("hint"),
                "error": j.get("error"),
            }
        )
    tmp = JOB_DIR / "jobs.json.tmp"
    tmp.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(JOB_DIR / "jobs.json")


def _load_persisted() -> None:
    p = JOB_DIR / "jobs.json"
    if not p.is_file():
        return
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(raw, list):
        return
    for item in raw:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        jid = str(item["id"])
        if jid in _jobs:
            continue
        st = item.get("status") or "running"
        pid = item.get("pid")
        if st == "running" and (not pid or not _alive(int(pid)) or not _still_ours(int(pid), str(item.get("name") or ""))):
            st = "done"
        _jobs[jid] = {
            "id": jid,
            "name": item.get("name") or "scan",
            "pid": pid,
            "pgid": item.get("pgid"),
            "proc": None,
            "log": item.get("log"),
            "status": st,
            "t0": float(item.get("t0") or time.time()),
            "started": item.get("started"),
            "exit_code": item.get("exit_code"),
            "hint": item.get("hint"),
            "error": item.get("error"),
            "stopped": st != "running",
        }


def ensure_watch() -> None:
    global _watch_started
    with _lock:
        if _watch_started:
            return
        _watch_started = True
        JOB_DIR.mkdir(parents=True, exist_ok=True)
        _load_persisted()
        t = threading.Thread(target=_watch_loop, name="hiroshima-watch", daemon=True)
        t.start()


def start_named(name: str, confirm: bool) -> dict:
    ensure_watch()
    if not confirm:
        return {"error": "confirm=true kreves"}
    argv = RUNS.get(name)
    if not argv:
        return {"error": f"ukjent run: {name}", "have": sorted(RUNS)}
    with _lock:
        for j in _jobs.values():
            if j["name"] == name and j["status"] == "running":
                _reap(j)
                if j["status"] == "running":
                    return {**_public(j), "note": "allerede i gang — den får bli ferdig"}
    ctl = _ctl()
    cmd = list(argv)
    if cmd[0] == "sudo" and ctl:
        cmd = ["sudo", "-n", ctl, *cmd[3:]]
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    jid = str(uuid.uuid4())[:12]
    log = JOB_DIR / f"{jid}.log"
    env = {**os.environ, "NO_COLOR": "1", "KALIVED_DATA": str(DATA)}
    try:
        fh = log.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO),
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
        # keep fh so GC doesn't close the child's stdout
    except FileNotFoundError:
        return {"error": "kalived-ctl mangler — sudo i xterm: sudo kalived-ctl " + name}
    job = {
        "id": jid,
        "name": name,
        "argv": cmd,
        "pid": proc.pid,
        "pgid": os.getpgid(proc.pid) if proc.pid else proc.pid,
        "proc": proc,
        "log_fh": fh,
        "log": str(log),
        "status": "running",
        "t0": time.time(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "exit_code": None,
        "hint": None,
        "error": None,
    }
    try:
        fh.write(f"# {' '.join(cmd)} pid={proc.pid}\n")
        fh.flush()
    except OSError:
        pass
    with _lock:
        _jobs[jid] = job
        try:
            _persist()
        except OSError:
            pass
    return _public(job)


def job_get(jid: str) -> dict | None:
    ensure_watch()
    with _lock:
        j = _jobs.get(jid)
        if not j:
            return None
        _reap(j)
        return _public(j)


def jobs_list() -> list[dict]:
    ensure_watch()
    with _lock:
        for j in _jobs.values():
            _reap(j)
        return [_public(j) for j in sorted(_jobs.values(), key=lambda x: x.get("t0") or 0, reverse=True)]


def run_named(name: str, confirm: bool) -> dict:
    """Start (or join) a detached job. Does not block until done — scan must finish on its own."""
    return start_named(name, confirm)


@router.get("/health")
def health():
    snap = latest_snapshot()
    running = [j for j in jobs_list() if j["status"] == "running"]
    return {
        "ok": True,
        "service": "hiroshima",
        "uid": os.geteuid(),
        "term": "/v1/term",
        "kernel_8787": "urørt",
        "ctl": _ctl(),
        "latest": snap.name if snap else None,
        "max_rounds": MAX_ROUNDS,
        "job_ttl_s": JOB_TTL_S,
        "running": running,
    }


@router.get("/verdict")
def verdict():
    snap = latest_snapshot()
    if not snap:
        raise HTTPException(404, "ingen snapshot")
    return _read_verdict(snap)


@router.get("/snapshots")
def snapshots(limit: int = 20):
    limit = max(1, min(limit, 80))
    out: list[dict] = []
    if not STATUS.is_dir():
        return {"snapshots": out}
    for d in sorted(STATUS.iterdir(), key=lambda p: p.name, reverse=True):
        verd = d / "verdict.json"
        if not verd.is_file():
            continue
        try:
            doc = json.loads(verd.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append(
            {
                "stamp": d.name,
                "verdict": doc.get("verdict"),
                "exit_code": doc.get("exit_code"),
            }
        )
        if len(out) >= limit:
            break
    return {"snapshots": out}


@router.get("/snapshots/{stamp}")
def snapshot_one(stamp: str):
    if "/" in stamp or stamp.startswith("."):
        raise HTTPException(400, "ugyldig stamp")
    snap = STATUS / stamp
    if not (snap / "verdict.json").is_file():
        raise HTTPException(404, "not found")
    return _read_verdict(snap)


@router.get("/jobs")
def jobs():
    return {"jobs": jobs_list()}


@router.get("/jobs/{jid}")
def job_one(jid: str):
    j = job_get(jid)
    if not j:
        raise HTTPException(404, "ukjent job")
    return j


class ConfirmIn(BaseModel):
    confirm: bool = False
    skip_hunt: bool = False


class RunIn(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,20}$")
    confirm: bool = False


@router.post("/scan")
def scan(body: ConfirmIn):
    return start_named("scan", body.confirm)


@router.post("/run")
def run(body: RunIn):
    return start_named(body.name, body.confirm)
