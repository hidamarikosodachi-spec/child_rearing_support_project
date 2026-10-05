#!/usr/bin/env python3
"""
ひだまりこそだち — note 見出し画像（サムネ）生成スクリプト

CEO決裁(2026-05-18): note記事の顔＝集客資産として方式B（プログラム生成の統一
ブランド・テキストカード）を全話標準化。既存PDFパイプライン資産（weasyprint /
Noto Sans CJK JP / ブランド配色 / ロゴ）を流用。新規課金なし・人手最小。

仕組み: HTML/CSS → weasyprint で PDF 化 → PyMuPDF で正確に 1280x670 PNG 化。
note 推奨アイキャッチ比率（横長 OGP, 1280x670）。

使い方（各回 Claude がコマンド一発で生成）:
  python3 scripts/note_thumbnail.py \
    --title '「抱っこしすぎ」と言われた夜に — アタッチメントという考え方' \
    --series '連載「となりの考え方」 第1回' \
    --out assets/thumbnails/02_series01_bowlby.png

  # シリーズ表記なし（マニフェスト/集客記事など単発）
  python3 scripts/note_thumbnail.py --title 'タイトル' --out assets/thumbnails/xxx.png
"""

import argparse
import os
import re
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_SVG = os.path.join(REPO, "assets", "logo", "mark_v0_a_sun_sprout.svg")

# ブランド配色（PDFパイプラインと同系・陽だまりオレンジ）
C_BG = "#fef3c7"        # 陽だまりクリーム（背景）
C_SUN = "#fbbf24"       # アクセント（日だまりの光）
C_ACCENT = "#c2410c"    # 強アクセント（罫・シリーズ）
C_SUB = "#b45309"       # サブ（ワードマーク）
C_TITLE = "#3a2b1a"     # 本文タイトル（温かいニアブラック）
C_MUTED = "#6b5b4a"     # サブテキスト

W, H = 1280, 670


def title_font_px(title: str) -> int:
    """タイトル長で級数を自動決定（人手最小・決定的）。CJK主体前提。"""
    n = len(title.strip())
    if n <= 16:
        return 76
    if n <= 24:
        return 64
    if n <= 34:
        return 54
    if n <= 46:
        return 46
    return 40


def load_logo_inline() -> str:
    """ロゴSVGを読み、背景クリーム矩形を除去して透過でインライン埋め込み。"""
    with open(LOGO_SVG, "r", encoding="utf-8") as f:
        svg = f.read()
    # XML宣言・コメントを除去（インライン化のため）
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.DOTALL)
    # 背景の不透明クリーム矩形を除去（サムネ背景の上に透過配置）
    svg = re.sub(r'<rect\s+width="512"\s+height="512"\s+fill="#FFFAF0"\s*/>', "", svg)
    return svg.strip()


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_html(title: str, series: str, subtitle: str) -> str:
    logo = load_logo_inline()
    tfs = title_font_px(title.replace('｜', ''))
    title_html = esc(title).replace('｜', '<br>')
    series_html = (
        f'<div class="series">{esc(series)}</div>' if series.strip() else ""
    )
    subtitle_html = (
        f'<div class="subtitle">{esc(subtitle)}</div>' if subtitle.strip() else ""
    )
    # weasyprint は flexbox 未対応のため絶対配置で決定的にレイアウトする。
    # シリーズ有無でタイトル開始位置を切替（縦中央寄せ風）。
    title_top = 250 if series.strip() else 224
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><style>
@page {{ size: {W}px {H}px; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
/* 改行は原稿側で決める（--title に「｜」で指定）。文節の途中で折り返さない */
* {{ word-break: keep-all; overflow-wrap: normal; line-break: strict; }}
html, body {{ width: {W}px; height: {H}px; }}
body {{
  font-family: 'Noto Sans CJK JP', sans-serif;
  background: {C_BG};
  position: relative;
  overflow: hidden;
}}
/* 右上のやわらかな陽だまり（控えめ） */
.sun {{
  position: absolute; top: -170px; right: -170px;
  width: 470px; height: 470px; border-radius: 50%;
  background: {C_SUN}; opacity: 0.18;
}}
.sun2 {{
  position: absolute; top: -30px; right: -30px;
  width: 190px; height: 190px; border-radius: 50%;
  background: {C_SUN}; opacity: 0.22;
}}
.logo {{
  position: absolute; top: 82px; left: 104px;
  width: 108px; height: 108px;
}}
.logo svg {{ width: 100%; height: 100%; display: block; }}
.wordmark {{
  position: absolute; top: 118px; left: 232px;
  font-size: 32px; font-weight: 700; color: {C_SUB};
  letter-spacing: 0.06em;
}}
.series {{
  position: absolute; top: 200px; left: 104px; right: 104px;
  font-size: 27px; font-weight: 700; color: {C_ACCENT};
  letter-spacing: 0.10em;
}}
.title {{
  position: absolute; top: {title_top}px; left: 104px; right: 104px;
  font-size: {tfs}px; font-weight: 700; color: {C_TITLE};
  line-height: 1.55; letter-spacing: 0.01em;
}}
.subtitle {{
  position: absolute; bottom: 150px; left: 104px; right: 104px;
  font-size: 26px; color: {C_MUTED}; line-height: 1.6;
}}
.rule {{
  position: absolute; bottom: 96px; left: 104px;
  width: 760px; height: 2px; background: {C_ACCENT}; opacity: 0.5;
}}
.tag {{
  position: absolute; bottom: 84px; right: 104px;
  font-size: 22px; color: {C_SUB}; letter-spacing: 0.08em;
}}
</style></head>
<body>
  <div class="sun"></div><div class="sun2"></div>
  <div class="logo">{logo}</div>
  <div class="wordmark">ひだまりこそだち</div>
  {series_html}
  <div class="title">{title_html}</div>
  {subtitle_html}
  <div class="rule"></div>
  <div class="tag">子育ての考え方を、親のことばに</div>
</body></html>"""


def render(html: str, out_path: str) -> None:
    import weasyprint  # 既存依存
    import fitz  # PyMuPDF（既存依存）

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        pdf_path = tf.name
    try:
        weasyprint.HTML(string=html, base_url=REPO).write_pdf(pdf_path)
        doc = fitz.open(pdf_path)
        page = doc[0]
        # weasyprint は CSS px を 96dpi で PDF 化 → page幅(pt)から 1280px へ拡大
        zoom = W / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        pix.save(out_path)
        doc.close()
        print(f"[OK] {out_path}  ({pix.width}x{pix.height}px)")
        if (pix.width, pix.height) != (W, H):
            print(
                f"[WARN] 期待サイズ {W}x{H} と不一致。CSS @page と zoom を確認。",
                file=sys.stderr,
            )
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)


def main():
    ap = argparse.ArgumentParser(description="note 見出し画像生成（ひだまりこそだち）")
    ap.add_argument("--title", required=True, help="記事タイトル（必須）")
    ap.add_argument("--series", default="", help="連載/シリーズ表記（任意）")
    ap.add_argument("--subtitle", default="", help="補助一行（任意・通常は空）")
    ap.add_argument("--out", required=True, help="出力PNGパス")
    args = ap.parse_args()
    html = build_html(args.title, args.series, args.subtitle)
    render(html, args.out)


if __name__ == "__main__":
    main()
