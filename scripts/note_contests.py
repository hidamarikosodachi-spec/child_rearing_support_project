#!/usr/bin/env python3
"""note の開催中コンテスト・常設お題を読み取り、応募できるものを知らせる（read-only）。

なぜ必要か:
  note のコンテスト/お題は**無料の打席**（応募するとお題ページに並ぶ＝露出が増える）。
  ただし育児系のコンテストは常時あるわけではなく、開いた時に気づけないと取り逃す。

    .venv/bin/python scripts/note_contests.py          # 開催中のコンテスト＋育児系の常設お題
    .venv/bin/python scripts/note_contests.py --all    # 常設お題も全部出す
"""
from __future__ import annotations

import json
import urllib.request

import click

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
# 育児・家族・暮らし系の拾い語（ブランドが自然に応募できる範囲）
KEYWORDS = ["子育て", "育児", "子ども", "子供", "ママ", "パパ", "親", "家族", "赤ちゃん",
            "保育", "幼児", "教育", "学び", "暮らし", "家事"]


def fetch() -> list[dict]:
    seen, out = set(), []
    for page in range(1, 4):
        req = urllib.request.Request(f"https://note.com/api/v2/contests?page={page}",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read().decode())["data"]["contests"]
        if not rows:
            break
        for c in rows:
            if c["id"] not in seen:
                seen.add(c["id"])
                out.append(c)
    return out


@click.command(help="note の開催中コンテストと、育児系の常設お題を一覧する。")
@click.option("--all", "show_all", is_flag=True, help="常設お題を全部出す")
def main(show_all: bool) -> None:
    rows = fetch()
    live = [c for c in rows if c.get("type") in ("contest", "contestLight") and c.get("state") == "opened"]
    click.echo(f"=== 開催中のコンテスト {len(live)}件 ===")
    for c in live:
        hit = "★育児系" if any(k in c["name"] for k in KEYWORDS) else "  "
        n = (c.get("hashtag") or {}).get("count")
        click.echo(f"{hit} {c['name']}  {str(c.get('openAt'))[:10]}〜{str(c.get('closeAt'))[:10]}  応募{n}件")
        click.echo(f"     https://note.com/info/n/{c['note']['key']}")
    if not any(any(k in c["name"] for k in KEYWORDS) for c in live):
        click.echo("→ いま応募できる育児系コンテストはありません（常設お題で打席に立つ）")

    themes = [c for c in rows if c.get("type") == "theme"]
    picked = themes if show_all else [c for c in themes if any(k in c["name"] for k in KEYWORDS)]
    picked.sort(key=lambda c: (c.get("hashtag") or {}).get("count") or 0, reverse=True)
    click.echo(f"\n=== 常設お題（育児系 {len(picked)}件・ハッシュタグを付けるだけで応募）===")
    for c in picked[:25]:
        click.echo(f"  {c['name']}  応募{(c.get('hashtag') or {}).get('count')}件")


if __name__ == "__main__":
    main()
