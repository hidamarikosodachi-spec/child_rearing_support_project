#!/usr/bin/env python3
"""Instagram のプロフィールのリンク先＝note 記事の一覧ページ（/note/）を作る。

オーナー指示（2026-10-18）: 「Instagram と note を連携させたい。Instagram は note 記事への最大限の導線に」。
Instagram で押せるリンクはプロフィールの1本だけなので、そこを note の入口にする。

    .venv/bin/python scripts/build_note_links.py      # → web/note/index.html

仕組み:
  - docs/note/articles/*.md のうち status: published の記事を、公開日の新しい順に並べる。
  - いちばん上を「今日の記事」として大きく出す（リールはその日の note 記事から作るので、見た記事にすぐ届く）。
  - リンクはすべて /go/<noteキー>?s=ig を経由する（web/functions/go/[key].js が D1 の clicks に1行記録して note へ転送）。
  - 記事を公開したら promote_note_article.py の前にこれを回し、web をデプロイする。
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "docs/note/articles"
OUT = ROOT / "web/note/index.html"

GENRE_LABEL = {"G1": "教育方法", "G2": "困りごと", "G3": "親の気持ち", "G4": "研究を読む", "G5": "どんな子に"}


def _fm(path: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8")
    out = {}
    for line in raw.split("---", 2)[1].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.split("  #")[0].strip().strip('"')
    return out


def lead_of(path: Path) -> str:
    """本文冒頭の引用（診断導線の定型文は飛ばす）の1行目を説明文に使う。"""
    body = path.read_text(encoding="utf-8").split("## 記事本文（ここから下を note へ）", 1)[-1]
    for block in re.findall(r"(?:^> .*\n?)+", body, re.M):
        lines = [x[2:].strip() for x in block.strip().splitlines()]
        if any("](" in x or "この記事は" in x for x in lines):
            continue
        return "".join(lines[:2])
    return ""


def items() -> list[dict]:
    rows = []
    for f in ARTICLES.glob("*.md"):
        m = _fm(f)
        key = re.search(r"/n/(n[0-9a-f]{12})", m.get("published_url", ""))
        if m.get("status") != "published" or not key:
            continue
        title = re.sub(r"^\s+", "", m.get("title", ""))
        rows.append({"key": key.group(1), "title": title, "date": str(m.get("published", ""))[:10],
                     "genre": GENRE_LABEL.get(m.get("genre", ""), ""), "lead": lead_of(f)})
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


def main() -> None:
    rows = items()
    e = html.escape
    go = lambda r: f"/go/{r['key']}?s=ig"  # noqa: E731
    top, rest = rows[0], rows[1:12]
    cards = "\n".join(
        f'    <div class="card-item"><a class="card-title" href="{go(r)}">{e(r["title"])}</a>'
        f'<p class="card-meta">{e(r["date"].replace("-", "/"))}{" ・ " + e(r["genre"]) if r["genre"] else ""}</p></div>'
        for r in rest)
    page = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>note の記事 | ひだまりこそだち</title>
<meta name="description" content="Instagram で見た話の続きは、ここから note で読めます。">
<meta name="robots" content="noindex">
<link rel="icon" href="/matcher/logo.svg">
<link rel="stylesheet" href="/matcher/style.css">
</head>
<body>
<div class="wrap">
  <header class="site"><img src="/matcher/logo.svg" alt=""><span class="name">ひだまりこそだち</span></header>
  <h1>リールの続きは、note で</h1>
  <p class="lead">Instagram で見た話の続きを、note に書いています。いちばん上が、今日の記事です。</p>
  <h2>今日の記事</h2>
    <div class="card-item"><a class="card-title" href="{go(top)}">{e(top["title"])}</a>
    <p class="card-desc">{e(top["lead"])}</p>
    <p class="card-meta">{e(top["date"].replace("-", "/"))}{" ・ " + e(top["genre"]) if top["genre"] else ""}</p></div>
    <p><a class="btn" href="{go(top)}">note で読む（無料）</a></p>
  <h2>最近の記事</h2>
{cards}
  <p><a href="https://note.com/hidamari_sodachi">note のすべての記事を見る</a></p>
  <h2>ほかにも</h2>
  <p><a href="/matcher/">わが家のこそだちタイプ診断（18問・約3分）</a></p>
  <p><a href="/kosodachi/">困りごとから探す（2〜3分で読める記事）</a></p>
</div>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"→ {OUT.relative_to(ROOT)}（今日の記事: {top['title'][:30]}／ほか {len(rest)} 本）")


if __name__ == "__main__":
    main()
