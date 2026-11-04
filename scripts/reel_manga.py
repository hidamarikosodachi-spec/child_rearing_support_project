#!/usr/bin/env python3
"""漫画リール：コマ画像（ChatGPT で作った絵）＋ナレーション・吹き出し → 1080x1920 動画。

2026-11-04 の調査（docs/instagram/reel_research_v2.md）で、文字だけのスライドは
平均視聴 0.8〜3.3秒で離脱されていた。絵で止めて、文字はこちらで正しく乗せる。

  - 絵はオーナーが ChatGPT で作る（費用をかけない・docs/instagram/manga_prompts_v1.md）。
    AI は日本語の文字を崩すので、絵には文字を入れさせない。
  - 改行は原稿側で手で決める（1行で読める位置で折る）。ここでは折り返さない。
  - ズームは使わない（文字がにじむ）。切替は reel_from_slides と同じフェード。

    .venv/bin/python scripts/reel_manga.py --script docs/instagram/reels/<slug>.md [--frames-only]

原稿の front-matter に frames（下の形）を書く。座標はコマ画像に対する割合（0〜1）。
  frames:
    - image: src_2.png          # 原稿 front-matter の image_dir からの相対。無ければ文字だけのカード
      sec: 3.0
      title: [行, 行]            # 大きい見出し（冒頭のつかみ）
      narration: [行, 行]        # 上のナレーション箱
      bubble: {lines: [行], x: 0.78, y: 0.38, tail: [0.80, 0.52]}
      rows: [[ラベル, 値], ...]   # カード：数字の表
      foot: [行]                 # カード：下の一言
      nudge: [行]                # カード：誘導（アクセント色）
出力: assets/reels/<slug>.mp4 ＋ assets/reels/<slug>/frame_NN.png
"""
from __future__ import annotations

import argparse
import os
import sys

import frontmatter
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import instagram_carousel as cz  # noqa: E402  配色を共有する
from reel_from_slides import W, H, encode  # noqa: E402

REPO = cz.REPO
FONT = os.path.expanduser("~/.local/share/fonts/NotoSansCJK-Bold.ttc")  # index 0 = JP


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size, index=0)


def text_block(d: ImageDraw.ImageDraw, lines: list[str], f, cx: int, top: int, fill, gap: float = 1.5) -> int:
    """中央揃えで行を描き、下端の y を返す。"""
    lh = int(f.size * gap)
    for i, line in enumerate(lines):
        w = d.textlength(line, font=f)
        d.text((cx - w / 2, top + i * lh), line, font=f, fill=fill)
    return top + len(lines) * lh


def box(d, lines, f, top, fill_bg="#fffdf6", fg=cz.C_TITLE, pad=36, gap=1.5):
    lh = int(f.size * gap)
    w = max(d.textlength(l, font=f) for l in lines) + pad * 2
    h = lh * len(lines) + pad * 2 - (lh - f.size)
    x0 = (W - w) / 2
    d.rounded_rectangle((x0, top, x0 + w, top + h), radius=28, fill=fill_bg, outline=cz.C_SUB, width=4)
    text_block(d, lines, f, W // 2, top + pad - 4, fg, gap)
    return top + h


def bubble(d, spec):
    f = font(54)
    lines = spec["lines"]
    lh = int(f.size * 1.4)
    tw = max(d.textlength(l, font=f) for l in lines)
    w, h = tw + 80, lh * len(lines) + 56
    cx, cy = spec["x"] * W, spec["y"] * H
    x0, y0 = min(max(cx - w / 2, 30), W - 30 - w), cy - h / 2
    tx, ty = spec["tail"][0] * W, spec["tail"][1] * H
    base = (min(max(tx, x0 + 60), x0 + w - 60), y0 + h - 4)
    d.polygon([(base[0] - 30, base[1]), (base[0] + 30, base[1]), (tx, ty)], fill="white", outline=cz.C_TITLE)
    d.ellipse((x0, y0, x0 + w, y0 + h), fill="white", outline=cz.C_TITLE, width=5)
    d.polygon([(base[0] - 26, base[1] - 8), (base[0] + 26, base[1] - 8), (tx, ty - 10)], fill="white")
    text_block(d, lines, f, x0 + w / 2, y0 + 28, cz.C_TITLE, 1.4)


def render(fr: dict, image_dir: str) -> Image.Image:
    if fr.get("image"):
        im = Image.open(os.path.join(image_dir, fr["image"])).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        im = Image.new("RGB", (W, H), cz.C_BG)
    d = ImageDraw.Draw(im)
    y = 230  # 上の UI（アカウント名）を避ける
    if fr.get("title"):
        y = box(d, fr["title"], font(76), y, gap=1.45) + 30
    if fr.get("narration"):
        y = box(d, fr["narration"], font(54), y) + 30
    if fr.get("bubble"):
        bubble(d, fr["bubble"])
    if fr.get("rows"):  # 数字の表（カード）
        f, fv = font(50), font(64)
        y += 40
        for label, val in fr["rows"]:
            hi = val == fr.get("highlight")
            d.text((150, y + 8), label, font=f, fill=cz.C_ACCENT if hi else cz.C_TITLE)
            vw = d.textlength(val, font=fv)
            d.text((W - 150 - vw, y), val, font=fv, fill=cz.C_ACCENT if hi else cz.C_TITLE)
            y += 120
            d.line((150, y - 20, W - 150, y - 20), fill=cz.C_MUTED, width=2)
        y += 40
    if fr.get("foot"):
        y = text_block(d, fr["foot"], font(56), W // 2, y + 20, cz.C_TITLE, 1.6) + 20
    if fr.get("nudge"):
        text_block(d, fr["nudge"], font(46), W // 2, max(y + 60, 1180), cz.C_ACCENT, 1.6)
    if fr.get("small"):
        text_block(d, fr["small"], font(32), W // 2, 1420, cz.C_MUTED, 1.5)
    return im


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True)
    ap.add_argument("--frames-only", action="store_true")
    a = ap.parse_args()
    post = frontmatter.load(a.script)
    slug = post["slug"]
    image_dir = os.path.join(REPO, post["image_dir"])
    out_dir = os.path.join(REPO, "assets", "reels", slug)
    os.makedirs(out_dir, exist_ok=True)
    pngs, durs = [], []
    for i, fr in enumerate(post["frames"], 1):
        p = os.path.join(out_dir, f"frame_{i:02d}.png")
        render(fr, image_dir).save(p)
        pngs.append(p)
        durs.append(float(fr.get("sec", 3.0)))
    print(f"{len(pngs)} 枚 → {out_dir}")
    if a.frames_only:
        return
    out = os.path.join(REPO, "assets", "reels", f"{slug}.mp4")
    encode(pngs, durs, out)
    print(f"→ {out}（{sum(durs) - 0.4 * (len(durs) - 1):.1f}秒）")


if __name__ == "__main__":
    main()
