#!/usr/bin/env python3
"""投稿ごとの「変えた要素」と結果を突き合わせる（read-only）。

オーナー指示（2026-10-13）:
  「毎回の投稿に違う要素を入れて、どうやると再生回数・フォロワーが増えるか確認して」

設計:
  - 変える要素は **1投稿につき1つ**。複数変えると、何が効いたか分からなくなる。
  - 台帳は `docs/experiments/log.jsonl`（1行＝1投稿）。
      {"date","channel","id","variable","value","note"}
  - このスクリプトが各プラットフォームから実績を取り、
    `docs/insights/experiments.md` に突き合わせ表を出す（手編集しない）。

    .venv/bin/python scripts/experiment_track.py            # 表を再生成
    .venv/bin/python scripts/experiment_track.py --sync     # 台帳に未登録の投稿を雛形で追記

注意（効果の読み方）:
  いまの規模（IG 16〜114再生 / Threads 12〜101views）では、**1本の差は誤差**。
  同じ要素を3本以上出して、**2倍以上の差**が続いたときだけ採用する。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "docs/experiments/log.jsonl"
OUT = ROOT / "docs/insights/experiments.md"
JST = dt.timezone(dt.timedelta(hours=9))


def _env() -> dict[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and line.startswith("META_"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    return env


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def instagram() -> list[dict]:
    e = _env()
    tok, uid = e["META_INSTAGRAM_TOKEN"], e["META_INSTAGRAM_USER_ID"]
    H = "https://graph.instagram.com/v21.0"
    q = urllib.parse.urlencode({"fields": "id,media_product_type,timestamp,permalink,caption",
                                "limit": 25, "access_token": tok})
    out = []
    for m in _get(f"{H}/{uid}/media?{q}").get("data", []):
        q2 = urllib.parse.urlencode({"metric": "views,reach,likes,saved,shares", "access_token": tok})
        try:
            v = {x["name"]: x["values"][0]["value"] for x in _get(f"{H}/{m['id']}/insights?{q2}")["data"]}
        except Exception:  # noqa: BLE001
            v = {}
        out.append({"channel": "instagram", "id": m["id"],
                    "date": dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
                             .astimezone(JST).date().isoformat(),
                    "type": m.get("media_product_type"), "url": m.get("permalink"),
                    "head": (m.get("caption") or "")[:24].replace("\n", " "), **v})
    return out


def threads() -> list[dict]:
    e = _env()
    tok, uid = e["META_ACCESS_TOKEN"], e["META_THREADS_USER_ID"]
    H = "https://graph.threads.net/v1.0"
    q = urllib.parse.urlencode({"fields": "id,timestamp,permalink,text", "limit": 25, "access_token": tok})
    out = []
    for m in _get(f"{H}/{uid}/threads?{q}").get("data", []):
        q2 = urllib.parse.urlencode({"metric": "views,likes,replies,reposts,quotes", "access_token": tok})
        try:
            v = {x["name"]: (x.get("values") or [{}])[0].get("value") for x in _get(f"{H}/{m['id']}/insights?{q2}")["data"]}
        except Exception:  # noqa: BLE001
            v = {}
        out.append({"channel": "threads", "id": m["id"],
                    "date": dt.datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
                             .astimezone(JST).date().isoformat(),
                    "type": "post", "url": m.get("permalink"),
                    "head": (m.get("text") or "")[:24].replace("\n", " "), **v})
    return out


def followers() -> dict:
    e = _env()
    out = {}
    try:
        q = urllib.parse.urlencode({"fields": "followers_count", "access_token": e["META_INSTAGRAM_TOKEN"]})
        out["instagram"] = _get(f"https://graph.instagram.com/v21.0/{e['META_INSTAGRAM_USER_ID']}?{q}").get("followers_count")
    except Exception:  # noqa: BLE001
        pass
    try:
        q = urllib.parse.urlencode({"metric": "followers_count", "access_token": e["META_ACCESS_TOKEN"]})
        d = _get(f"https://graph.threads.net/v1.0/{e['META_THREADS_USER_ID']}/threads_insights?{q}")
        out["threads"] = d["data"][0]["total_value"]["value"]
    except Exception:  # noqa: BLE001
        pass
    return out


def load_log() -> dict[str, dict]:
    if not LOG.exists():
        return {}
    return {r["id"]: r for r in (json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip())}


@click.command(help="投稿ごとの『変えた要素』と結果を突き合わせる。")
@click.option("--sync", is_flag=True, help="台帳に無い投稿を雛形で追記する")
def main(sync: bool) -> None:
    posts = instagram() + threads()
    posts.sort(key=lambda p: p["date"], reverse=True)
    log = load_log()

    if sync:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        added = 0
        with LOG.open("a", encoding="utf-8") as f:
            for p in posts:
                if p["id"] in log:
                    continue
                f.write(json.dumps({"date": p["date"], "channel": p["channel"], "id": p["id"],
                                    "variable": "", "value": "", "note": p["head"]},
                                   ensure_ascii=False) + "\n")
                added += 1
        click.echo(f"台帳に {added} 件を追記しました（variable / value を手で埋める）")
        log = load_log()

    fw = followers()
    lines = ["---", "tags: [insights, experiment]", "status: active",
             f"updated: {dt.datetime.now(JST):%Y-%m-%d %H:%M} JST",
             "updated_by: scripts/experiment_track.py（自動生成・手編集しない）", "---", "",
             "# 🧪 投稿ごとの検証（1投稿＝1要素）", "",
             f"フォロワー: Instagram {fw.get('instagram')} / Threads {fw.get('threads')}", "",
             "> 読み方: いまの規模では**1本の差は誤差**。同じ要素を3本以上出し、"
             "**2倍以上の差**が続いたときだけ採用する。", "",
             "| 日付 | 媒体 | 変えた要素 | 値 | 到達 | 反応 | 冒頭 |", "|---|---|---|---|---|---|---|"]
    for p in posts[:30]:
        r = log.get(p["id"], {})
        reach = p.get("views") if p.get("views") is not None else p.get("reach")
        react = sum(v for k, v in p.items()
                    if k in ("likes", "saved", "shares", "replies", "reposts", "quotes")
                    and isinstance(v, int))
        lines.append(f"| {p['date']} | {p['channel'][:2]} | {r.get('variable') or '—'} | "
                     f"{r.get('value') or '—'} | {reach} | {react} | {p['head']} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"→ {OUT.relative_to(ROOT)} を更新（{len(posts)}件）")


if __name__ == "__main__":
    main()
