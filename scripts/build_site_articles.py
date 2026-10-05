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

import datetime as _dt

# GitHub Actions のランナーは UTC。朝6時台に走ると UTC ではまだ前日で、
# その日の予約記事が出ない（2026-10-05 に実際に取りこぼした）。日本時間で判定する。
_JST = _dt.timezone(_dt.timedelta(hours=9))


def _today() -> str:
    return _dt.datetime.now(_JST).date().isoformat()

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/site/articles"
OUT = ROOT / "web/kosodachi"
SITE = "https://hidamari-kosodachi.com"

# カテゴリは増やさない（迷子になる）。詳細は docs/site/taxonomy_v1.md
TAGS = {  # slug: (表示名, 軸)
    "age-0-1": ("0〜1歳", "年齢"), "age-2-3": ("2〜3歳", "年齢"), "age-4-6": ("4〜6歳", "年齢"),
    "age-any": ("年齢を問わず", "年齢"),
    "morning": ("朝", "場面"), "meal": ("食事", "場面"), "bedtime": ("寝る前", "場面"),
    "hoikuen": ("保育園", "場面"), "asobi": ("遊び", "場面"), "kaimono": ("買うか迷う", "場面"),
    "iraira": ("イライラ", "気持ち"), "jiko": ("自己嫌悪", "気持ち"),
    "fuan": ("不安", "気持ち"), "tsukare": ("疲れ", "気持ち"),
    "kyodai": ("きょうだい", "関係"), "papa": ("パパ", "関係"),
}
AXES = ["年齢", "場面", "気持ち", "関係"]

CAT_DESC = {
    "kimochi": "怒鳴ってしまった、イライラが止まらない、ひとりで抱えている",
    "seikatsu": "寝かしつけ、朝の支度、ごはん、歯みがき",
    "kodomo": "イヤイヤ期、赤ちゃん返り、保育園の朝、かんしゃく",
    "asobi": "知育おもちゃ、動画、絵本",
}

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
      <a href="/kosodachi/">読みもの</a> ・
      <a href="/soudan/">頼れる相談先</a> ・
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
<title>{page_title} | ひだまりこそだち</title>
<meta name="description" content="{lead}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{title} | ひだまりこそだち">
<meta property="og:description" content="{lead}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og}">
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
    <p><a href="/">トップ</a> ・ <a href="/kosodachi/">読みもの</a> ・
      <a href="/kosodachi/all">すべての読みもの</a> ・
      <a href="/soudan/">頼れる相談先</a> ・
      <a href="/about/">このサイトについて</a> ・
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


