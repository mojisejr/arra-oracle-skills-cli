#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


TIMEOUT_SECONDS = 4
BODY_SAMPLE_LIMIT = 220


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only preflight probes for Oracle work.")
    parser.add_argument("--env", action="append", default=[], metavar="PATH", help="Probe .env-style file key presence without printing values.")
    parser.add_argument("--endpoint", action="append", default=[], metavar="URL", help="GET endpoint and report status/content presence.")
    parser.add_argument("--host", action="append", default=[], metavar="HOST", help="Resolve host using local DNS.")
    parser.add_argument("--node-abi", action="append", default=[], metavar="MODULE", help="Try requiring a native Node module with current node.")
    args = parser.parse_args(argv)

    print("== oracle preflight raw ==")
    print(f"cwd: {Path.cwd()}")
    print(f"timestamp: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}")

    ran = False
    for path in args.env:
        ran = True
        run_probe(probe_env, Path(path).expanduser())
    for url in args.endpoint:
        ran = True
        run_probe(probe_endpoint, url)
    for host in args.host:
        ran = True
        run_probe(probe_host, host)
    for module in args.node_abi:
        ran = True
        run_probe(probe_node_abi, module)

    if not ran:
        print("no probes requested")
    print("exit: 0")
    return 0


def run_probe(func, *args) -> None:
    try:
        func(*args)
    except Exception as exc:  # noqa: BLE001 - preflight must report failures and exit 0.
        print(f"\n[probe-error] {func.__name__}")
        print(f"error: {type(exc).__name__}: {safe_one_line(str(exc), BODY_SAMPLE_LIMIT)}")


def probe_env(path: Path) -> None:
    print(f"\n[env] {path}")
    if not path.exists():
        print("exists: no")
        return
    if not path.is_file():
        print("exists: yes")
        print("file: no")
        return
    keys = parse_env_keys(path)
    print("exists: yes")
    print(f"keys_count: {len(keys)}")
    if keys:
        print("keys:")
        for key in keys:
            print(f"- {key}: present")
    else:
        print("keys: none")
    print("values: redacted")


def parse_env_keys(path: Path) -> list[str]:
    keys: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as exc:
        print(f"read_error: {exc}")
        return keys
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if key and key not in keys:
            keys.append(key)
    return keys


def probe_endpoint(url: str) -> None:
    print(f"\n[endpoint] {redact_url(url)}")
    request = urllib.request.Request(url, headers={"User-Agent": "oracle-preflight/1.0"})
    status = "unavailable"
    body = ""
    error = ""
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = str(response.status)
            raw = response.read(4096)
            body = raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = str(exc.code)
        try:
            body = exc.read(4096).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        error = f"HTTPError: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - preflight reports all failures and exits 0.
        error = f"{type(exc).__name__}: {exc}"

    meaningful = bool(body.strip())
    print(f"status: {status}")
    print(f"body_bytes_sampled: {len(body.encode('utf-8'))}")
    print(f"content_present: {'yes' if meaningful else 'no'}")
    if body:
        print(f"body_sample: {safe_one_line(body, BODY_SAMPLE_LIMIT)}")
    if error:
        print(f"error: {safe_one_line(error, BODY_SAMPLE_LIMIT)}")


def redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    netloc = parsed.netloc
    if "@" in netloc:
        netloc = "***@" + netloc.rsplit("@", 1)[1]
    query = "…" if parsed.query else ""
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, query, ""))


def safe_one_line(value: str, limit: int) -> str:
    collapsed = " ".join(value.replace("\x00", "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 1)].rstrip() + "…"


def probe_host(host: str) -> None:
    print(f"\n[host] {host}")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        print("resolved: no")
        print(f"error: {exc}")
        return
    addresses = sorted({info[4][0] for info in infos if info and info[4]})
    print("resolved: yes")
    print(f"addresses_count: {len(addresses)}")
    for address in addresses[:8]:
        print(f"- {address}")
    if len(addresses) > 8:
        print(f"- … {len(addresses) - 8} more")


def probe_node_abi(module: str) -> None:
    print(f"\n[node-abi] {module}")
    node = shutil_which("node")
    if not node:
        print("node: missing")
        return
    script = (
        "const mod=process.argv[1];"
        "try{require(mod); console.log('load: ok');}"
        "catch(e){console.log('load: fail'); console.log('error: '+(e&&e.message?e.message:String(e)).split('\\n')[0]);}"
        "console.log('node: '+process.version);"
        "console.log('modules: '+process.versions.modules);"
    )
    try:
        completed = subprocess.run(
            [node, "-e", script, module],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        print(completed.stdout.rstrip() or "(no output)")
    except subprocess.TimeoutExpired:
        print("load: timeout")
        print(f"error: node require timed out after {TIMEOUT_SECONDS}s")
    except Exception as exc:  # noqa: BLE001 - preflight reports all failures and exits 0.
        print("load: error")
        print(f"error: {type(exc).__name__}: {safe_one_line(str(exc), BODY_SAMPLE_LIMIT)}")


def shutil_which(command: str) -> str:
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = Path(directory) / command
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
