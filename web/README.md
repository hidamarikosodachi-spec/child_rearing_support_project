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
| `worker/index.js` | 回答を D1 に1行 INSERT する API（`POST /api/response`） |
| `worker/schema.sql` | D1 のテーブル定義 |

## ローカルで確認する

```bash
cd web && python3 -m http.server 8765
# → http://127.0.0.1:8765/matcher/
```
API 未設定でも診断は動く（送信は失敗しても握りつぶし、結果は必ず表示する）。

## 公開手順（Cloudflare Pages + D1）

**前提**: Cloudflare アカウント（R2 で使用中のもの）。オーナー作業は API トークン発行のみ。

```bash
npm install -g wrangler        # 初回のみ
wrangler login                 # ブラウザで認証（オーナー）

# 1) DB を作る → 出力された database_id を worker/wrangler.toml に記入
wrangler d1 create hidamari-matcher
wrangler d1 execute hidamari-matcher --remote --file=web/worker/schema.sql

# 2) API をデプロイ
cd web/worker && wrangler deploy

# 3) サイトを公開（web/ を publish ディレクトリに）
wrangler pages deploy web --project-name hidamari-kosodachi
```

`/api/response` を同一オリジンで受けるには、Pages プロジェクトに Worker を
**Functions ルート**または**カスタムドメインのルート**で割り当てる。未設定の間は送信だけ失敗し、診断自体は動く。

## 分析（回答データ）

```bash
# タイプ分布
wrangler d1 execute hidamari-matcher --remote --command \
  "SELECT type, COUNT(*) n FROM responses WHERE type IS NOT NULL GROUP BY type ORDER BY n DESC"
# 悩みの自由記述（原文は公開しない）
wrangler d1 execute hidamari-matcher --remote --command \
  "SELECT worry FROM responses WHERE worry <> '' ORDER BY created_at DESC LIMIT 50"
# 離脱した設問
wrangler d1 execute hidamari-matcher --remote --command \
  "SELECT drop_at, COUNT(*) n FROM responses WHERE drop_at IS NOT NULL GROUP BY drop_at ORDER BY drop_at"
```
集計結果は `docs/insights/matcher.md` に定期生成する（既存の insights 運用に合わせる）。

## 設計上の約束（変更するときは [[type_system_v1]] を読んでから）

- **順位をつけない／正解を決めない**。8タイプは等価。
- 結果は「性格の判定」ではなく「いまのスナップショット」と明記する（`DISCLAIMER`）。
- 個人を特定できる情報は受け取らない（氏名・メール・IP・追跡クッキーなし）。
- 保存に失敗しても診断体験は壊さない。
- ロックインしない：静的部分は他のホスティングでも動き、D1 は SQLite として書き出せる。
