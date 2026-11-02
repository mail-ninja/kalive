#!/usr/bin/env python3
"""VSIX install from a local zip; Open VSX search is mocked."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cockpit" / "backend"))

td = tempfile.mkdtemp(prefix="kalived-ext-")
os.environ["KALIVED_EXTENSIONS"] = str(Path(td) / "ext")
os.environ.setdefault("KALIVED_UP_LOG", "/tmp/kalived-ext-test")

from app import extensions as ext  # noqa: E402

fail = 0


def ok(msg: str) -> None:
    print("  OK", msg)


def bad(msg: str) -> None:
    global fail
    fail = 1
    print("  FAIL", msg)


def make_vsix() -> bytes:
    buf = io.BytesIO()
    pkg = {
        "name": "hello",
        "publisher": "kalived",
        "displayName": "Hello",
        "version": "0.1.0",
        "description": "test vsix",
        "engines": {"vscode": "^1.80.0"},
        "contributes": {"commands": []},
    }
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("extension.vsixmanifest", "<PackageManifest/>")
        z.writestr("extension/package.json", json.dumps(pkg))
        z.writestr("extension/readme.md", "hi\n")
    return buf.getvalue()


print("[install vsix]")
got = ext.install_vsix(make_vsix(), source="test")
if got.get("ok") and got.get("id") == "kalived.hello" and (Path(td) / "ext" / "kalived.hello" / "package.json").is_file():
    ok("installed")
else:
    bad("install " + str(got))

print("[list]")
lst = ext.list_installed()
ids = [e.get("id") for e in lst.get("extensions") or []]
if "kalived.hello" in ids and lst.get("n") == 1:
    ok("list")
else:
    bad("list " + str(lst))

print("[disable]")
off = ext.set_enabled("kalived.hello", False)
if off.get("enabled") is False:
    ok("disabled")
else:
    bad("enable " + str(off))

print("[bad zip]")
badz = ext.install_vsix(b"not-a-zip")
if badz.get("error"):
    ok("bad zip")
else:
    bad("accepted junk " + str(badz))

print("[path escape id]")
esc = ext.uninstall("../etc")
if esc.get("error"):
    ok("id escape")
else:
    bad("escaped " + str(esc))

print("[search mock]")

def fake_json(url: str, timeout: float = 15):
    return {
        "totalSize": 1,
        "extensions": [
            {
                "namespace": "kalived",
                "name": "hello",
                "displayName": "Hello",
                "version": "0.1.0",
                "description": "from mock",
                "files": {"download": "https://open-vsx.org/api/kalived/hello/0.1.0/file/kalived.hello-0.1.0.vsix"},
            }
        ],
    }

ext._http_json = fake_json  # type: ignore[assignment]
sr = ext.search("hello")
if sr.get("ok") and sr["extensions"][0]["id"] == "kalived.hello":
    ok("search mock")
else:
    bad("search " + str(sr))

print("[ssrf]")
from app.extensions import _http_bytes as real_http_bytes

ssrf = real_http_bytes("https://example.com/x.vsix")
if isinstance(ssrf, dict) and "open-vsx" in str(ssrf.get("error") or ""):
    ok("ssrf blocked")
else:
    bad("ssrf " + str(ssrf))

print("[uninstall]")
rm = ext.uninstall("kalived.hello")
lst2 = ext.list_installed()
if rm.get("ok") and lst2.get("n") == 0:
    ok("removed")
else:
    bad("uninstall " + str(rm) + " " + str(lst2))

sys.exit(fail)
