#!/usr/bin/env python3
"""note ダッシュボードの指標（インプレッション・PV・スキ・コメント・フォロワー）を取得する。

背景（2026-09-27）:
  これまで集計していたのは記事別 PV の**累計**だけだった。累計だけ見ると
  「増えていない」に見えるが、note のダッシュボードは**日次のインプレッション**を持っていて、
  そちらは明確に伸びていた（オーナーの指摘で判明）。伸びを見落とさないため、
  ダッシュボードと同じ指標をここで取る。

取得方法:
  note のダッシュボードは GraphQL（POST /api/v3/graphql）。保存済みセッションで
  ブラウザからページを開き、返ってきたレスポンスを拾う（クエリを自前で組まないので UI 変更に強い）。

    .venv/bin/python scripts/note_dashboard.py            # 直近28日
    .venv/bin/python scripts/note_dashboard.py --json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
AUTH = ROOT / ".auth/note_state.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
CREATOR = "hidamari_sodachi"


def fetch() -> dict:
    from playwright.sync_api import sync_playwright

    out: dict = {"summary": None, "chart": [], "followers": None}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(storage_state=str(AUTH), user_agent=UA,
                            viewport={"width": 1400, "height": 1000})
        pg = ctx.new_page()

        def on_resp(r):
            if "graphql" not in r.url or r.request.method != "POST":
                return
            try:
                op = json.loads(r.request.post_data or "{}").get("operationName")
                raw = r.text()
            except Exception:  # noqa: BLE001
                return
            # summary は @defer で multipart ストリームとして届くため、JSON として一発で
            # 読めないことがある。生テキストから metrics ブロックを拾う。
            if "impressionCount" in raw:
                m = re.search(r'"metrics"\s*:\s*\{(.*?)\}', raw, re.S)
                if m:
                    try:
                        out["summary"] = json.loads("{" + m.group(1) + "}")
                    except Exception:  # noqa: BLE001
                        pass
            try:
                body = json.loads(raw)
            except Exception:  # noqa: BLE001
                return
            if not isinstance(body, dict):
                return
            data = body.get("data") or {}
            if op == "Dashboard_MetricChartQuery":
                pts = (data.get("dashboardMetricChart") or {}).get("points") or []
                if pts:
                    out["chart"] = [{"date": x["startDate"], "value": x["value"]} for x in pts]

        pg.on("response", on_resp)
        pg.goto("https://note.com/dashboard", wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(9000)
        if out["summary"] is None:   # @defer の遅延分を待つ
            pg.wait_for_timeout(6000)
        r = ctx.request.get(f"https://note.com/api/v2/creators/{CREATOR}")
        out["followers"] = (r.json().get("data") or {}).get("followerCount")
        ctx.storage_state(path=str(AUTH))
        b.close()
    return out


@click.command(help="note ダッシュボードの指標を取得する（読み取り専用）。")
@click.option("--json", "as_json", is_flag=True)
def main(as_json: bool) -> None:
    d = fetch()
    if as_json:
        click.echo(json.dumps(d, ensure_ascii=False, indent=2))
        return
    # @defer の途中チャンクを拾うと部分値になることがあるため、
    # インプレッション合計はチャート（日次）の合計を正とする（ダッシュボード表示と一致）。
    total = sum(p["value"] for p in d["chart"])
    click.echo("=== note ダッシュボード（直近28日）===")
    click.echo(f"インプレッション: {total}")
    click.echo(f"フォロワー      : {d.get('followers', '—')} 人")
    pts = [p for p in d["chart"] if p["value"]]
    if pts:
        click.echo("\n--- インプレッションの推移（0 の日は省略）---")
        for p in pts[-14:]:
            click.echo(f"  {p['date']}  {p['value']:>4}  {'█' * min(40, p['value'] // 2)}")
        head = sum(p["value"] for p in d["chart"][-7:])
        prev = sum(p["value"] for p in d["chart"][-14:-7])
        click.echo(f"\n直近7日 {head} ／ その前7日 {prev} → {'+' if head >= prev else ''}{head - prev}")


if __name__ == "__main__":
    main()
