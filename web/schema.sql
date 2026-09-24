-- 診断回答の保存先（Cloudflare D1 / SQLite）
-- 生データを保存する方針（集計値だけ保存すると後から分析し直せないため）。
-- 個人を特定できる項目は保存しない（氏名・メール・IP・Cookie は取らない）。

CREATE TABLE IF NOT EXISTS responses (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  v           INTEGER NOT NULL DEFAULT 1,
  type        TEXT,             -- 算出タイプ（途中離脱なら NULL）
  near        TEXT,             -- 近接タイプ（JSON配列）
  axis_i      REAL,
  axis_s      REAL,
  axis_r      REAL,
  answers     TEXT,             -- 15問の生回答（JSON）
  age         TEXT,             -- 子の年齢（JSON配列）
  siblings    TEXT,
  worry       TEXT,             -- 自由記述（任意・最大200字）
  drop_at     INTEGER,          -- 途中離脱した設問番号（完了は NULL）
  ref         TEXT,             -- 流入元
  ua_mobile   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_responses_created ON responses (created_at);
CREATE INDEX IF NOT EXISTS idx_responses_type    ON responses (type);
