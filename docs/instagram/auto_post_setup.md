---
tags: [instagram, deploy, runbook, automation]
status: active
date: 2026-09-25
related: [[carousel04_matcher]] [[profile_matcher_v1]] [[deploy_cloudflare]]
---

# Instagram 自動投稿を有効にする手順（T103）

> **結論**: 仕組み（`scripts/post_instagram.py`・カルーセル対応）は完成していて、画像の公開先も用意できた。
> 足りないのは **Instagram 用のアクセストークンと ID だけ**。オーナーの Meta ログインが要るため、ここだけ代行できない。

## 現状（2026-09-25 時点）

| 要素 | 状態 |
|---|---|
| 投稿スクリプト（カルーセル/単画像） | ✅ 完成（`scripts/post_instagram.py`） |
| キャプション抽出 | ✅ 修正済（「## キャプション（投稿本文）」節だけを本文にする） |
| 画像の公開URL | ✅ **Cloudflare Pages で配信**（`web/ig/...` → `https://hidamari-kosodachi.pages.dev/ig/...`）。**R2 は不要になった** |
| `META_INSTAGRAM_BUSINESS_ID` | ❌ 未取得 |
| Instagram 投稿権限つきトークン | ❌ 未取得（いまの `META_ACCESS_TOKEN` は **Threads 専用**で、Facebook Graph では弾かれる） |
| `META_APP_ID` / `META_APP_SECRET` | ❌ 新マシンで未再設定 |

## できること・できないこと（先に把握）

- ✅ **フィード投稿（カルーセル・単画像）は完全自動化できる**。承認済みドラフトを日付指定で投稿できる。
- ❌ **ストーリーのリンクスタンプは API で貼れない**。ストーリーだけは今後も手動（Meta Business Suite）。
- ⚠️ 自動投稿は「1日25件まで」等の API 制限あり。週1〜2本の運用なら問題ない。

## オーナー作業（20分・1回だけ）

### 1. Instagram がプロアカウント＆Facebookページ連携になっているか確認
Business Suite からストーリー投稿ができている（2026-09-24 実績）ので、**おそらく済んでいる**。
念のため: Instagram アプリ → 設定 → アカウントの種類とツール → 「プロアカウント」になっているか。

### 2. Meta アプリを作る
1. https://developers.facebook.com/apps → 「アプリを作成」
2. ユースケース: **「Instagram」**（または「その他」→ ビジネス）
3. アプリ名: `hidamari-kosodachi`（任意）
4. 作成後、**アプリID** と **app secret**（設定 → ベーシック）を控える

### 3. アクセストークンを取得
1. https://developers.facebook.com/tools/explorer （グラフAPIエクスプローラ）
2. 右上でアプリに `hidamari-kosodachi` を選択
3. 「ユーザーまたはページ」→ **自分のFacebookページ** を選ぶ
4. 権限（アクセス許可）に次を追加:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
   - `business_management`
5. 「アクセストークンを生成」→ Facebook のログイン確認 → 出てきたトークンをコピー

### 4. `.env` に貼る
```
META_APP_ID=（アプリID）
META_APP_SECRET=（app secret）
META_INSTAGRAM_TOKEN=（手順3のトークン）
```
> ⚠️ `META_ACCESS_TOKEN`（Threads用）は**上書きしない**。別の変数名で入れる。

### 5. 「入れました」と一言
残りは私がやる:
- `scripts/meta_setup_ids.py` で **Instagram ビジネスID / FBページID** を取得し `.env` に追記
- 短期トークン → **長期トークン（60日）** に交換
- カルーセル④で実投稿テスト
- 月次リフレッシュを `meta_token_refresh.py` の運用に追加

## 私の運用（有効化後）

```bash
# 画像を Pages に置いて公開URLにする
cp assets/instagram/<date>/slide_*.png web/ig/<date>/
cd web && npx wrangler pages deploy . --project-name hidamari-kosodachi --commit-dirty=true

# ドラフトの images: を公開URLにして投稿
.venv/bin/python scripts/post_instagram.py --date <date>            # dry-run
.venv/bin/python scripts/post_instagram.py --date <date> --commit   # 実投稿
```

## やらない判断

- **R2 は使わない**（Cloudflare Pages で画像配信できるため。管理するキーが減る）。
- ストーリーの自動化は追わない（リンクスタンプが API 非対応で、自動化しても価値が出ない）。
