#!/usr/bin/env python3
"""Gemini で漫画リール用のコマ絵を作る（参照画像で同じ親子の顔にそろえる）。

    .venv/bin/python scripts/gemini_image.py --prompt-file p.txt --ref assets/reels/manga_douga/src_2.png --out out.png

- 参照画像（--ref・複数可）を渡して「同じ母親と子ども」を保つ。
- 出力は 1080x1920 に整える（9:16）。文字・吹き出しは絵に入れない（reel_manga.py で乗せる）。
- キーは .env の GEMINI_API_KEY（値は表示しない）。
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gemini-3.1-flash-image"


def key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        sys.exit("GEMINI_API_KEY が .env にありません")
    return k


def generate(prompt: str, refs: list[Path], model: str = MODEL, aspect: str = "9:16") -> Image.Image:
    parts: list[dict] = []
    for r in refs:
        parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(r.read_bytes()).decode()}})
    parts.append({"text": prompt})
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key()},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:400]}")
    for c in d.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            blob = p.get("inlineData") or p.get("inline_data")
            if blob:
                return Image.open(io.BytesIO(base64.b64decode(blob["data"]))).convert("RGB")
    sys.exit("画像が返りませんでした: " + json.dumps(d, ensure_ascii=False)[:400])


def fit_9x16(im: Image.Image, w: int = 1080, h: int = 1920) -> Image.Image:
    sw, sh = im.size
    scale = max(w / sw, h / sh)
    im = im.resize((round(sw * scale), round(sh * scale)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((l, t, l + w, t + h))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file", required=True, type=Path)
    ap.add_argument("--ref", action="append", default=[], type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    im = generate(a.prompt_file.read_text(encoding="utf-8"), a.ref, a.model)
    print("raw", im.size)
    fit_9x16(im).save(a.out)
    print("→", a.out)


if __name__ == "__main__":
    main()
