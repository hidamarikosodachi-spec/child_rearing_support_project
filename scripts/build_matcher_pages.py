#!/usr/bin/env python3
"""タイプ別の静的ページ・sitemap・robots を生成する（SEO と SNS 共有プレビュー用）。

なぜ必要か:
  診断結果は `?type=xxx` で JS が描画しているが、**SNS のクローラは JS を実行しない**ため、
  共有してもプレビュー画像も説明文も出ない（＝拡散しない）。検索にも載らない。
  タイプごとに静的な HTML を持たせて、OGP と本文を最初から埋めておく。

出力:
  web/matcher/t/<key>.html … タイプ別ページ（OGP・本文・診断への導線）
  web/sitemap.xml / web/robots.txt

    python3 scripts/build_matcher_pages.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
SITE = "https://hidamari-kosodachi.pages.dev"


def load_types() -> tuple[dict, list, str]:
    src = (WEB / "matcher/types.js").read_text(encoding="utf-8")
    body = src.split("export const TYPES = ", 1)[1].split("\n};", 1)[0] + "\n}"
    body = re.sub(r"^(\s*)([a-zA-Z_]\w*):", r'\1"\2":', body, flags=re.M)
    order = json.loads(re.search(r"export const TYPE_ORDER = (\[.*?\]);", src, re.S).group(1))
    disc = json.loads(re.search(r"export const DISCLAIMER = (\".*?\");", src, re.S).group(1))
    return json.loads(body), order, disc


def e(s: str) -> str:
    return html.escape(s, quote=True)


def page(t: dict, types: dict, order: list, disc: str) -> str:
    url = f"{SITE}/matcher/t/{t['key']}"  # Pages は .html を拡張子なしへ 308 するので最初から拡張子なしで書く
    desc = f"{t['lead']}。{t['strength'][:60]}…（わが家のこそだちタイプ診断）"
    theories = "\n".join(
        f"""      <div class="theory"><b>{e(th['t'])}</b> — {e(th['d'])}<br>
        {f'<a href="{th["url"]}" target="_blank" rel="noopener">記事を読む</a>' if th.get('url') else '<span class="note">（連載で書く予定です）</span>'}</div>"""
        for th in t["theories"])
    ease = "\n".join(
        f"      <div class=\"theory\"><b>{e(x.split('。')[0])}。</b>{e('。'.join(x.split('。')[1:]))}</div>"
        for x in t["ease"])
    others = "\n".join(
        f"""      <a class="other" href="{o['key']}"><b>{e(o['label'])}</b><span>{e(o['lead'])}</span>
        <span class="ax">{e(o['axes'])}</span></a>"""
        for o in (types[k] for k in order if k != t["key"]))
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(t['label'])} — わが家のこそだちタイプ | ひだまりこそだち</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:title" content="{e(t['label'])} — {e(t['lead'])}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/og/type_{t['key']}.png">
<meta property="og:site_name" content="ひだまりこそだち">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(t['label'])} — {e(t['lead'])}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="twitter:image" content="{SITE}/og/type_{t['key']}.png">
<link rel="icon" href="../logo.svg">
<link rel="stylesheet" href="../style.css">
</head>
<body>
<div class="wrap">
  <header class="site"><img src="../logo.svg" alt=""><span class="name">ひだまりこそだち</span></header>
  <p class="step">わが家のこそだちタイプ</p>
  <div class="typename">{e(t['label'])}</div>
  <span class="axes">{e(t['axes'])}</span>
  <p class="lead" style="margin-top:14px">{e(t['lead'])}</p>
  <div class="card"><p class="note">{e(disc)}</p></div>
  <p>{e(t['intro'])}</p>
  <h2>大事にしていること</h2><p>{e(t['value'])}</p>
  <h2>強み</h2><p>{e(t['strength'])}</p>
  <h2>つまずきやすいところ</h2><p>{e(t['stumble'])}</p>
  <h2>気持ちが、少し楽になるかもしれない見方</h2>
{ease}
  <h2>明日、ひとつだけ試すなら</h2>
  <div class="card"><p style="margin:0">{e(t['tomorrow'])}</p></div>
  <h2>ちがう風景の人と、一緒に育てるとき</h2><p>{e(t['withOthers'])}</p>
  <h2>となりに置いてみる考え方</h2>
{theories}
  <div class="card" style="margin-top:24px">
    <p><b>自分の風景を知りたい方へ</b></p>
    <p class="note">18問・約3分。お名前もメールアドレスも必要ありません。</p>
    <a class="btn" href="../">診断をはじめる</a>
  </div>
  <h2>ほかの7つの風景</h2>
{others}
  <p style="margin-top:14px"><a href="../types">8つのタイプの一覧を見る</a></p>
  <footer>
    <p>ひだまりこそだち — 子育ての考え方を、親のことばに。<br>
      <a href="https://note.com/hidamari_sodachi" target="_blank" rel="noopener">note</a> ・
      <a href="../../privacy/">プライバシーについて</a> ・ <a href="../">診断</a></p>
    <p style="margin-top:10px">この診断は、教育・発達に関する複数の理論をもとにした読みものです。医療・心理の診断ではありません。
      気がかりが強いときは、地域の子育て支援センターや小児科にご相談ください。</p>
  </footer>
</div>
</body>
</html>
"""


def main() -> None:
    types, order, disc = load_types()
    out = WEB / "matcher/t"
    out.mkdir(parents=True, exist_ok=True)
    for k in order:
        (out / f"{k}.html").write_text(page(types[k], types, order, disc), encoding="utf-8")
    print(f"[OK] web/matcher/t/*.html を生成（{len(order)}件）")

    urls = [f"{SITE}/matcher/", f"{SITE}/matcher/types", f"{SITE}/privacy/"] + \
           [f"{SITE}/matcher/t/{k}" for k in order]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemap.org/schemas/sitemap/0.9">'.replace("sitemap.org", "sitemaps.org")]
    for u in urls:
        sm.append(f"  <url><loc>{u}</loc><changefreq>monthly</changefreq></url>")
    sm.append("</urlset>")
    (WEB / "sitemap.xml").write_text("\n".join(sm) + "\n", encoding="utf-8")
    (WEB / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding="utf-8")
    print(f"[OK] sitemap.xml（{len(urls)} URL）/ robots.txt")


if __name__ == "__main__":
    main()
