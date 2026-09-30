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

# カテゴリは増やさない（迷子になる）。詳細は docs/site/taxonomy_v1.md
CATEGORIES = {
    "kimochi": "気持ちがしんどい日に",
    "seikatsu": "毎日の生活",
    "kodomo": "子どもの様子",
    "asobi": "遊びと道具",
}


def popular_slugs() -> list[str]:
    """Web Analytics の実測ページビュー順。取れなければ空（架空の人気順は作らない）。"""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from web_analytics import fetch  # noqa: PLC0415
        rows = fetch(30)
    except Exception:  # noqa: BLE001
        return []
    from collections import Counter
    c: Counter[str] = Counter()
    for r in rows:
        path = r["dimensions"]["requestPath"]
        if path.startswith("/kosodachi/") and path.count("/") == 2:
            c[path.rsplit("/", 1)[-1]] += r["count"]
    return [s for s, _ in c.most_common()]


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
  <p class="step"><a href="/kosodachi/category/{cat_slug}">{cat_name}</a></p>
  <h1>{title}</h1>
{body}
  <p class="tags">{tags_html}</p>
{related}
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
<title>{title} | ひだまりこそだち</title>
<meta name="description" content="{lead}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title} | ひだまりこそだち">
<meta property="og:description" content="{lead}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="https://hidamari-kosodachi.com/og/matcher.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/matcher/logo.svg">
<link rel="stylesheet" href="/matcher/style.css">
</head>
<body>
<div class="wrap">
  <header class="site"><img src="/matcher/logo.svg" alt=""><span class="name">ひだまりこそだち</span></header>
  <h1>{title}</h1>
  <p class="lead">{lead}</p>
{body}
  <div class="card" style="margin-top:24px">
    <p><b>わが家のこそだちタイプ診断</b></p>
    <p class="note">18問・約3分。子育てのかたちを8つの風景にしてお返しします。</p>
    <a class="btn" href="/matcher/">診断をはじめる</a>
  </div>
  <footer>
    <p><a href="/">トップ</a> ・ <a href="/kosodachi/">読みもの一覧</a> ・
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
        cat = meta.get("category", "kimochi")
        tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
        page = TEMPLATE.format(
            cat_slug=cat, cat_name=html.escape(CATEGORIES.get(cat, "読みもの")),
            tags_html="".join(
                f'<a class="tag-chip" href="/kosodachi/tag/{t}">#{html.escape(t)}</a>' for t in tags),
            related="{related}",
            title=html.escape(meta["title"], quote=True),
            desc=html.escape(meta.get("description", ""), quote=True),
            url=url, site=SITE, date=meta.get("date", ""),
            title_json=_json.dumps(meta["title"], ensure_ascii=False),
            desc_json=_json.dumps(meta.get("description", ""), ensure_ascii=False),
            body=md_to_html(body),
        )
        made.append((slug, meta["title"]))
        meta_list.append({"slug": slug, "title": meta["title"],
                          "description": meta.get("description", ""),
                          "category": cat, "tags": tags, "date": meta.get("date", ""),
                          "page": page})
    # ---- 一覧・カテゴリ・タグのページを生成 ----
    import json as _j

    def card(a: dict) -> str:
        return (f'      <a class="other" href="/kosodachi/{a["slug"]}"><b>{html.escape(a["title"])}</b>'
                f'<span>{html.escape(a["description"])}</span></a>')

    by_date = sorted(meta_list, key=lambda a: a["date"], reverse=True)
    pops = popular_slugs()
    by_pop = [a for s_ in pops for a in meta_list if a["slug"] == s_]

    # 記事ページ（関連記事を差し込んでから書き出す）
    for a in meta_list:
        rel = [x for x in by_date if x["slug"] != a["slug"] and x["category"] == a["category"]][:3]
        block = ""
        if rel:
            block = ("  <h2>同じテーマの読みもの</h2>\n"
                     + "\n".join(card(x) for x in rel) + "\n")
        (OUT / f'{a["slug"]}.html').write_text(a["page"].replace("{related}", block), encoding="utf-8")

    (OUT / "articles.json").write_text(
        _j.dumps([{k: a[k] for k in ("slug", "title", "description", "category", "tags", "date")}
                  for a in by_date], ensure_ascii=False, indent=2), encoding="utf-8")

    def section(title: str, items: list[dict]) -> str:
        if not items:
            return ""
        return f"  <h2>{title}</h2>\n" + "\n".join(card(a) for a in items) + "\n"

    cats_html = ""
    for cs, cn in CATEGORIES.items():
        n = len([a for a in meta_list if a["category"] == cs])
        if n:
            cats_html += (f'      <a class="other" href="/kosodachi/category/{cs}">'
                          f'<b>{cn}</b><span>{n}本</span></a>\n')
    all_tags = sorted({t for a in meta_list for t in a["tags"]})
    tags_html = "".join(f'<a class="tag-chip" href="/kosodachi/tag/{t}">#{html.escape(t)}</a>'
                        for t in all_tags)

    # 記事が少ないうちは「人気」と「新着」が同じ並びになって意味がないので出さない
    show_pop = len(meta_list) >= 3 and by_pop
    body = (section("人気の読みもの", by_pop[:5] if show_pop else [])
            + section("新着", by_date[:8])
            + (f"  <h2>カテゴリ</h2>\n{cats_html}" if cats_html else "")
            + (f'  <h2>タグ</h2>\n  <p class="tags">{tags_html}</p>\n' if tags_html else ""))
    (OUT / "index.html").write_text(
        INDEX_TEMPLATE.format(title="読みもの", lead="いま困っていることから読めます。",
                              body=body, canonical=f"{SITE}/kosodachi/"), encoding="utf-8")

    # カテゴリ別
    (OUT / "category").mkdir(exist_ok=True)
    for cs, cn in CATEGORIES.items():
        items = [a for a in by_date if a["category"] == cs]
        if not items:
            continue
        (OUT / "category" / f"{cs}.html").write_text(
            INDEX_TEMPLATE.format(title=cn, lead=f"「{cn}」の読みもの {len(items)}本",
                                  body="\n".join(card(a) for a in items),
                                  canonical=f"{SITE}/kosodachi/category/{cs}"), encoding="utf-8")

    # タグ別
    (OUT / "tag").mkdir(exist_ok=True)
    for t in all_tags:
        items = [a for a in by_date if t in a["tags"]]
        (OUT / "tag" / f"{t}.html").write_text(
            INDEX_TEMPLATE.format(title=f"#{t}", lead=f"「{t}」の読みもの {len(items)}本",
                                  body="\n".join(card(a) for a in items),
                                  canonical=f"{SITE}/kosodachi/tag/{t}"), encoding="utf-8")

    print(f"[OK] 記事{len(made)}本 / カテゴリ{len([c for c in CATEGORIES if any(a['category']==c for a in meta_list)])} / タグ{len(all_tags)} を生成")
    print(f"     人気順: {'表示' if show_pop else '非表示（記事3本未満、または実測データ無し）'}")
    for s_, t_ in made:
        print(f"  /kosodachi/{s_}  {t_}")


if __name__ == "__main__":
    main()
