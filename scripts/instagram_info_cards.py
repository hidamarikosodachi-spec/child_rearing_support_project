#!/usr/bin/env python3
"""情報カルーセル用の画像（1080x1350）。見出し＋項目（日時/場所/対象/料金/申込）の表形式で作る。

    .venv/bin/python scripts/instagram_info_cards.py --spec docs/instagram/info_cards/20261111_oidekake.json --outdir assets/instagram/2026-11-11

spec: {"cover": {"title": [..], "sub": ".."}, "cards": [{"chip": "大阪", "title": [..], "rows": [["日時","..."],...], "note": ".."}], "last": {"lines": [..]}}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = str(Path.home() / ".local/share/fonts/NotoSansCJK-Bold.ttc")
W, H = 1080, 1350
BG, INK, ACC, SUB, LINE = (253, 241, 196), (61, 43, 31), (190, 82, 18), (120, 92, 60), (232, 200, 140)
CHIP = {"大阪": (214, 96, 40), "東京": (52, 110, 150)}


def f(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size, index=0)


def base(n: int, total: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.ellipse((760, -220, 1300, 320), fill=(252, 228, 150))
    d.ellipse((900, -150, 1240, 190), fill=(250, 218, 120))
    d.text((60, 56), "ひだまりこそだち", font=f(30), fill=ACC)
    d.text((W - 60, H - 70), f"{n} / {total}", font=f(26), fill=SUB, anchor="ra")
    d.text((60, H - 70), "子育ての考え方を、親のことばに", font=f(24), fill=SUB)
    return im, d


def wrap(d: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    out: list[str] = []
    for part in text.split("\n"):   # 明示の改行を優先（単語の途中で折らないため）
        cur = ""
        for ch in part:
            if d.textlength(cur + ch, font=font) > width:
                out.append(cur)
                cur = ch
            else:
                cur += ch
        out.append(cur)
    return out


def cover(spec: dict, total: int) -> Image.Image:
    im, d = base(1, total)
    y = 430
    for line in spec["title"]:
        d.text((W // 2, y), line, font=f(84), fill=INK, anchor="ma")
        y += 120
    d.line((W // 2 - 80, y + 20, W // 2 + 80, y + 20), fill=ACC, width=5)
    d.text((W // 2, y + 70), spec["sub"], font=f(44), fill=ACC, anchor="ma")
    return im


def card(c: dict, n: int, total: int) -> Image.Image:
    im, d = base(n, total)
    chip = c["chip"]
    cw = int(d.textlength(chip, font=f(36))) + 56
    d.rounded_rectangle((60, 150, 60 + cw, 214), 32, fill=CHIP.get(chip[:2], ACC))
    d.text((60 + cw // 2, 182), chip, font=f(36), fill="white", anchor="mm")
    y = 250
    for line in c["title"]:
        d.text((60, y), line, font=f(62), fill=INK)
        y += 86
    y += 24
    d.line((60, y, W - 60, y), fill=LINE, width=4)
    y += 36
    for label, val in c["rows"]:
        d.text((60, y + 6), label, font=f(32), fill=ACC)
        lines = wrap(d, val, f(42), W - 60 - 230)
        for i, ln in enumerate(lines):
            d.text((230, y + i * 58), ln, font=f(42), fill=INK)
        y += max(1, len(lines)) * 58 + 30
    if c.get("note"):
        d.rounded_rectangle((60, y + 10, W - 60, y + 10 + 20 + 46 * len(wrap(d, c["note"], f(34), W - 160)) + 20), 18, fill=(255, 250, 225), outline=LINE, width=3)
        yy = y + 30
        for ln in wrap(d, c["note"], f(34), W - 160):
            d.text((90, yy), ln, font=f(34), fill=SUB)
            yy += 46
    return im


def last(spec: dict, n: int, total: int) -> Image.Image:
    im, d = base(n, total)
    y = 380
    for i, ln in enumerate(spec["lines"]):
        font = f(54) if i < 2 else f(36)
        for w in wrap(d, ln, font, W - 140):
            d.text((W // 2, y), w, font=font, fill=INK if i < 2 else SUB, anchor="ma")
            y += int(font.size * 1.5)
        y += 20
    return im


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    a = ap.parse_args()
    s = json.loads(a.spec.read_text(encoding="utf-8"))
    total = 2 + len(s["cards"])
    a.outdir.mkdir(parents=True, exist_ok=True)
    cover(s["cover"], total).save(a.outdir / "slide_01.png")
    for i, c in enumerate(s["cards"], 2):
        card(c, i, total).save(a.outdir / f"slide_{i:02d}.png")
    last(s["last"], total, total).save(a.outdir / f"slide_{total:02d}.png")
    print("完了:", total, "枚 →", a.outdir)


if __name__ == "__main__":
    main()
