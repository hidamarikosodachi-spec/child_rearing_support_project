---
tags: [instagram, deploy, runbook, automation]
status: active
date: 2026-09-25
related: [[carousel04_matcher]] [[profile_matcher_v1]] [[deploy_cloudflare]]
---

# Instagram 自動投稿を有効にする手順（T103）

> **結論**: 仕組み（`scripts/post_instagram.py`・カルーセル対応）は完成していて、画像の公開先も用意できた。
> 足りないのは **Instagram 用のアクセストークンと ID だけ**。オーナーの Meta ログインが要るため、ここだけ代行できない。



> ## ▶ 2026-10-01 再開（オーナー判断）
> 9/26 に「月20分の節約に見合わない」と一度見送ったが、**Instagram が全チャネルで最も反応率が高い**ことが
> 分かったため再開する（9/28 カルーセルでコメント1件・パパ層から。note/Threads では取れていない層）。
> 自動化の価値は「投稿の手間」より **コメントを取りこぼさないこと**にある。
>
> **方式は Instagram ログイン方式**（`graph.instagram.com`・**Facebookページ不要**）。
> ただし **Meta アプリの作成には Facebook アカウントが必要**で、本アカウントは Instagram 単独のため、
> **オーナーが Facebook アカウントを作るところからになる**（下記手順）。

## 現状（2026-09-25 時点）

| 要素 | 状態 |
|---|---|
| 投稿スクリプト（カルーセル/単画像） | ✅ 完成。**2026-10-01 に Instagram ログイン方式（`graph.instagram.com`）へ変更済** |
| コメントの読み取り・返信 | ✅ **`scripts/instagram_comments.py` 新設**（list / reply・dry-run 既定・1日3件まで・全操作ログ） |
| キャプション抽出 | ✅ 修正済（「## キャプション（投稿本文）」節だけを本文にする） |
| 画像の公開URL | ✅ **Cloudflare Pages で配信**（`web/ig/...` → `https://hidamari-kosodachi.com/ig/...`）。**R2 は不要になった** |
| `META_INSTAGRAM_BUSINESS_ID` | ❌ 未取得 |
| Instagram 投稿権限つきトークン | ❌ 未取得（いまの `META_ACCESS_TOKEN` は **Threads 専用**で、Facebook Graph では弾かれる） |
| `META_APP_ID` / `META_APP_SECRET` | ❌ 未設定（※Instagramログイン方式では不要） |
| Facebookページ | 無し（**Instagram単独のビジネスポートフォリオ**）→ ページ不要の方式を採る |

## できること・できないこと（先に把握）

- ✅ **フィード投稿（カルーセル・単画像）は完全自動化できる**。承認済みドラフトを日付指定で投稿できる。
- ❌ **ストーリーのリンクスタンプは API で貼れない**。ストーリーだけは今後も手動（Meta Business Suite）。
- ⚠️ 自動投稿は「1日25件まで」等の API 制限あり。週1〜2本の運用なら問題ない。

## オーナー作業（20〜30分・1回だけ）

> **前提の確認**: Meta の開発者登録には **Facebook アカウントが必要**です。
> 本アカウントは Instagram 単独なので、**Facebook アカウントを新しく作るところから**始まります。
> Facebook を使う必要はありません（アプリ管理のためだけに持ちます）。

### ステップ1: Facebook アカウントを作る
1. https://www.facebook.com/ → 「新しいアカウントを作成」
2. 実名・生年月日・メール（`Hidamarikosodachi@gmail.com` でよい）で作成
3. **プロフィールを埋めたり友達を追加したりする必要はありません**
4. ⚠️ 作りたてのアカウントは一時的に制限がかかることがあります。
   その場合は数日おいてから、または本人確認を済ませてから次へ進みます

### ステップ2: Instagram と紐づける（推奨・任意）
Instagram アプリ → 設定 → アカウントセンター → **「アカウントを追加」→ Facebook**
（紐づけておくと、のちの認証でつまずきにくくなります）

### ステップ3: Meta アプリを作る
1. https://developers.facebook.com/apps → ログイン（**作った Facebook アカウントで**）
2. 初回は開発者登録（規約同意＋電話かメールの確認・2〜3分）
3. **「アプリを作成」** → ユースケース **「Instagram」**
4. アプリ名 `hidamari-kosodachi` ／ 連絡先メールを入力 → 作成

### ステップ4: アクセストークンを生成
1. 左メニュー **「Instagram」→「Instagramログインでのapi設定」**
2. 権限に次が含まれていることを確認（足りなければ追加）
   - `instagram_business_basic`
   - `instagram_business_content_publish`（投稿）
   - `instagram_business_manage_comments`（コメント返信）
3. **「アクセストークンを生成」** → @hidamarikosodachi でログイン → 許可
4. 出てきた長い文字列を**その場でコピー**（画面を離れると二度と出ません）

### ステップ5: `.env` に貼る
```
META_INSTAGRAM_TOKEN=（ステップ4のトークン）
```
> ⚠️ `META_ACCESS_TOKEN`（Threads 用）は**上書きしない**。別の行に足す。

### ステップ6: 「入れました」と一言
残りは私がやります。
- ユーザーID（`META_INSTAGRAM_USER_ID`）を API から取得して `.env` に追記
- 短期トークン → **長期トークン（60日）** に交換し、更新を定期作業へ登録
- カルーセルで dry-run → 実投稿テスト
- コメントの読み取り・返信を稼働

### つまずいたら
- **「Instagram」のユースケースが出ない** → 「その他」→「ビジネス」で作成し、製品から Instagram を追加
- **ログインで弾かれる** → Instagram がプロアカウント（ビジネス/クリエイター）か確認
- **新しい Facebook アカウントがロックされた** → 本人確認を済ませる。急がず数日待つ

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