def render_index(**kw) -> str:
    """一覧系ページのHTML。page_title を省くと title と同じにする（H1は語りかけ、titleは検索語）。"""
    kw.setdefault("page_title", kw["title"])
    return INDEX_TEMPLATE.format(**kw)


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
        if not show_draft and meta.get("date", "") > _today():
            print(f"  skip（予約 {meta.get('date')}）: {f.name}")
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
                f'<a class="tag-chip" href="/kosodachi/tag/{t}">'
                f'{html.escape(TAGS.get(t, (t, ""))[0])}</a>' for t in tags),
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
                          "chars": len(body.replace("\n", "")),
                          "theory": meta.get("theory", ""), "page": page})
    # ---- 一覧・カテゴリ・タグのページを生成 ----
    import json as _j

    def card(a: dict, show_date: bool = False) -> str:
        mins = max(2, round(a["chars"] / 450))
        meta_bits = [f"約{mins}分"]
        if show_date:
            meta_bits.append(a["date"].replace("-", "/"))
        ages = [TAGS[t][0] for t in a["tags"] if t.startswith("age-")]
        if ages:
            meta_bits.append("・".join(ages))
        # リンクはタイトルだけ（読み上げでタイトル＋本文が1つのリンク名にならないように）
        return (f'      <div class="card-item">'
                f'<a class="card-title" href="/kosodachi/{a["slug"]}">{html.escape(a["title"])}</a>'
                f'<p class="card-desc">{html.escape(a["description"])}</p>'
                f'<p class="card-meta">{" ・ ".join(meta_bits)}</p></div>')

    by_date = sorted(meta_list, key=lambda a: (a["date"], a["slug"]), reverse=True)
    pops = popular_slugs()
    by_pop = [a for s_ in pops for a in meta_list if a["slug"] == s_]

    # 記事ページ（関連記事・タグ表示を差し込んでから書き出す）
    for a in meta_list:
        rel = [x for x in by_date if x["slug"] != a["slug"] and x["category"] == a["category"]][:3]
        block = ("  <h2>同じテーマの読みもの</h2>\n" + "\n".join(card(x) for x in rel) + "\n") if rel else ""
        block += ('  <div class="card" style="margin-top:20px"><p class="note">'
                  '読むより、誰かに話したいときは、<a href="/soudan/">頼れる相談先</a>もあります。'
                  '「まだそこまでではない」と思う段階で使って大丈夫です。</p></div>\n')
        block += ('  <div class="about-article">\n'
                  '    <p class="ttl">この記事について</p>\n'
                  f'    <p>参考にした考え方：{html.escape(a["theory"]) if a["theory"] else "—"}</p>\n'
                  f'    <p>最終更新：{a["date"].replace("-", "/")}</p>\n'
                  '    <p>書いているのは、0〜6歳の子と過ごす人のための小さなメディア「ひだまりこそだち」です。'
                  '専門家の監修は受けていません。医療や発達の判断が必要なことは、'
                  '<a href="/soudan/">相談先</a>をご案内しています。'
                  '<a href="/about/">編集方針</a></p>\n'
                  '  </div>\n')
        (OUT / f'{a["slug"]}.html').write_text(a["page"].replace("{related}", block), encoding="utf-8")

    (OUT / "articles.json").write_text(
        _j.dumps([{k: a[k] for k in ("slug", "title", "description", "category", "tags", "date")}
                  for a in by_date], ensure_ascii=False, indent=2), encoding="utf-8")

    def cat_cards() -> str:
        out = []
        for cs, cn in CATEGORIES.items():
            items = [a for a in meta_list if a["category"] == cs]
            if not items:
                continue
            out.append(f'      <a class="cat" href="/kosodachi/category/{cs}"><b>{cn}</b>'
                       f'<span>{html.escape(CAT_DESC.get(cs, ""))}</span>'
                       f'<span class="n">{len(items)}本</span></a>')
        return "\n".join(out)

    def tag_block() -> str:
        out = []
        for axis in AXES:
            chips = []
            for t, (label, ax) in TAGS.items():
                if ax != axis:
                    continue
                n = len([a for a in meta_list if t in a["tags"]])
                if n:
                    chips.append(f'<a class="tag-chip" href="/kosodachi/tag/{t}">{html.escape(label)}'
                                 f'<span class="n">{n}</span></a>')
            if chips:
                out.append(f'  <p class="tag-axis">{axis}</p>\n  <p class="tags">{"".join(chips)}</p>')
        return "\n".join(out)

    # ---- 一覧トップ：困りごと起点を最上部に（2026-10-01 UXレビュー反映）----
    pick = next((a for a in by_date if a["slug"] == "donatte-shimatta"), by_date[0])
    # 「よくある困りごと」＝親が頭の中で使う言葉で、直接記事へ送る
    QUICK = [
        ("今夜、寝てくれない", "nekashitsuke-jikan"),
        ("朝からもう疲れた", "asa-no-shitaku"),
        ("「いや」しか言わない", "iyaiya-tsukareta"),
        ("ひとりで抱えている", "hitori-de-kakaeru"),
        ("子どもの育ちが気になる", "hoka-to-kuraberu"),
    ]
    quick_html = "\n".join(
        f'      <a class="quick" href="/kosodachi/{sl}">{html.escape(label)}</a>'
        for label, sl in QUICK if any(a["slug"] == sl for a in meta_list))

    body = (f'  <h2>いま困っていることから</h2>\n{cat_cards()}\n'
            f'  <h2>よくある困りごと</h2>\n{quick_html}\n'
            f'  <h2>まず読んでほしい一本</h2>\n{card(pick)}\n'
            f'  <h2>もう少し絞って探す</h2>\n{tag_block()}\n'
            f'  <h2>新着</h2>\n' + "\n".join(card(a, show_date=True) for a in by_date[:5]) + "\n"
            f'  <p style="margin-top:14px"><a class="btn sub" href="/kosodachi/all">'
            f'すべての読みもの（{len(by_date)}本）</a></p>\n'
            f'  <div class="card" style="margin-top:26px">\n'
            f'    <p><b>読むより、誰かに話したいとき</b></p>\n'
            f'    <p class="note">ひとりで抱えなくても大丈夫です。無料で使える相談先をまとめています。</p>\n'
            f'    <a class="btn sub" href="/soudan/">頼れる相談先を見る</a>\n'
            f'  </div>\n')
    (OUT / "index.html").write_text(
        render_index(
            title="いま困っていること、ありますか？",
            page_title="子育ての読みもの一覧",
            lead="寝かしつけ、イヤイヤ、イライラ。2〜3分で読める子育てのヒントを集めています。",
            body=body, canonical=f"{SITE}/kosodachi/",
            og="https://hidamari-kosodachi.com/og/kosodachi.png"), encoding="utf-8")

    # ---- すべての読みもの ----
    all_body = ""
    for cs, cn in CATEGORIES.items():
        items = [a for a in by_date if a["category"] == cs]
        if items:
            all_body += f"  <h2>{cn}</h2>\n" + "\n".join(card(a) for a in items) + "\n"
    (OUT / "all.html").write_text(
        render_index(title=f"すべての読みもの（{len(by_date)}本）",
                              lead="カテゴリごとに並べています。",
                              body=all_body, canonical=f"{SITE}/kosodachi/all",
                              og="https://hidamari-kosodachi.com/og/kosodachi.png"), encoding="utf-8")

    # ---- カテゴリ別 ----
    (OUT / "category").mkdir(exist_ok=True)
    for cs, cn in CATEGORIES.items():
        items = [a for a in by_date if a["category"] == cs]
        if not items:
            continue
        (OUT / "category" / f"{cs}.html").write_text(
            render_index(title=cn, lead=CAT_DESC.get(cs, "") + f"／{len(items)}本",
                                  body="\n".join(card(a) for a in items),
                                  canonical=f"{SITE}/kosodachi/category/{cs}",
                                  og="https://hidamari-kosodachi.com/og/kosodachi.png"), encoding="utf-8")

    # ---- タグ別 ----
    (OUT / "tag").mkdir(exist_ok=True)
    all_tags = sorted({t for a in meta_list for t in a["tags"]})
    for t in all_tags:
        items = [a for a in by_date if t in a["tags"]]
        label = TAGS.get(t, (t, ""))[0]
        (OUT / "tag" / f"{t}.html").write_text(
            render_index(title=label, lead=f"「{label}」の読みもの {len(items)}本",
                                  body="\n".join(card(a) for a in items),
                                  canonical=f"{SITE}/kosodachi/tag/{t}",
                                  og="https://hidamari-kosodachi.com/og/kosodachi.png"), encoding="utf-8")

    print(f"[OK] 記事{len(made)}本 / カテゴリ{len([c for c in CATEGORIES if any(a['category']==c for a in meta_list)])} / タグ{len(all_tags)}軸分類 を生成")
    for s_, t_ in made:
        print(f"  /kosodachi/{s_}  {t_}")


if __name__ == "__main__":
    main()
