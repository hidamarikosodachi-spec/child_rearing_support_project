#!/usr/bin/env python3
"""診断（わが家のこそだちタイプ）の回答を集計し docs/insights/matcher.md を生成する（read-only）。

D1 から生データを読んで、タイプ分布・軸の平均・流入元・離脱設問・自由記述を集計する。
自由記述の**原文は出力しない**（プライバシーポリシーの約束）。頻出語と件数のみ。
公開前の試用（announce_date より前の回答）は「試用」として本集計から分けて数える。

    .venv/bin/python scripts/matcher_insights.py            # 集計してダッシュボード再生成
    .venv/bin/python scripts/matcher_insights.py --words    # 頻出語も表示（確認用）
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/insights/matcher.md"
DB = "hidamari-matcher"
ANNOUNCE = "2026-09-25"          # 各SNSで告知した日。これより前は試用として分ける
JST = timezone(timedelta(hours=9))
TYPE_JP = {
    "lighthouse": "灯台", "field": "畑", "bonfire": "たき火", "trail": "山道",
    "engawa": "縁側", "bookshelf": "本棚", "stream": "小川", "meadow": "野原",
}
ORDER = list(TYPE_JP)
STOP = set("こと それ これ ある いる する なる ため よう もの そう どう さん ない です ます から けど でも して いて ても のに ので たい たら れる られ ください 思い 思う 自分 子供 子ども".split())


def fetch() -> list[dict]:
    env = os.environ.copy()
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("CLOUDFLARE_") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    cmd = ["npx", "--yes", "wrangler@latest", "d1", "execute", DB, "--remote", "--json",
           "--command", "SELECT * FROM responses ORDER BY id"]
    r = subprocess.run(cmd, cwd=ROOT / "web", env=env, capture_output=True, text=True, timeout=300)
    m = re.search(r"\[\s*\{.*\}\s*\]", r.stdout, re.S)
    if not m:
        sys.exit(f"D1 から取得できませんでした:\n{r.stdout[-500:]}\n{r.stderr[-500:]}")
    return json.loads(m.group(0))[0]["results"]


def words(texts: list[str]) -> list[tuple[str, int]]:
    """形態素解析は入れず、2-4文字の連続する日本語をざっくり数える（傾向を見る用途）。"""
    c: Counter[str] = Counter()
    for t in texts:
        for tok in re.findall(r"[ぁ-んァ-ヶー一-龠]{2,6}", t or ""):
            if tok not in STOP and len(tok) >= 2:
                c[tok] += 1
    return c.most_common(25)


def bar(n: int, total: int, width: int = 18) -> str:
    return "█" * round(width * n / total) if total else ""


def main() -> None:
    rows = fetch()
    done = [r for r in rows if r.get("type")]
    drops = [r for r in rows if r.get("drop_at") is not None]
    live = [r for r in done if (r["created_at"] or "") >= ANNOUNCE]
    pre = [r for r in done if (r["created_at"] or "") < ANNOUNCE]
    n = len(live)

    L: list[str] = [
        "---", "tags: [insights, matcher, diagnosis]", "status: auto-generated",
        f"date: {datetime.now(JST):%Y-%m-%d}", "related: [[type_system_v1]] [[dashboard]] [[backlog]]",
        "---", "",
        "# 診断インサイト（わが家のこそだちタイプ）", "",
        "> **自動生成（`scripts/matcher_insights.py`）。手で編集しない。**",
        "> 自由記述の原文は載せない（プライバシーポリシーの約束）。頻出語と件数のみ。", "",
        f"集計 {datetime.now(JST):%Y-%m-%d %H:%M} JST ／ 診断URL https://hidamari-kosodachi.pages.dev/matcher/", "",
        "## サマリ", "",
        "| 項目 | 件数 |", "|---|---|",
        f"| 完了した回答（告知 {ANNOUNCE} 以降） | **{n}** |",
        f"| 公開前の試用 | {len(pre)} |",
        f"| 途中離脱 | {len(drops)} |",
        f"| 完了率 | {f'{n / (n + len(drops)) * 100:.0f}%' if n + len(drops) else '—'} |",
        "",
    ]

    if not n:
        L += ["> まだ本番の回答がありません。告知直後は流入まで時間差があるので、数日おいて再集計する。", ""]
    else:
        c = Counter(r["type"] for r in live)
        L += ["## タイプ分布", "", "| タイプ | 件数 | |", "|---|---|---|"]
        for k in ORDER:
            L.append(f"| {TYPE_JP[k]}タイプ | {c.get(k, 0)} | {bar(c.get(k, 0), n)} |")
        L += ["", "## 軸の平均（−2=委ねる/流れる/見守る ⇔ +2=導く/整える/寄り添う）", "",
              "| 軸 | 平均 |", "|---|---|"]
        for f, jp in (("axis_i", "主導権"), ("axis_s", "構造性"), ("axis_r", "応答性")):
            vals = [r[f] for r in live if r.get(f) is not None]
            L.append(f"| {jp} | {sum(vals) / len(vals):+.2f} |" if vals else f"| {jp} | — |")

        ages: Counter[str] = Counter()
        for r in live:
            for a in json.loads(r.get("age") or "[]"):
                ages[a] += 1
        L += ["", "## 読者の状況", "", "**子の年齢**（複数回答）", ""]
        L += [f"- {a}: {v}" for a, v in sorted(ages.items())] or ["- —"]
        sib = Counter(r.get("siblings") for r in live if r.get("siblings"))
        L += ["", "**きょうだい**", ""] + ([f"- {k}: {v}" for k, v in sib.most_common()] or ["- —"])

        refs = Counter((r.get("ref") or "直接・不明").split("?")[0] for r in live)
        L += ["", "## 流入元", "", "| 流入元 | 件数 |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in refs.most_common()]

        ws = [r.get("worry") or "" for r in live if (r.get("worry") or "").strip()]
        L += ["", "## いま、いちばん気になっていること", "",
              f"記入 {len(ws)} 件 / {n} 件（記入率 {len(ws) / n * 100:.0f}%）", ""]
        if ws:
            L += ["**頻出語**（2回以上）", ""]
            L += [f"- {w}: {v}" for w, v in words(ws) if v >= 2] or ["- （まだ傾向が出るほど集まっていない）"]
            L += ["", "> 記事テーマの選定に使う。原文は D1 内のみで扱い、公開しない。"]
        else:
            L += ["> まだ記入なし。"]

    if drops:
        d = Counter(r["drop_at"] for r in drops)
        L += ["", "## 離脱した設問（1-2=年齢/きょうだい、3以降=設問）", "", "| 設問 | 離脱 |", "|---|---|"]
        L += [f"| {k} 問目 | {v} |" for k, v in sorted(d.items())]
        L += ["", "> 特定の問で集中していたら、その質問文を見直す。"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"[OK] {OUT.relative_to(ROOT)} を更新（本番 {n} 件 / 試用 {len(pre)} 件 / 離脱 {len(drops)} 件）")
    if "--words" in sys.argv:
        for w, v in words([r.get("worry") or "" for r in live]):
            print(f"  {w}: {v}")


if __name__ == "__main__":
    main()
