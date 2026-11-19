"""Command-line entrypoint; zero third-party runtime dependencies."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from sentinel.monitor import check_all, read_targets, save_results, summarize


def alert(webhook_url: str, failures: list[dict]) -> None:
    payload = json.dumps({"event": "sentinel.down", "failures": failures}).encode("utf-8")
    req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise URLError(f"Webhook returned {response.status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor HTTP services, record history, and alert via webhook")
    parser.add_argument("--config", default="targets.json", help="JSON list of endpoints")
    parser.add_argument("--db", default="sentinel.sqlite3", help="SQLite history path")
    parser.add_argument("--interval", type=float, default=0, help="Seconds between checks (0: once)")
    parser.add_argument("--report", action="store_true", help="Print historical availability statistics")
    args = parser.parse_args(argv)
    if args.report:
        print(json.dumps(summarize(args.db), indent=2))
        return 0
    if args.interval < 0:
        parser.error("--interval must be >= 0")
    try:
        targets = read_targets(args.config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    webhook = os.getenv("SENTINEL_WEBHOOK_URL", "")
    try:
        while True:
            results = check_all(targets)
            save_results(args.db, results)
            for result in results:
                status = "UP" if result.ok else "DOWN"
                print(f"[{status}] {result.name}: status={result.status} latency={result.latency_ms}ms", flush=True)
            failures = [{"name": r.name, "url": r.url, "status": r.status, "error": r.error} for r in results if not r.ok]
            if failures and webhook:
                try:
                    alert(webhook, failures)
                except (URLError, OSError, TimeoutError) as exc:
                    print(f"Webhook delivery failed: {exc}", file=sys.stderr)
            if not args.interval:
                return 1 if failures else 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
