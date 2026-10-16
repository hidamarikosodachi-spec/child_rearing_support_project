#!/usr/bin/env python3
"""読者が実際に探している言葉を集める（read-only・需要調査）。

オーナー指示（2026-10-16）: 「とにかくユーザーが求めている内容にどこまで寄せれるか。
常に固定概念を捨てて、新しい試みを」。
→ 企画を「書きたいこと」からではなく、**検索サジェスト（検索欄に出る候補）**から起こす。

    .venv/bin/python scripts/demand_scan.py                 # 既定の種語で → docs/insights/demand.md
    .venv/bin/python scripts/demand_scan.py --seed "夜泣き" --seed "トイトレ"

仕組み:
  - Google の検索候補（suggestqueries・公開エンドポイント）に「種語 + 空白」と
    「種語 + あ〜わ」の頭文字を足して問い合わせ、候補を集める。
  - 送るのは種語だけ（個人情報は送らない）。1語あたり0.3秒あけて、短時間に連打しない。
  - 候補に出てくる回数が多い語ほど、上に並べる（回数＝需要の強さの目安。検索数そのものではない）。
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/insights/demand.md"
JST = dt.timezone(dt.timedelta(hours=9))

SEEDS = [
    "イヤイヤ期", "癇癪 3歳", "赤ちゃん返り", "夜泣き", "寝かしつけ", "トイトレ", "偏食",
    "保育園 行きたくない", "きょうだいげんか", "怒鳴ってしまう", "育児 疲れた",
    "知育", "モンテッソーリ", "幼児教育", "絵本 2歳", "叱り方", "褒め方",
    "言葉が遅い", "発達 心配", "スマホ 子供",
]
HEADS = list("あかさたなはまやらわ")


def suggest(q: str) -> list[str]:
    u = "https://suggestqueries.google.com/complete/search?client=firefox&hl=ja&q=" + urllib.parse.quote(q)
    try:
        raw = urllib.request.urlopen(u, timeout=10).read().decode("utf-8", "ignore")
        return json.loads(raw)[1]
    except Exception:  # noqa: BLE001
        return []


@click.command(help="検索候補から、読者が実際に探している言葉を集める。")
@click.option("--seed", multiple=True, help="種語（複数可）。省略時は既定の20語")
@click.option("--deep/--no-deep", default=True, help="種語＋あ〜わ の頭文字でも問い合わせる")
def main(seed: tuple[str, ...], deep: bool) -> None:
    seeds = list(seed) or SEEDS
    lines = ["---", "tags: [insights, demand]", "status: auto-generated",
             f"updated: {dt.datetime.now(JST):%Y-%m-%d %H:%M} JST",
             "updated_by: scripts/demand_scan.py（自動生成・手編集しない）", "---", "",
             "# 🔎 読者が探している言葉（検索候補）", "",
             "> 企画はここから起こす（[[feedback-chase-user-demand]]）。回数は候補に出た回数で、検索数そのものではない。", ""]
    for s in seeds:
        cnt: collections.Counter[str] = collections.Counter()
        qs = [s + " "] + ([f"{s} {h}" for h in HEADS] if deep else [])
        for q in qs:
            for c in suggest(q):
                rest = c.replace(s, "").strip()
                if rest:
                    for w in rest.split():
                        cnt[w] += 1
            time.sleep(0.3)
        top = [f"{w}({n})" if n > 1 else w for w, n in cnt.most_common(15)]
        lines += [f"## {s}", "", "、".join(top) or "（候補なし）", ""]
        click.echo(f"{s}: {'、'.join(top[:10])}")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
