#!/usr/bin/env python3
"""Cloudflare Web Analytics（診断サイト）の訪問数を取得する（読み取り専用）。

なぜ必要か:
  D1 には「診断を完了した人」と「途中離脱した人」しか残らない。
  **来たけれど始めなかった人**が見えないため、集客の問題か入口の問題かを切り分けられなかった。

    .venv/bin/python scripts/web_analytics.py             # 直近7日
    .venv/bin/python scripts/web_analytics.py --days 1
"""
from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.cloudflare.com/client/v4/graphql"
QUERY = """
query($account: String!, $since: Time!) {
  viewer { accounts(filter: {accountTag: $account}) {
    rumPageloadEventsAdaptiveGroups(limit: 200, filter: {datetime_geq: $since}) {
      count
      dimensions { requestPath refererHost date }
    }
  } }
}"""


def _env() -> tuple[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("CLOUDFLARE_") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env.get("CLOUDFLARE_API_TOKEN", ""), env.get("CLOUDFLARE_ACCOUNT_ID", "")


def fetch(days: int) -> list[dict]:
    token, account = _env()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    body = json.dumps({"query": QUERY, "variables": {"account": account, "since": since}}).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    if d.get("errors"):
        raise SystemExit(f"取得できません: {[e.get('message') for e in d['errors']]}")
    return d["data"]["viewer"]["accounts"][0]["rumPageloadEventsAdaptiveGroups"]


@click.command(help="診断サイトの訪問数（ページ別・流入元別）を表示する。")
@click.option("--days", default=7, help="何日ぶんを見るか")
@click.option("--json", "as_json", is_flag=True)
def main(days: int, as_json: bool) -> None:
    rows = fetch(days)
    if as_json:
        click.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    total = sum(r["count"] for r in rows)
    pages, refs, dates = Counter(), Counter(), Counter()
    for r in rows:
        d = r["dimensions"]
        pages[d["requestPath"]] += r["count"]
        refs[d["refererHost"] or "直接・不明"] += r["count"]
        dates[d.get("date", "")] += r["count"]
    click.echo(f"=== 診断サイトの訪問（直近{days}日）合計 {total} ===")
    click.echo("※ 2026-09-29 に独自ドメインへ移行。移行前は hidamari-kosodachi.pages.dev 側に計上されている")
    click.echo("\n--- ページ別 ---")
    for k, v in pages.most_common(12):
        click.echo(f"  {v:>4}  {k}")
    click.echo("\n--- 流入元 ---")
    for k, v in refs.most_common(10):
        click.echo(f"  {v:>4}  {k}")
    if len(dates) > 1:
        click.echo("\n--- 日別 ---")
        for k in sorted(dates):
            click.echo(f"  {k}  {dates[k]}")


if __name__ == "__main__":
    main()
