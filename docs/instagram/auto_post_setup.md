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
| `META_APP_ID` / `META_APP_SECRET` | ❌ 未設定（※Instagramログイン方式では不要） |
| Facebookページ | 無し（**Instagram単独のビジネスポートフォリオ**）→ ページ不要の方式を採る |

## できること・できないこと（先に把握）

- ✅ **フィード投稿（カルーセル・単画像）は完全自動化できる**。承認済みドラフトを日付指定で投稿できる。
- ❌ **ストーリーのリンクスタンプは API で貼れない**。ストーリーだけは今後も手動（Meta Business Suite）。
- ⚠️ 自動投稿は「1日25件まで」等の API 制限あり。週1〜2本の運用なら問題ない。

## オーナー作業（15分・1回だけ）

> **重要**: Meta Business Suite の「設定」画面では**トークンは作れません**。作業場所は **developers.facebook.com** です。
> また、このアカウントは Facebookページを持たない Instagram 単独のポートフォリオなので、
> 従来の「Facebookページ経由（Instagram Graph API）」ではなく、**Instagram ログイン方式**を使う。
> こちらは **Facebookページ不要**で投稿までできる（Meta 公式ドキュメントで確認済 2026-09-25）。

### ステップ1: アプリを作る
1. https://developers.facebook.com/apps を開く（Instagram と同じアカウントでログイン）
2. 右上 **「アプリを作成」**
3. ユースケースの選択 → **「Instagram」**（"Instagramのコンテンツを管理する" 等と書かれたもの）
4. アプリ名: `hidamari-kosodachi`／連絡先メールを入力 → 作成

### ステップ2: トークンを生成する（ここが本丸）
1. 作成したアプリの左メニュー → **「Instagram」** → **「Instagramログインでのapi設定」**
   （英語表記なら *API setup with Instagram login*）
2. **「3. Instagramビジネスログインを設定」**あたりにある **「アクセストークンを生成」** をクリック
3. Instagram のログイン画面が出る → **@hidamarikosodachi でログイン** → アクセスを許可
4. 画面にトークン（非常に長い文字列）が表示される
   ⚠️ **この画面を離れると二度と表示されない**ので、その場でコピー
5. 同じ画面に出ている **Instagram アプリID** も控える（数字の羅列）

### ステップ3: `.env` に貼る
```
META_INSTAGRAM_TOKEN=（ステップ2でコピーしたトークン）
META_INSTAGRAM_APP_ID=（Instagram アプリID）
```
> ⚠️ `META_ACCESS_TOKEN`（Threads用）は**絶対に上書きしない**。別の行に追記する。

### ステップ4: 「入れました」と一言
残りは私がやる:
- ユーザーID（`META_INSTAGRAM_BUSINESS_ID`）を API から取得して `.env` に追記
- 短期トークン → **長期トークン（60日）** に交換
- カルーセル④で dry-run → 実投稿
- 60日ごとのリフレッシュを定期作業（T112）に追加

### つまずいたら
- **「Instagram」のユースケースが出ない** → 「その他」→「ビジネス」を選び、作成後にダッシュボードの製品追加から「Instagram」を追加
- **ログインで弾かれる** → Instagram がプロアカウント（ビジネスまたはクリエイター）になっているか確認
- **トークンをコピーし損ねた** → 同じ画面で作り直せる（何度でも可）

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
