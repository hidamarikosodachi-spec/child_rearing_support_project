#!/usr/bin/env python3
"""Instagram ストーリー用 告知画像（1080x1920）を生成する — note 記事の宣伝用。

note_thumbnail.py と同じブランド（ひだまりクリーム／陽だまり／Noto Sans CJK JP）と
同じ描画パイプライン（HTML/CSS → weasyprint → PyMuPDF）。
上下 各250px は Instagram の UI（プロフィール帯・返信欄）に隠れるので安全域に寄せる。
中央下の空白は、投稿時に**リンクスタッカー**を貼る場所（API では貼れない＝手動）。

使い方:
    python3 scripts/instagram_story.py --article docs/note/articles/05_series04_nvc.md
    python3 scripts/instagram_story.py --title '…' --series '連載「となりの考え方」 第4回' --hook '…' --out assets/stories/xxx.png
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from note_thumbnail import (  # noqa: E402
    C_ACCENT, C_BG, C_MUTED, C_SUB, C_SUN, C_TITLE, REPO, esc, load_logo_inline,
)

W, H = 1080, 1920


def title_font_px(title: str) -> int:
    n = len(title)
    if n <= 18:
        return 76
    if n <= 26:
        return 66
    if n <= 36:
        return 58
    return 50


def build_html(title: str, series: str, hook: str, cta: str) -> str:
    logo = load_logo_inline()
    tfs = title_font_px(title)
    series_html = f'<div class="series">{esc(series)}</div>' if series.strip() else ""
    hook_html = f'<div class="hook">{esc(hook)}</div>' if hook.strip() else ""
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><style>
@page {{ size: {W}px {H}px; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; }}
body {{ font-family: 'Noto Sans CJK JP', sans-serif; background: {C_BG}; position: relative; overflow: hidden; }}
.sun  {{ position: absolute; top: -260px; right: -260px; width: 760px; height: 760px; border-radius: 50%; background: {C_SUN}; opacity: 0.18; }}
.sun2 {{ position: absolute; top: -40px;  right: -40px;  width: 300px; height: 300px; border-radius: 50%; background: {C_SUN}; opacity: 0.22; }}
.logo {{ position: absolute; top: 300px; left: 96px; width: 120px; height: 120px; }}
.logo svg {{ width: 100%; height: 100%; display: block; }}
.wordmark {{ position: absolute; top: 340px; left: 236px; font-size: 38px; font-weight: 700; color: {C_SUB}; letter-spacing: 0.06em; }}
.label {{ position: absolute; top: 520px; left: 96px; font-size: 30px; color: {C_MUTED}; letter-spacing: 0.12em; }}
.series {{ position: absolute; top: 580px; left: 96px; right: 96px; font-size: 32px; font-weight: 700; color: {C_ACCENT}; letter-spacing: 0.10em; }}
.title {{ position: absolute; top: 660px; left: 96px; right: 96px; font-size: {tfs}px; font-weight: 700; color: {C_TITLE}; line-height: 1.5; letter-spacing: 0.01em; }}
.hook {{ position: absolute; top: 1040px; left: 96px; right: 96px; font-size: 34px; color: {C_MUTED}; line-height: 1.75; }}
.cta {{ position: absolute; top: 1330px; left: 96px; right: 96px; font-size: 32px; font-weight: 700; color: {C_ACCENT}; letter-spacing: 0.06em; text-align: center; }}
.cta-sub {{ position: absolute; top: 1385px; left: 96px; right: 96px; font-size: 24px; color: {C_MUTED}; text-align: center; letter-spacing: 0.04em; }}
.rule {{ position: absolute; top: 1560px; left: 96px; width: 640px; height: 2px; background: {C_ACCENT}; opacity: 0.5; }}
.tag {{ position: absolute; top: 1580px; right: 96px; font-size: 26px; color: {C_SUB}; letter-spacing: 0.08em; }}
</style></head>
<body>
  <div class="sun"></div><div class="sun2"></div>
  <div class="logo">{logo}</div>
  <div class="wordmark">ひだまりこそだち</div>
  <div class="label">note 新しい記事</div>
  {series_html}
  <div class="title">{esc(title)}</div>
  {hook_html}
  <div class="cta">{esc(cta)}</div>
  <div class="cta-sub">（この下のリンクから読めます）</div>
  <div class="rule"></div>
  <div class="tag">子育ての考え方を、親のことばに</div>
</body></html>"""


def render(html: str, out_path: str) -> None:
    import tempfile
    import weasyprint
    import fitz

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        pdf_path = tf.name
    try:
        weasyprint.HTML(string=html, base_url=REPO).write_pdf(pdf_path)
        doc = fitz.open(pdf_path)
        page = doc[0]
        zoom = W / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        pix.save(out_path)
        doc.close()
        print(f"[OK] {out_path}  ({pix.width}x{pix.height}px)")
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def from_article(path: str) -> dict:
    """記事 md の front-matter と冒頭引用から title/series/hook/out を組み立てる。"""
    txt = open(path, encoding="utf-8").read()
    fm = txt.split("---", 2)[1]
    g = lambda k: (re.search(rf'^{k}: "?(.+?)"?$', fm, re.M) or [None, ""])[1]  # noqa: E731
    body = txt.split("## 記事本文（ここから下を note へ）", 1)[1]
    title = re.search(r"^# (.+)$", body, re.M).group(1).strip()
    lead = re.search(r"^> (.+)$", body, re.M)
    hook = lead.group(1).strip() if lead else ""
    # 文字数を抑える（冒頭2文まで）
    hook = "".join(re.findall(r"[^。]*。", hook)[:2]) or hook
    series_no = g("series_no")
    series = f"連載「となりの考え方」 第{series_no}回" if series_no else ""
    slug = g("slug")
    return {"title": title, "series": series, "hook": hook,
            "out": os.path.join(REPO, "assets", "stories", f"{slug}.png")}


def main():
    ap = argparse.ArgumentParser(description="Instagram ストーリー告知画像（1080x1920）")
    ap.add_argument("--article", help="記事 md（title/series/hook/out を自動抽出）")
    ap.add_argument("--title"); ap.add_argument("--series", default="")
    ap.add_argument("--hook", default=""); ap.add_argument("--out")
    ap.add_argument("--cta", default="note で公開しました")
    a = ap.parse_args()
    if a.article:
        d = from_article(a.article)
        title, series, hook, out = a.title or d["title"], a.series or d["series"], a.hook or d["hook"], a.out or d["out"]
    else:
        if not (a.title and a.out):
            ap.error("--article か --title/--out が必要")
        title, series, hook, out = a.title, a.series, a.hook, a.out
    render(build_html(title, series, hook, a.cta), out)


if __name__ == "__main__":
    main()
