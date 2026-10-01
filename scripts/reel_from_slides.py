#!/usr/bin/env python3
"""スライド原稿（md） → Instagram リール動画（1080x1920）。

オーナー指示（2026-10-01）:
  「カルーセル投稿をリールで1秒ごとに切り替わるなどでも良いです」
  → カルーセルと同じ原稿・同じブランド資産を使い、**リールとして**出す。

なぜこの方式か:
  既存の絵本リール（scripts/reel_node/render_full.js）は1本ごとに JS を手書きしており
  量産できない。一方カルーセルは md から画像を生成できるので、それを縦9:16で描き直して
  動画に並べれば、週次で回せる。

切替の速さ:
  1秒は日本語を読むには速すぎるため、**文字数に応じて 1.8〜4.5秒で可変**。
  切替は軽いフェード（0.4秒）、BGM は既存の自作トラック（scripts/reel_node/bgm.wav）。

    .venv/bin/python scripts/reel_from_slides.py --script docs/instagram/reel03_douga_yamerarenai.md
    # 画像だけ作って確認（動画にしない）
    ... --script <md> --frames-only

出力: assets/reels/<slug>.mp4 ＋ assets/reels/<slug>/slide_NN.png
投稿は scripts/post_instagram_reel.py（公開URLが必要なので web/ig/reels/ に置いてデプロイ）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import frontmatter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import instagram_carousel as cz  # noqa: E402  レイアウト・配色・描画を共有する

REPO = cz.REPO
W, H = 1080, 1920          # リール（9:16）
FPS = 30
FADE = 0.4                 # 切替のフェード（秒）
MIN_SEC, MAX_SEC = 1.8, 4.0
BGM = os.path.join(REPO, "scripts", "reel_node", "bgm.wav")


def frame_html(inner_html: str) -> str:
    """リール用の枠。Instagram の UI に隠れる上下は空けておく（上250px・下420px）。"""
    logo = cz.load_logo_inline()
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><style>
@page {{ size: {W}px {H}px; margin: 0; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; }}
/* 日本語を単語の途中で折り返さない（改行は原稿側で決める・オーナー指示 2026-09-27） */
* {{ word-break: keep-all; overflow-wrap: normal; line-break: strict; }}
body {{ font-family: 'Noto Sans CJK JP', sans-serif; background: {cz.C_BG};
  position: relative; overflow: hidden; }}
.sun  {{ position: absolute; top: -240px; right: -240px; width: 620px; height: 620px;
  border-radius: 50%; background: {cz.C_SUN}; opacity: 0.16; }}
.sun2 {{ position: absolute; top: -50px; right: -50px; width: 260px; height: 260px;
  border-radius: 50%; background: {cz.C_SUN}; opacity: 0.20; }}
.logo {{ position: absolute; top: 250px; left: 80px; width: 86px; height: 86px; }}
.logo svg {{ width: 100%; height: 100%; display: block; }}
.wordmark {{ position: absolute; top: 276px; left: 182px; font-size: 30px;
  font-weight: 700; color: {cz.C_SUB}; letter-spacing: 0.06em; }}
/* 本文は安全領域（250〜1500px）の中央に置く */
.center {{ position: absolute; left: 80px; width: {W - 160}px;
  top: 880px; transform: translateY(-50%); text-align: center; }}
.cover-title {{ font-size: 70px; font-weight: 700; color: {cz.C_TITLE}; line-height: 1.5; }}
.cover-sub {{ margin-top: 40px; font-size: 32px; color: {cz.C_ACCENT};
  letter-spacing: 0.08em; font-weight: 700; }}
.pill {{ display: inline-block; font-size: 26px; font-weight: 700;
  letter-spacing: 0.10em; padding: 7px 24px; border-radius: 999px; }}
.pill-tsui {{ color: {cz.C_MUTED}; background: rgba(107,91,74,0.10); }}
.pill-iikae {{ color: #fff; background: {cz.C_ACCENT}; }}
.before {{ margin-top: 26px; font-size: 52px; color: {cz.C_MUTED};
  line-height: 1.5; font-weight: 700; }}
.arrow {{ margin: 30px 0; font-size: 56px; color: {cz.C_ACCENT}; font-weight: 700; }}
.after {{ font-size: 56px; color: {cz.C_ACCENT}; line-height: 1.5; font-weight: 700; }}
.note {{ margin-top: 30px; font-size: 30px; color: {cz.C_MUTED}; line-height: 1.6; }}
.text {{ font-size: 50px; color: {cz.C_TITLE}; line-height: 1.75; font-weight: 700; }}
.nudge {{ margin-top: 44px; font-size: 34px; color: {cz.C_ACCENT};
  line-height: 1.6; font-weight: 700; }}
.rule {{ position: absolute; bottom: 530px; left: 80px; width: 360px; height: 2px;
  background: {cz.C_ACCENT}; opacity: 0.45; }}
.tag {{ position: absolute; bottom: 450px; left: 80px; font-size: 26px;
  color: {cz.C_SUB}; letter-spacing: 0.06em; }}
</style></head>
<body>
  <div class="sun"></div><div class="sun2"></div>
  <div class="logo">{logo}</div>
  <div class="wordmark">ひだまりこそだち</div>
  <div class="center">{inner_html}</div>
  <div class="rule"></div>
  <div class="tag">子育ての考え方を、親のことばに</div>
</body></html>"""


