#!/usr/bin/env python3
"""note 見出し画像（1280x670）を「絵＋タイトル帯」で作る（検証 NT-1・docs/growth/reach_goal_v1.md）。

従来の文字だけの見出し画像（note_thumbnail.py）と比べて、記事の PV・スキが変わるかを見る。
絵は Gemini（gemini_image.py）で作る。日本語の文字は絵に入れず、PIL で乗せる。

    .venv/bin/python scripts/note_eyecatch_illust.py --scene scene.txt --ref assets/reels/manga_douga/src_2.png \
        --title "動画をやめられない|夕方に" --out assets/thumbnails/xx.png
    # 絵を作り直さず文字だけ直すとき: --image 既存の絵.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemini_image import generate  # noqa: E402

W, H = 1280, 670
FONT = str(Path.home() / ".local/share/fonts/NotoSansCJK-Bold.ttc")
INK, ACCENT = "#3a2a1a", "#b4500f"


def compose(art: Image.Image, lines: list[str], tag: str) -> Image.Image:
    sw, sh = art.size
    k = max(W / sw, H / sh)
    art = art.resize((round(sw * k), round(sh * k)), Image.LANCZOS)
    l, t = (art.width - W) // 2, (art.height - H) // 2
    im = art.crop((l, t, l + W, t + H)).convert("RGBA")

    f = ImageFont.truetype(FONT, 66, index=0)
    ft = ImageFont.truetype(FONT, 30, index=0)
    d0 = ImageDraw.Draw(im)
    tw = max(d0.textlength(x, font=f) for x in lines)
    pad, lh = 44, 88
    bw, bh = int(tw + pad * 2), int(len(lines) * lh + pad * 2 - 10 + 44)
    x0, y0 = 56, H - bh - 48
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 28, fill=(255, 253, 246, 238), outline=(180, 80, 15, 255), width=3)
    im = Image.alpha_composite(im, over)
    d = ImageDraw.Draw(im)
    d.text((x0 + pad, y0 + 22), tag, font=ft, fill=ACCENT)
    for i, ln in enumerate(lines):
        d.text((x0 + pad, y0 + 22 + 44 + i * lh), ln, font=f, fill=INK)
    return im.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True, help="帯の文字。行は | で区切る")
    ap.add_argument("--tag", default="ひだまりこそだち")
    ap.add_argument("--scene", type=Path, help="絵の指示（テキストファイル）")
    ap.add_argument("--ref", action="append", default=[], type=Path)
    ap.add_argument("--image", type=Path, help="作成済みの絵を使う（生成しない）")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    if a.image:
        art = Image.open(a.image).convert("RGB")
    else:
        art = generate(a.scene.read_text(encoding="utf-8"), a.ref, aspect="16:9")
        art.save(a.out.with_suffix(".art.png"))
    compose(art, a.title.split("|"), a.tag).save(a.out)
    print("→", a.out)


if __name__ == "__main__":
    main()
