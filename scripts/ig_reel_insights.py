#!/usr/bin/env python3
"""Instagram リールの再生数・平均視聴時間を取り、docs/insights/ig_reels.md を再生成する（read-only）。

目標（2026-11-09 オーナー）: リール1本あたり再生 500 回。達成まで試行錯誤する
→ docs/growth/reach_goal_v1.md

    .venv/bin/python scripts/ig_reel_insights.py [--limit 30]

履歴は docs/insights/ig_reels_history.jsonl（日付×リール）に追記する。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("META_GRAPH_HOST", "https://graph.instagram.com")
VER = "v21.0"
GOAL = 500


def load_env() -> tuple[str, str]:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return os.environ["META_INSTAGRAM_TOKEN"].strip(), os.environ.get("META_INSTAGRAM_USER_ID", "me").strip()


def get(path: str, tok: str, **params) -> dict:
    q = urllib.parse.urlencode({**params, "access_token": tok})
    try:
        with urllib.request.urlopen(f"{HOST}/{VER}/{path}?{q}", timeout=30) as r:
            return json.load(r)
    except Exception as e:  # noqa: BLE001  1本の失敗で全体を止めない
        return {"error": str(e)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    tok, _ = load_env()

    media = get("me/media", tok, fields="id,caption,timestamp,permalink,media_product_type", limit=a.limit).get("data", [])
    rows = []
    for m in media:
        if m.get("media_product_type") != "REELS":
            continue
        ins = get(f"{m['id']}/insights", tok, metric="views,reach,ig_reels_avg_watch_time,likes,saved,shares,comments")
        v = {x["name"]: x["values"][0]["value"] for x in ins.get("data", [])}
        rows.append({
            "date": m["timestamp"][:10],
            "id": m["id"],
            "url": m["permalink"],
            "cap": (m.get("caption") or "").replace("\n", " ")[:34],
            "views": v.get("views"),
            "reach": v.get("reach"),
            "watch": round((v.get("ig_reels_avg_watch_time") or 0) / 1000, 1),
            "likes": v.get("likes"),
            "saved": v.get("saved"),
            "shares": v.get("shares"),
            "comments": v.get("comments"),
        })

    today = dt.date.today().isoformat()
    hist = ROOT / "docs/insights/ig_reels_history.jsonl"
    with hist.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"on": today, **r}, ensure_ascii=False) + "\n")

    vs = sorted((r["views"] or 0) for r in rows)
    med = vs[len(vs) // 2] if vs else 0
    best = vs[-1] if vs else 0
    lines = [
        "---",
        "tags: [insights, instagram, reel]",
        "status: auto-generated",
        f"updated: {today}",
        "updated_by: scripts/ig_reel_insights.py（自動生成・手編集しない）",
        "related: [[reach_goal_v1]] [[dashboard]]",
        "---",
        "",
        f"# 📹 IG リール別の再生（目標: 1本 {GOAL} 回）",
        "",
        f"> 集計 {today}／リール {len(rows)} 本／**中央値 {med}／最大 {best}**／目標 {GOAL} 到達 **{sum(1 for x in vs if x >= GOAL)} 本**",
        "> 再生数は投稿からの累計。公開日が新しいものは伸びる途中。平均視聴は秒。",
        "",
        "| 公開日 | 再生 | リーチ | 平均視聴(秒) | 保存 | シェア | 冒頭 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['date']} | **{r['views']}** | {r['reach']} | {r['watch']} | {r['saved']} | {r['shares']} | [{r['cap']}]({r['url']}) |")
    (ROOT / "docs/insights/ig_reels.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"リール {len(rows)} 本／中央値 {med}／最大 {best}／目標{GOAL}到達 {sum(1 for x in vs if x >= GOAL)} 本")
    print("→ docs/insights/ig_reels.md")


if __name__ == "__main__":
    main()
