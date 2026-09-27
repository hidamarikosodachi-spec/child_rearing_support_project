#!/usr/bin/env python3
"""
ひだまりこそだち — Instagram 声かけカルーセル画像生成スクリプト

CEO決裁(2026-06-16): Instagram 週2運用（声かけカルーセル週2＋絵本リール週1）。
カルーセルは note サムネと同じブランド資産（weasyprint / Noto Sans CJK JP /
陽だまり配色 / ロゴ）を流用し、統一世界観で量産する。新規課金なし・人手最小。

仕組み: ドラフト md の「## スライド本文」を読み、各スライドを HTML/CSS →
weasyprint → PDF → PyMuPDF で 1080x1350(4:5) PNG 化。Instagram カルーセル用。

スライドのレイアウトは本文から自動判定:
  - ラベルに「表紙」を含む           → cover（大見出し＋小見出し）
  - 本文に「↓」を含む                → swap（つい言う言葉 → 言い換え＋補足）
  - それ以外                          → text（情景・まとめ・note誘導）

使い方:
  python3 scripts/instagram_carousel.py --draft docs/drafts/instagram/2026-06-18.md
  # 出力: assets/instagram/2026-06-18/slide_01.png ... slide_05.png
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile

import frontmatter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_SVG = os.path.join(REPO, "assets", "logo", "mark_v0_a_sun_sprout.svg")

# ブランド配色（note サムネ／PDF パイプラインと同系・陽だまりオレンジ）
C_BG = "#fef3c7"        # 陽だまりクリーム（背景）
C_SUN = "#fbbf24"       # アクセント（日だまりの光）
C_ACCENT = "#c2410c"    # 強アクセント（言い換え・罫）
C_SUB = "#b45309"       # サブ（ワードマーク）
C_TITLE = "#3a2b1a"     # 見出し（温かいニアブラック）
C_MUTED = "#6b5b4a"     # サブテキスト・つい言う言葉

W, H = 1080, 1350  # Instagram 4:5 ポートレート


def load_logo_inline() -> str:
    """ロゴSVGを読み、背景クリーム矩形を除去して透過でインライン埋め込み。"""
    with open(LOGO_SVG, "r", encoding="utf-8") as f:
        svg = f.read()
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)
    svg = re.sub(r'<rect\s+width="512"\s+height="512"\s+fill="#FFFAF0"\s*/>', "", svg)
    return svg.strip()


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_slides(md_body: str) -> list[dict]:
    """「## スライド本文」セクションを slide dict のリストに分解。

    各 slide = {"label": str, "lines": [str, ...]}。
    `**N枚目（ラベル）**` をスライド区切りとして扱う。
    """
    # スライド本文セクションを抽出（次の "## " 見出しまで）
    m = re.search(r"##\s*スライド本文\s*\n(.*?)(?:\n##\s|\Z)", md_body, re.DOTALL)
    section = m.group(1) if m else md_body
    slides: list[dict] = []
    cur: dict | None = None
    marker = re.compile(r"^\*\*\s*\d+\s*枚目\s*[（(]?\s*(.*?)\s*[）)]?\s*\*\*\s*$")
    for raw in section.splitlines():
        line = raw.rstrip()
        mk = marker.match(line.strip())
        if mk:
            if cur:
                slides.append(cur)
            cur = {"label": mk.group(1) or "", "lines": []}
            continue
        if cur is None:
            continue
        if line.strip():
            cur["lines"].append(line.strip())
    if cur:
        slides.append(cur)
    return slides


def _frame(inner_html: str, page_no: int, total: int) -> str:
    """全スライド共通の枠（背景・陽だまり・ロゴ・タグライン・ページ番号）。"""
    logo = load_logo_inline()
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><style>
@page {{ size: {W}px {H}px; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; }}
/* 日本語は既定だと単語の途中でも折り返す。keep-all で禁止し、改行は原稿側で決める
   （オーナー指示 2026-09-27「文末から読んで1行で読めるように」） */
* {{ word-break: keep-all; overflow-wrap: normal; line-break: strict; }}
body {{ font-family: 'Noto Sans CJK JP', sans-serif; background: {C_BG};
  position: relative; overflow: hidden; }}
.sun  {{ position: absolute; top: -210px; right: -210px; width: 540px; height: 540px;
  border-radius: 50%; background: {C_SUN}; opacity: 0.16; }}
.sun2 {{ position: absolute; top: -40px; right: -40px; width: 230px; height: 230px;
  border-radius: 50%; background: {C_SUN}; opacity: 0.20; }}
.logo {{ position: absolute; top: 70px; left: 80px; width: 92px; height: 92px; }}
.logo svg {{ width: 100%; height: 100%; display: block; }}
.wordmark {{ position: absolute; top: 100px; left: 188px; font-size: 30px;
  font-weight: 700; color: {C_SUB}; letter-spacing: 0.06em; }}
/* 中央コンテンツ（縦中央寄せ：weasyprint は table で実現） */
.center {{ position: absolute; left: 80px; width: {W - 160}px;
  top: 50%; transform: translateY(-50%); text-align: center; }}
.cover-title {{ font-size: 64px; font-weight: 700; color: {C_TITLE};
  line-height: 1.5; letter-spacing: 0.01em; }}
.cover-sub {{ margin-top: 36px; font-size: 30px; color: {C_ACCENT};
  letter-spacing: 0.08em; font-weight: 700; }}
.pill {{ display: inline-block; font-size: 24px; font-weight: 700;
  letter-spacing: 0.10em; padding: 6px 22px; border-radius: 999px; }}
.pill-tsui {{ color: {C_MUTED}; background: rgba(107,91,74,0.10); }}
.pill-iikae {{ color: #fff; background: {C_ACCENT}; }}
.before {{ margin-top: 22px; font-size: 46px; color: {C_MUTED};
  line-height: 1.5; font-weight: 700; }}
.arrow {{ margin: 26px 0; font-size: 52px; color: {C_ACCENT}; font-weight: 700; }}
.after {{ font-size: 50px; color: {C_ACCENT}; line-height: 1.5; font-weight: 700; }}
.note {{ margin-top: 26px; font-size: 28px; color: {C_MUTED}; line-height: 1.6; }}
.text {{ font-size: 42px; color: {C_TITLE}; line-height: 1.7; font-weight: 700; }}
.nudge {{ margin-top: 40px; font-size: 32px; color: {C_ACCENT};
  line-height: 1.6; font-weight: 700; }}
.rule {{ position: absolute; bottom: 138px; left: 80px; width: 520px; height: 2px;
  background: {C_ACCENT}; opacity: 0.45; }}
.tag {{ position: absolute; bottom: 120px; left: 80px; font-size: 24px;
  color: {C_SUB}; letter-spacing: 0.06em; }}
.pageno {{ position: absolute; bottom: 120px; right: 80px; font-size: 24px;
  color: {C_SUB}; letter-spacing: 0.10em; }}
</style></head>
<body>
  <div class="sun"></div><div class="sun2"></div>
  <div class="logo">{logo}</div>
  <div class="wordmark">ひだまりこそだち</div>
  <div class="center">{inner_html}</div>
  <div class="rule"></div>
  <div class="tag">子育ての考え方を、親のことばに</div>
  <div class="pageno">{page_no} / {total}</div>
</body></html>"""


