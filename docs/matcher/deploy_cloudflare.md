---
tags: [matcher, deploy, cloudflare, runbook]
status: active
date: 2026-09-24
related: [[type_system_v1]] [[web/README]]
---

# 診断サイト公開の手順（Cloudflare）

> ✅ **2026-09-24 公開完了 → https://hidamari-kosodachi.pages.dev/matcher/**
> 以下は記録（再構築・引き継ぎ用）。日々の更新手順は [[web/README]] を見る。

> **オーナーがやるのは「1. トークンを作って .env に貼る」だけ（10分）。** 残りは私（Claude）が実行する。

## 1. オーナー作業：API トークンを作る（10分・1回だけ）

1. https://dash.cloudflare.com にログイン（**R2 で使っている既存アカウント**）
2. 右上のアイコン → **「プロフィール」** → 左メニュー **「API トークン」**
3. **「トークンを作成」** → 一番下の **「カスタムトークンを作成」** の「作成を開始する」
4. 名前: `hidamari-matcher-deploy`
5. **アクセス許可**（「＋権限を追加」で3行にする）

   | 種別 | 項目 | 権限 |
   |---|---|---|
   | アカウント | Workers スクリプト | 編集 |
   | アカウント | D1 | 編集 |
   | アカウント | Cloudflare Pages | 編集 |

6. **アカウントリソース**: 「包含」→ ご自身のアカウントを選択
7. 「概要に進む」→ **「トークンを作成する」** → 表示された文字列をコピー
   （**この画面を閉じると二度と表示されない**ので、その場で次の手順へ）
8. アカウント ID を控える: ダッシュボード右側、または Workers & Pages のページに表示される32桁の英数字
9. リポジトリの `.env` に追記して保存（`.env` は Git に載らない）

   ```
   CLOUDFLARE_API_TOKEN=（コピーしたトークン）
   CLOUDFLARE_ACCOUNT_ID=（32桁のアカウントID）
   ```

10. 「入れました」と一言ください。

### 注意
- トークンは**パスワードと同じ**。チャットや note に貼らない。`.env` にだけ置く。
- 権限は上の3つだけ。DNS やゾーン編集の権限は**渡さない**（万一漏れても被害を診断サイトに限定するため）。
- 不要になったら同じ画面から削除できる（削除は即時・可逆）。

## 2. 私の作業（トークンが入ったあと）

```bash
npm install -g wrangler                                    # 初回のみ
wrangler d1 create hidamari-matcher                        # DB作成 → id を wrangler.toml へ
wrangler d1 execute hidamari-matcher --remote --file=web/worker/schema.sql
cd web/worker && wrangler deploy                           # 保存API
wrangler pages project create hidamari-kosodachi           # 初回のみ
wrangler pages deploy web --project-name hidamari-kosodachi
```

公開URL（例）: `https://hidamari-kosodachi.pages.dev/matcher/`
→ 動作確認（実際に1回診断して D1 に行が入るか）まで私がやり、URL をお知らせする。

## 3. 公開後

- note・Threads・IG の各プロフィールに診断URLを置く（T101 導線）
- 告知記事（予告編）を note に入稿 → オーナーが公開ボタン
- 回答が溜まったら `docs/insights/matcher.md` に集計（タイプ分布・悩みの頻出語・離脱設問）

## 4. 独自ドメインについて（保留・今は不要）

`*.pages.dev` のままで支障はない。独自ドメイン（例 `hidamari-kosodachi.com`）は年1,000〜1,500円程度で、
**ブランドとして必要になったら**取得を判断する。取得した場合も Cloudflare に載せれば設定は数分。
