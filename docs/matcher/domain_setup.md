---
tags: [web, domain, runbook, seo]
status: active
date: 2026-09-29
related: [[web_growth_strategy_v1]] [[deploy_cloudflare]] [[web/README]]
---

# 独自ドメイン `hidamari-kosodachi.com` の取得と接続

> ✅ **2026-09-29 稼働開始 → https://hidamari-kosodachi.com/matcher/**

> 空き確認済み（2026-09-29・RDAP で未登録）。**ドメイン購入だけはオーナーの決済操作が必要**（API では不可）。
> 取得後の接続・移行はすべて私（Claude）が行う。

## なぜ取るか
[[web_growth_strategy_v1]] の柱のひとつが**検索流入（SEO）**。`*.pages.dev` は検索で不利なうえ、
サブドメインなので**ドメインの評価が自分に積み上がらない**。SEO に賭けるなら前提条件。
費用は**年 1,500円前後のみ**（Cloudflare は原価提供・上乗せなし・Whois代行は無料で自動）。

## オーナー作業（10分・1回だけ）

1. https://dash.cloudflare.com/42eee9ce328ae3727b92ca4530e88471/domains/register を開く
   （左メニュー **Domains → Register domain**）
2. 検索欄に **`hidamari-kosodachi.com`** と入力
3. 価格を確認（`.com` は年 $10 前後＝1,500円程度）→ **Purchase / 購入**
4. 支払い情報（クレジットカード）を登録 → 購入確定
   - **Whois 代行は自動で無料適用**される（個人情報は公開されない）
   - 自動更新はオンのままでよい（切れると失う）
5. 「買いました」と一言

> ⚠️ 更新料も同額（原価提供）。初年度だけ安い方式ではないので、後から値上がりしない。

## 私の作業（購入後）

1. Pages プロジェクトにカスタムドメインを追加（`hidamari-kosodachi.com` / `www` )
   ```bash
   cd web && npx wrangler pages deployment ... # または dash の Custom domains から追加
   ```
2. DNS は Cloudflare 内で自動設定（同一アカウントのため手作業なし）
3. **サイト内のURLをすべて新ドメインへ置換**
   - `scripts/build_matcher_pages.py` の `SITE`
   - `scripts/build_matcher_og.py` の OGP URL
   - `web/matcher/*.html` の canonical / og:url
   - `web/sitemap.xml` / `robots.txt`
4. **`*.pages.dev` からのリダイレクト**を設定（既に配った旧URLを死なせない）
   - note 告知記事・Threads 投稿・IG プロフィールに旧URLが出ているため必須
5. Web Analytics のホスト名を新ドメインに追加
6. 記事置き場（`docs/site/articles/` → `web/kosodachi/*.html`）の生成スクリプトを作る
7. Google Search Console に登録し、sitemap を送信

## 移行後のURL

| いま | 移行後 |
|---|---|
| `hidamari-kosodachi.com/matcher/` | `hidamari-kosodachi.com/matcher/` |
| `…/matcher/t/engawa` | `hidamari-kosodachi.com/matcher/t/engawa` |
| （新設） | `hidamari-kosodachi.com/kosodachi/<slug>` ＝ 悩み別の検索記事 |

## 注意
- ドメイン購入の API は現行トークンの権限外（`Authentication error` を確認済）。**画面からの操作が必要**。
- 取得後すぐは検索に出ない。**効き始めるのは3〜6ヶ月後**。焦って評価しない。

---

## 取得後の進捗（2026-09-29）

| 手順 | 状態 |
|---|---|
| ドメイン取得 | ✅ オーナー購入（Cloudflare Registrar） |
| ゾーン作成 | ✅ `hidamari-kosodachi.com`（active・自動） |
| Pages へカスタムドメイン追加 | ✅ API で追加（status: pending） |
| **DNS レコード作成** | ✅ CNAME `@` / `www` → pages.dev（プロキシON） |
| SSL 証明書 | ✅ 発行済み（apex / www とも 200） |
| サイト内URLの置換 | ✅ 27ファイル（canonical・OGP・sitemap・生成スクリプト） |
| 旧URLのリダイレクト | ✅ `functions/_middleware.js` で 301（POST は除外） |
| Web Analytics のホスト追加 | ⏳ オーナー操作（下記） |
| Google Search Console | ⏳ 次にやる |

### 解除方法（どちらか一方でよい）

**方法A：トークンに DNS 権限を足す（推奨・以後も私が作業できる）**
1. https://dash.cloudflare.com/profile/api-tokens → `hidamari-matcher-deploy` の **編集**
2. 「アクセス許可」に1行追加 → **ゾーン / DNS / 編集**
3. ゾーンリソース: 「包含 → 特定のゾーン → hidamari-kosodachi.com」
4. 保存（**トークンの文字列は変わらない**ので .env の更新は不要）

**方法B：画面から手で足す（1回きり）**
1. Cloudflare → **Websites** → `hidamari-kosodachi.com` → **DNS** → **レコードを追加**
2. 種類 `CNAME` ／ 名前 `@` ／ ターゲット `hidamari-kosodachi.com` ／ **プロキシ ON（オレンジの雲）**
3. 同じ要領で 名前 `www` ／ ターゲット `hidamari-kosodachi.com` ／ プロキシ ON


## 移行後の残作業

### オーナー（3分）
**Web Analytics に新ホスト名を追加**（いまは pages.dev のみ計測しているため、新ドメインの訪問が記録されない）
1. https://dash.cloudflare.com/42eee9ce328ae3727b92ca4530e88471/web-analytics
2. `hidamari-kosodachi.com` を **Add a site**
3. 表示される token を教えてください → 私がタグを差し替えます
   （※ 既存の pages.dev 用サイトは残しておいてよい）

### 私
- Google Search Console 登録＋sitemap 送信（DNS 認証は権限があるので自動でできる）
- 悩み別記事の置き場と生成スクリプト（`docs/site/articles/` → `/kosodachi/<slug>`）

## Google Search Console（2026-09-30 完了）

| 手順 | 状態 |
|---|---|
| プロパティ登録（ドメイン） | ✅ オーナー実施。Cloudflare 連携の **Authorize** でTXTレコードが自動追加された |
| sitemap 送信 | ✅ `https://hidamari-kosodachi.com/sitemap.xml` →「成功しました」検出11ページ |
| 検索パフォーマンスのデータ | ⏳ 翌日から。中身が溜まるのは数週間〜数ヶ月先 |

> **つまずいた点**: ドメインプロパティでは `sitemap.xml` だけでは無効。**URL全体**を入れる必要がある。

### これから見る場所
- **検索パフォーマンス** … どんな検索語で表示/クリックされたか（次の記事テーマを決める実データ）
- **ページ（インデックス作成）** … 検索に載っているページ／載っていないページと、その理由

記事を公開したら sitemap は自動更新されるので、**再送信は不要**（Google が定期的に読みに来る）。
