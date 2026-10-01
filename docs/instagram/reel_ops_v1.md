---
tags: [instagram, reel, ops]
status: v1
date: 2026-10-01
related: [[auto_post_setup]] [[feedback-note-to-instagram]] [[writing_voice_v1]]
---

# Instagram リール運用 v1（オーナー方針 2026-10-01）

> **「IGは文章よりリールの方が確実に回るので、リール登録を基本としてください」**
> → **Instagram の基本形式をリールにする。フィードでの告知投稿はしない。**

## 制作パイプライン（2026-10-01 復旧・全自動）

```bash
# 1. フレーム生成（色鉛筆絵本タッチ・930枚＝31秒）
cd scripts/reel_node && node render_full.js

# 2. 動画化（BGM付き・1080x1920・h264/aac）
FF=$(.venv/bin/python -c "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())")
"$FF" -y -framerate 30 -i scripts/reel_node/frames_full/f_%05d.png -i scripts/reel_node/bgm.wav \
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest \
  -movflags +faststart assets/reels/<name>.mp4

# 3. 公開URL化（Instagram API は公開URLしか受け取れない）
cp assets/reels/<name>.mp4 web/ig/reels/
cd web && npx wrangler pages deploy . --project-name hidamari-kosodachi --commit-dirty=true

# 4. 投稿（--commit 無しは dry-run）
.venv/bin/python scripts/post_instagram_reel.py --video https://hidamari-kosodachi.com/ig/reels/<name>.mp4 \
  --caption-file docs/instagram/<台本>.md --commit
```

### 新マシンで直したこと（2026-10-01）
- `render_full.js` のフォントパスが `/usr/share/fonts/...` 固定で、**日本語が豆腐（□）になっていた**
  → ユーザー領域（`~/.local/share/fonts/NotoSansCJK-Regular.ttc`）を探す形に変更
- ffmpeg 未導入 → **`imageio-ffmpeg`（venv 内蔵バイナリ）**で解決（システムへの install 不要）
- `npm install`（@napi-rs/canvas / roughjs）

## ⚠️ 音源の制約（判断が要る）

**API から投稿したリールには、Instagram の音源ライブラリ（流行の音）を付けられない。**
焼き込んだ BGM だけになる。リールの伸びは音の影響が大きいので、ここは無視できない。

| 方式 | オーナーの手間 | 流行の音 | 向き |
|---|---|---|---|
| **A. API で自動投稿** | **0分** | ✗（自作BGMのみ） | 本数を出す回・在庫消化 |
| **B. アプリから手動投稿** | 2〜3分 | **○** | 勝負する回・新シリーズの初回 |

**当面の運用案**: 基本はA（自動）。反応を見て、伸ばしたい回だけBに切り替える。

## 1本目の在庫（完成済み）

- `assets/reels/reel02_ehon.mp4`（31秒・4.3MB・BGM付き）
- 公開URL: https://hidamari-kosodachi.com/ig/reels/reel02_ehon.mp4
- 台本: [[reel02_ehon_kutsushita]]（靴が履けない場面→待つ→できた）