def duration_of(slide: dict) -> float:
    """読む時間に合わせて1枚の表示時間を決める（短い行は1秒あたり13字くらいで読める）。"""
    chars = sum(len(l) for l in slide["lines"])
    sec = 1.0 + chars / 13.0
    if "表紙" in slide["label"]:
        sec += 0.6          # 表紙は一拍おく（離脱の判断に必要な時間）
    return round(min(max(sec, MIN_SEC), MAX_SEC), 2)


def encode(pngs: list[str], durs: list[float], out: str) -> None:
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y"]
    for p, d in zip(pngs, durs):
        cmd += ["-loop", "1", "-t", f"{d}", "-i", p]
    cmd += ["-stream_loop", "-1", "-i", BGM]

    # 各入力を同じ規格に揃え、xfade を連ねる（offset は累積・重なり分だけ短くなる）
    parts = [f"[{i}:v]fps={FPS},format=yuv420p,setsar=1[v{i}]" for i in range(len(pngs))]
    cur, offset = "[v0]", durs[0] - FADE
    for i in range(1, len(pngs)):
        nxt = f"[x{i}]"
        parts.append(f"{cur}[v{i}]xfade=transition=fade:duration={FADE}:offset={offset:.2f}{nxt}")
        cur = nxt
        offset += durs[i] - FADE
    total = sum(durs) - FADE * (len(pngs) - 1)
    parts.append(f"[{len(pngs)}:a]afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5[a]")

    cmd += ["-filter_complex", ";".join(parts),
            "-map", cur, "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-profile:v", "high", "-level", "4.0",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-t", f"{total:.2f}", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpeg 失敗:\n" + r.stderr[-1500:])


def main() -> None:
    ap = argparse.ArgumentParser(description="スライド原稿md → リール動画（1080x1920）")
    ap.add_argument("--script", required=True, help="スライド原稿 md（## スライド本文 を含む）")
    ap.add_argument("--outdir", default="", help="既定: assets/reels/<slug>")
    ap.add_argument("--frames-only", action="store_true", help="画像だけ作る")
    a = ap.parse_args()

    post = frontmatter.load(a.script)
    slug = str(post.get("slug") or os.path.splitext(os.path.basename(a.script))[0])
    slides = cz.parse_slides(post.content)
    if not slides:
        sys.exit("スライドが見つかりません（「## スライド本文」と **N枚目** 区切りを確認）")

    outdir = a.outdir or os.path.join(REPO, "assets", "reels", slug)
    cz.W, cz.H = W, H          # render_html_to_png の拡大率もリール用に切り替える
    pngs, durs = [], []
    print(f"=== リール生成: {len(slides)}枚 (slug={slug}) ===")
    for n, slide in enumerate(slides, 1):
        out = os.path.join(outdir, f"slide_{n:02d}.png")
        w, h = cz.render_html_to_png(frame_html(cz.build_inner(slide)), out)
        d = duration_of(slide)
        flag = "" if (w, h) == (W, H) else f"  [WARN] 期待{W}x{H}と不一致"
        print(f"[OK] slide_{n:02d}.png ({w}x{h}) {d}秒 — {slide['label'] or 'text'}{flag}")
        pngs.append(out)
        durs.append(d)

    total = sum(durs) - FADE * (len(pngs) - 1)
    print(f"\n合計 {total:.1f}秒（リールは3〜90秒・15秒以上が目安）")
    if a.frames_only:
        return
    if not os.path.exists(BGM):
        sys.exit(f"BGM が見つかりません: {BGM}")
    mp4 = os.path.join(REPO, "assets", "reels", f"{slug}.mp4")
    encode(pngs, durs, mp4)
    size = os.path.getsize(mp4) / 1024 / 1024
    print(f"[OK] {mp4}  {size:.1f}MB")
    print(f"""
--- 次の手順 ---
cp {mp4} web/ig/reels/
cd web && npx wrangler pages deploy . --project-name hidamari-kosodachi --commit-dirty=true
.venv/bin/python scripts/post_instagram_reel.py \\
  --video https://hidamari-kosodachi.com/ig/reels/{slug}.mp4 \\
  --caption-file {a.script} --commit""")


if __name__ == "__main__":
    main()
