#!/usr/bin/env python3
"""docs/site/articles/*.md → web/kosodachi/<slug>.html を生成する（検索流入用の記事）。

役割の分担（[[writing_voice_web_v1]]）:
  Threads/IG = 物語 ／ note = 連載（理論をとなりに並べる） ／ 自前サイト = 検索から来た人への実用記事

front-matter:
  slug / title / description / search_intent / status(draft|published) / date / theory / related_note

    python3 scripts/build_site_articles.py            # published のみ生成
    python3 scripts/build_site_articles.py --all      # draft も生成（確認用）
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/site/articles"
OUT = ROOT / "web/kosodachi"
SITE = "https://hidamari-kosodachi.com"


def fm_parse(text: str) -> tuple[dict, str]:
    parts = text.split("---", 2)
    meta = {}
    for line in parts[1].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, parts[2].lstrip("\n")


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(md: str) -> str:
    out, para, mode = [], [], None

    def flush():
        nonlocal para, mode
        if para:
            if mode == "ul":
                out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in para) + "</ul>")
            else:
                out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
        para, mode = [], None

    for line in md.split("\n"):
        if not line.strip():
            flush()
        elif line.startswith("# "):
            flush()  # h1 はテンプレ側で出すので本文からは落とす
        elif line.startswith("## "):
            flush(); out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "):
            flush(); out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.strip() == "---":
            flush(); out.append("<hr>")
        elif line.startswith("- "):
            if mode != "ul":
                flush(); mode = "ul"
            para.append(line[2:])
        else:
            if mode != "p":
                flush(); mode = "p"
            para.append(line)
    flush()
    return "\n".join(out)


TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title} | ひだまりこそだち</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{site}/og/matcher.png">
<meta property="og:site_name" content="ひだまりこそだち">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/matcher/logo.svg">
<link rel="stylesheet" href="/matcher/style.css">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Article","headline":{title_json},
"description":{desc_json},"datePublished":"{date}","inLanguage":"ja",
"publisher":{{"@type":"Organization","name":"ひだまりこそだち"}},
"mainEntityOfPage":"{url}"}}
</script>
</head>
<body>
<div class="wrap">
  <header class="site"><img src="/matcher/logo.svg" alt=""><span class="name">ひだまりこそだち</span></header>
  <h1>{title}</h1>
{body}
  <footer>
    <p>ひだまりこそだち — 子育ての考え方を、親のことばに。<br>
      <a href="/">トップ</a> ・
      <a href="/kosodachi/">読みもの一覧</a> ・
      <a href="/matcher/">こそだちタイプ診断</a> ・
      <a href="https://note.com/hidamari_sodachi" target="_blank" rel="noopener">note の連載</a> ・
      <a href="/privacy/">プライバシーについて</a></p>
    <p style="margin-top:10px">この記事は、教育・発達に関する複数の理論をもとにした読みものです。
      医療・心理の診断や治療にかわるものではありません。
      気がかりが強いときは、地域の子育て支援センターや小児科にご相談ください。</p>
  </footer>
</div>
</body>
</html>
"""


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>読みもの一覧 | ひだまりこそだち</title>
<meta name="description" content="子育てで困っていることから読める記事の一覧です。怒鳴ってしまった夜、動画をやめられないとき、保育園の朝に泣かれるとき。">
<link rel="canonical" href="https://hidamari-kosodachi.com/kosodachi/">
<meta property="og:type" content="website">
<meta property="og:title" content="読みもの一覧 | ひだまりこそだち">
<meta property="og:description" content="子育てで困っていることから読める記事の一覧です。">
<meta property="og:url" content="https://hidamari-kosodachi.com/kosodachi/">
<meta property="og:image" content="https://hidamari-kosodachi.com/og/matcher.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/matcher/logo.svg">
<link rel="stylesheet" href="/matcher/style.css">
</head>
<body>
<div class="wrap">
  <header class="site"><img src="/matcher/logo.svg" alt=""><span class="name">ひだまりこそだち</span></header>
  <h1>読みもの</h1>
  <p class="lead">いま困っていることから読めます。</p>
{cards}
  <div class="card" style="margin-top:24px">
    <p><b>わが家のこそだちタイプ診断</b></p>
    <p class="note">18問・約3分。子育てのかたちを8つの風景にしてお返しします。</p>
    <a class="btn" href="/matcher/">診断をはじめる</a>
  </div>
  <footer>
    <p><a href="/">ひだまりこそだち トップ</a> ・
      <a href="/matcher/">診断</a> ・
      <a href="https://note.com/hidamari_sodachi" target="_blank" rel="noopener">note の連載</a> ・
      <a href="/privacy/">プライバシーについて</a></p>
    <p style="margin-top:10px">このサイトの記事は、教育・発達に関する複数の理論をもとにした読みものです。
      医療・心理の診断や治療にかわるものではありません。</p>
  </footer>
</div>
</body>
</html>
"""


def main() -> None:
    show_draft = "--all" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    meta_list = []
    for f in sorted(SRC.glob("*.md")):
        meta, body = fm_parse(f.read_text(encoding="utf-8"))
        if meta.get("status") != "published" and not show_draft:
            print(f"  skip（{meta.get('status')}）: {f.name}")
            continue
        slug = meta["slug"]
        # スマホ幅では 1行あたり約11字。17字前後を超えると文節の途中で折り返りやすく、
        # Google の検索結果でも約30字で切られる（2026-09-30 実測して決めた上限）。
        if len(meta["title"]) > 20:
            print(f"  ⚠ タイトルが長い（{len(meta['title'])}字）: {meta['title']}"
                  f"\n     → スマホで途中改行しやすい。17字前後に縮める")
        url = f"{SITE}/kosodachi/{slug}"
        import json as _json
        page = TEMPLATE.format(
            title=html.escape(meta["title"], quote=True),
            desc=html.escape(meta.get("description", ""), quote=True),
            url=url, site=SITE, date=meta.get("date", ""),
            title_json=_json.dumps(meta["title"], ensure_ascii=False),
            desc_json=_json.dumps(meta.get("description", ""), ensure_ascii=False),
            body=md_to_html(body),
        )
        (OUT / f"{slug}.html").write_text(page, encoding="utf-8")
        made.append((slug, meta["title"]))
        meta_list.append((slug, meta["title"], meta.get("description", "")))
    # 一覧ページと、トップページが読む JSON を生成する
    import json as _j
    (OUT / "articles.json").write_text(
        _j.dumps([{"slug": s_, "title": t_, "description": d_} for s_, t_, d_ in meta_list],
                 ensure_ascii=False, indent=2), encoding="utf-8")
    cards = "\n".join(
        f'      <a class="other" href="/kosodachi/{s_}"><b>{html.escape(t_)}</b>'
        f'<span>{html.escape(d_)}</span></a>' for s_, t_, d_ in meta_list
    ) or '      <p class="note">準備中です。</p>'
    (OUT / "index.html").write_text(INDEX_TEMPLATE.format(cards=cards), encoding="utf-8")

    print(f"[OK] {len(made)} 本を生成 → web/kosodachi/（一覧ページと articles.json も更新）")
    for s, t in made:
        print(f"  /kosodachi/{s}  {t}")
    if made:
        print("※ sitemap は build_matcher_pages.py が生成するので、記事を公開したらそちらも更新する")


if __name__ == "__main__":
    main()