def _is_sub(line: str) -> bool:
    return line.startswith("—") or line.startswith("ー") or line.startswith("─")


def build_inner(slide: dict) -> str:
    """スライド種別を自動判定して内側 HTML を組む。"""
    label = slide["label"]
    lines = slide["lines"]

    # cover: 表紙ラベル
    if "表紙" in label:
        title = [esc(x) for x in lines if not _is_sub(x)]
        sub = [esc(x) for x in lines if _is_sub(x)]
        html = f'<div class="cover-title">{"<br>".join(title)}</div>'
        if sub:
            html += f'<div class="cover-sub">{"<br>".join(sub)}</div>'
        return html

    # swap: 「↓」を含む（つい言う言葉 → 言い換え）
    if any(l.strip() in ("↓", "⬇", "⇩") for l in lines):
        i = next(idx for idx, l in enumerate(lines) if l.strip() in ("↓", "⬇", "⇩"))
        before = [esc(x) for x in lines[:i]]
        rest = lines[i + 1:]
        note = [esc(x) for x in rest if x.startswith("（") or x.startswith("(")]
        after = [esc(x) for x in rest if not (x.startswith("（") or x.startswith("("))]
        html = (
            f'<div class="pill pill-tsui">つい</div>'
            f'<div class="before">{"<br>".join(before)}</div>'
            f'<div class="arrow">↓</div>'
            f'<div class="pill pill-iikae">こう言い換える</div>'
            f'<div class="after">{"<br>".join(after)}</div>'
        )
        if note:
            html += f'<div class="note">{"<br>".join(note)}</div>'
        return html

    # text: 情景・まとめ・note誘導
    main = [esc(x) for x in lines if not x.startswith("→")]
    nudge = [esc(x.lstrip("→ ").strip()) for x in lines if x.startswith("→")]
    html = f'<div class="text">{"<br>".join(main)}</div>'
    if nudge:
        html += f'<div class="nudge">→ {"<br>".join(nudge)}</div>'
    return html


def render_html_to_png(html: str, out_path: str) -> tuple[int, int]:
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
        return pix.width, pix.height
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def main():
    ap = argparse.ArgumentParser(description="Instagram 声かけカルーセル画像生成")
    ap.add_argument("--draft", required=True, help="カルーセルドラフト md のパス")
    ap.add_argument("--outdir", default="", help="出力ディレクトリ（既定: assets/instagram/<date>）")
    args = ap.parse_args()

    post = frontmatter.load(args.draft)
    date = str(post.get("date", "")) or os.path.splitext(os.path.basename(args.draft))[0]
    slides = parse_slides(post.content)
    if not slides:
        print("[ERROR] スライドが見つかりません（「## スライド本文」と **N枚目** 区切りを確認）", file=sys.stderr)
        sys.exit(1)

    outdir = args.outdir or os.path.join(REPO, "assets", "instagram", date)
    total = len(slides)
    print(f"=== カルーセル生成: {total}枚 (date={date}) → {outdir} ===")
    for n, slide in enumerate(slides, 1):
        inner = build_inner(slide)
        html = _frame(inner, n, total)
        out = os.path.join(outdir, f"slide_{n:02d}.png")
        w, h = render_html_to_png(html, out)
        flag = "" if (w, h) == (W, H) else f"  [WARN] 期待{W}x{H}と不一致"
        print(f"[OK] slide_{n:02d}.png ({w}x{h}) — {slide['label'] or 'text'}{flag}")
    print(f"\n完了: {total}枚 → {outdir}")


if __name__ == "__main__":
    main()
