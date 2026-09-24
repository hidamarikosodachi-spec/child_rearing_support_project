---
tags: [web, matcher, deploy]
status: active
date: 2026-09-24
related: [[type_system_v1]] [[questions_v1]] [[type_results_v1]]
---

# web/ — 診断サイト「わが家のこそだちタイプ」

リポジトリ内で完結する静的サイト。**中身の正本は `docs/matcher/`**（質問＝`questions_v1.md`／タイプ文＝`type_results_v1.md`）で、
`web/matcher/data.js` はそれを実装用に写したもの。**文言を変えるときは必ず両方を更新する。**

## 構成

| パス | 役割 |
|---|---|
| `matcher/index.html` | 診断本体（1ページ・開始→設問18→自由記述→結果） |
| `matcher/app.js` | 進行・採点・結果描画・共有・送信（素の JS / モジュール） |
| `matcher/data.js` | 質問15問・8タイプ・タイプ判定表 |
| `matcher/style.css` | ブランド配色（`scripts/note_thumbnail.py` と共通の色） |
| `privacy/index.html` | プライバシーについて（診断から常時リンク） |
| `functions/api/response.js` | 回答を D1 に1行 INSERT する Pages Function（`POST /api/response`・サイトと同一オリジン） |
| `schema.sql` | D1 のテーブル定義 |
| `wrangler.toml` | Pages プロジェクト設定＋D1 バインディング |

## ローカルで確認する

```bash
cd web && python3 -m http.server 8765
# → http://127.0.0.1:8765/matcher/
```
API 未設定でも診断は動く（送信は失敗しても握りつぶし、結果は必ず表示する）。

## 公開状況（2026-09-24 公開済）

- 本番URL: **https://hidamari-kosodachi.pages.dev/matcher/**
- Pages プロジェクト: `hidamari-kosodachi` ／ D1: `hidamari-matcher`（`35971a97-b7e4-4eac-a80c-c76af473e8e1`・APAC）
- 認証は `.env` の `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`（gitignore 済）

### 更新をデプロイする

```bash
cd web && set -a && . ../.env && set +a
npx wrangler pages deploy . --project-name hidamari-kosodachi --commit-dirty=true
```

スキーマを変更したとき:
```bash
npx wrangler d1 execute hidamari-matcher --remote --file=schema.sql
```

> workers.dev のサブドメインは登録していない（標準 Worker ではなく **Pages Function** を使うため不要）。
> これにより `/api/response` がサイトと同一オリジンになり、CORS の問題も起きない。

## 分析（回答データ）

```bash
# タイプ分布
npx wrangler d1 execute hidamari-matcher --remote --command \
  "SELECT type, COUNT(*) n FROM responses WHERE type IS NOT NULL GROUP BY type ORDER BY n DESC"
# 悩みの自由記述（原文は公開しない）
npx wrangler d1 execute hidamari-matcher --remote --command \
  "SELECT worry FROM responses WHERE worry <> '' ORDER BY created_at DESC LIMIT 50"
# 離脱した設問
npx wrangler d1 execute hidamari-matcher --remote --command \
  "SELECT drop_at, COUNT(*) n FROM responses WHERE drop_at IS NOT NULL GROUP BY drop_at ORDER BY drop_at"
```
集計結果は `docs/insights/matcher.md` に定期生成する（既存の insights 運用に合わせる）。

## 設計上の約束（変更するときは [[type_system_v1]] を読んでから）

- **順位をつけない／正解を決めない**。8タイプは等価。
- 結果は「性格の判定」ではなく「いまのスナップショット」と明記する（`DISCLAIMER`）。
- 個人を特定できる情報は受け取らない（氏名・メール・IP・追跡クッキーなし）。
- 保存に失敗しても診断体験は壊さない。
- ロックインしない：静的部分は他のホスティングでも動き、D1 は SQLite として書き出せる。
