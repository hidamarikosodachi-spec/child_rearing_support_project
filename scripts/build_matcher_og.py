#!/usr/bin/env python3
"""タイプ別の OGP 画像（1200x630）を生成する。SNS 共有時のプレビュー用。

note_thumbnail.py と同じブランド・同じ描画パイプライン（HTML/CSS → weasyprint → PyMuPDF）。
出力: web/og/type_<key>.png（＋ web/og/matcher.png = 診断トップ用）

    .venv/bin/python scripts/build_matcher_og.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from note_thumbnail import (  # noqa: E402
    C_ACCENT, C_BG, C_MUTED, C_SUB, C_SUN, C_TITLE, REPO, esc, load_logo_inline,
)

W, H = 1200, 630
OUT = Path(REPO) / "web/og"
TYPES_JS = Path(REPO) / "web/matcher/types.js"


def load_types() -> dict:
    """自動生成された types.js から JSON 部分を取り出す（正本は type_results_v1.md）。"""
    src = TYPES_JS.read_text(encoding="utf-8")
    body = src.split("export const TYPES = ", 1)[1].split("\n};", 1)[0] + "\n}"
    order = json.loads(re.search(r"export const TYPE_ORDER = (\[.*?\]);", src, re.S).group(1))
    # JS オブジェクトのキーは引用符なし → JSON に直す
    body = re.sub(r"^(\s*)([a-zA-Z_]\w*):", r'\1"\2":', body, flags=re.M)
    return json.loads(body), order


def build_html(label: str, lead: str, axes: str) -> str:
    logo = load_logo_inline()
    fs = 96 if len(label) <= 5 else 80
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>
@page {{ size: {W}px {H}px; margin: 0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:{W}px; height:{H}px; }}
body {{ font-family:'Noto Sans CJK JP',sans-serif; background:{C_BG}; position:relative; overflow:hidden; }}
.sun  {{ position:absolute; top:-200px; right:-200px; width:560px; height:560px; border-radius:50%; background:{C_SUN}; opacity:.18; }}
.sun2 {{ position:absolute; top:-30px;  right:-30px;  width:210px; height:210px; border-radius:50%; background:{C_SUN}; opacity:.22; }}
.logo {{ position:absolute; top:60px; left:80px; width:84px; height:84px; }}
.logo svg {{ width:100%; height:100%; display:block; }}
.wordmark {{ position:absolute; top:86px; left:184px; font-size:30px; font-weight:700; color:{C_SUB}; letter-spacing:.06em; }}
.kicker {{ position:absolute; top:212px; left:80px; font-size:26px; color:{C_MUTED}; letter-spacing:.12em; }}
.name {{ position:absolute; top:256px; left:80px; right:80px; font-size:{fs}px; font-weight:700; color:{C_TITLE}; letter-spacing:.04em; }}
.axes {{ position:absolute; top:{256+fs+26}px; left:80px; font-size:28px; font-weight:700; color:{C_ACCENT}; letter-spacing:.08em; }}
.lead {{ position:absolute; bottom:104px; left:80px; right:80px; font-size:30px; color:{C_MUTED}; line-height:1.6; }}
.rule {{ position:absolute; bottom:70px; left:80px; width:560px; height:2px; background:{C_ACCENT}; opacity:.5; }}
.tag {{ position:absolute; bottom:58px; right:80px; font-size:22px; color:{C_SUB}; letter-spacing:.08em; }}
</style></head><body>
<div class="sun"></div><div class="sun2"></div>
<div class="logo">{logo}</div><div class="wordmark">ひだまりこそだち</div>
<div class="kicker">わが家のこそだちタイプ</div>
<div class="name">{esc(label)}</div>
<div class="axes">{esc(axes)}</div>
<div class="lead">{esc(lead)}</div>
<div class="rule"></div><div class="tag">子育ての考え方を、親のことばに</div>
</body></html>"""


def render(html: str, out: Path) -> None:
    import weasyprint
    import fitz

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        pdf = tf.name
    try:
        weasyprint.HTML(string=html, base_url=REPO).write_pdf(pdf)
        doc = fitz.open(pdf)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(W / page.rect.width, W / page.rect.width), alpha=False)
        out.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out))
        doc.close()
        print(f"[OK] {out.relative_to(Path(REPO))} ({pix.width}x{pix.height})")
    finally:
        if os.path.exists(pdf):
            os.remove(pdf)


def main() -> None:
    types, order = load_types()
    for k in order:
        t = types[k]
        render(build_html(t["label"], t["lead"], t["axes"]), OUT / f"type_{k}.png")
    render(build_html("8つのこそだちタイプ", "18問・約3分。正解も順位もありません。", "導く/委ねる・整える/流れる・寄り添う/見守る"),
           OUT / "matcher.png")


if __name__ == "__main__":
    main()
