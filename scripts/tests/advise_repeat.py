#!/usr/bin/env python3
"""Advise repeat-block: last 8 live stamps. INFO counted, not in findings[]."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "scripts" / "tests" / "fixtures" / "advise-repeat"


def load_advise():
    path = ROOT / "scripts" / "kalived-advise.py"
    spec = importlib.util.spec_from_file_location("kalived_advise", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_repeat_two_stamps() -> None:
    mod = load_advise()
    current = FIX / "2026-10-28_175001"
    verd = json.loads((current / "verdict.json").read_text(encoding="utf-8"))
    payload = mod.redact(verd, current, status_dir=FIX)
    assert all(f.get("severity") != "INFO" for f in payload["findings"]), payload["findings"]
    assert payload.get("info_count") == 1, payload.get("info_count")
    ids = {f.get("id") for f in payload["findings"]}
    assert "PROC-DELETED" in ids
    assert "PROC-HIDDEN-NOISE" not in ids
    procs = payload.get("procs") or {}
    assert procs.get("kind") == "scan-child", procs
    assert procs.get("hidden_raw") == 6 and procs.get("hidden_kept") == 0
    repeat = payload.get("repeat") or {}
    assert repeat.get("window") == 8
    assert "2026-10-28_175001" in (repeat.get("stamps") or [])
    assert "2026-10-28_171551" in (repeat.get("stamps") or [])
    rows = {r["id"]: r for r in (repeat.get("rows") or [])}
    deleted = rows["PROC-DELETED"]
    assert deleted["n"] == 2, deleted
    assert deleted["seen_before"] is True, deleted
    assert deleted["pid"] == "1942", deleted
    assert deleted["exe"] == "gpg-agent", deleted
    assert deleted["first"] == "2026-10-28_171551"
    assert deleted["last"] == "2026-10-28_175001"
    assert deleted["severity"] == "ALERT"
    noise = rows["PROC-HIDDEN-NOISE"]
    assert noise["n"] == 2, noise
    assert noise["kind"] == "scan-child", noise
    assert noise["seen_before"] is True
    assert noise.get("severity") == "INFO"
    assert "candidate" not in json.dumps(noise)
    fim = rows["FIM-AIDE"]
    assert fim["n"] == 2 and fim["seen_before"] is True
    print("OK repeat: gpg-agent 1942 sett før; hidden_raw scan-child; INFO utenfor findings")


def test_one_stamp_not_seen_before() -> None:
    import tempfile
    from shutil import copytree

    mod = load_advise()
    with tempfile.TemporaryDirectory() as d:
        src = FIX / "2026-10-28_175001"
        dest = Path(d) / "2026-10-28_175001"
        copytree(src, dest)
        verd = json.loads((dest / "verdict.json").read_text(encoding="utf-8"))
        payload = mod.redact(verd, dest, status_dir=Path(d))
        rows = {r["id"]: r for r in (payload.get("repeat") or {}).get("rows") or []}
        assert rows["PROC-DELETED"]["seen_before"] is False
        assert rows["PROC-DELETED"]["n"] == 1
        assert rows["PROC-HIDDEN-NOISE"]["kind"] == "scan-child"
    print("OK repeat: én stamp er ikke sett før")


def main() -> int:
    test_repeat_two_stamps()
    test_one_stamp_not_seen_before()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
