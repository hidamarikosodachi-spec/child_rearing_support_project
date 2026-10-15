#!/usr/bin/env python3
"""note 探索期の突き合わせ表を作る（read-only）。

オーナー指示（2026-10-15）: note を毎日投稿して、ジャンルと口調で何が当たるかを調べる。
計画は docs/note/exploration_v1.md。

仕組み:
  - 記事 md の front-matter `genre:`（G1〜G5）と `tone:`（T1〜T4）を読む。
    無い記事は `category:` をジャンル代わりに使う（過去記事は基準線として並べる）。
  - note の統計 API は**累計PVしか返さない**ので、実行のたびに記事別PVを
    docs/insights/note_pv_history.jsonl に記録し、「公開から3日後・7日後のPV」をそこから求める。
    → **セッションを開いた日にしか記録されない**。3日後ちょうどの値が無いときは、
       3日以上たった最初の記録を使う（表に経過日数を出す）。
  - 出力: docs/insights/note_experiments.md（手編集しない）

    .venv/bin/python scripts/note_experiment.py
"""
from __future__ import annotations

import datetime as dt
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import note_insights  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "docs/note/articles"
HIST = ROOT / "docs/insights/note_pv_history.jsonl"
OUT = ROOT / "docs/insights/note_experiments.md"
JST = dt.timezone(dt.timedelta(hours=9))

GENRES = {"G1": "教育方法", "G2": "困りごと", "G3": "親の自責", "G4": "研究を読む", "G5": "上流の問い"}
TONES = {"T1": "説明体", "T2": "物語体", "T3": "要点型", "T4": "対話体"}


def _fm(path: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}
    out = {}
    for line in raw.split("---", 2)[1].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.split("  #")[0].strip().strip('"')
    return out


def articles() -> list[dict]:
    rows = []
    for f in sorted(ARTICLES.glob("*.md")):
        m = _fm(f)
        url = m.get("published_url", "")
        key = re.search(r"/n/(n[0-9a-f]+)", url)
        if m.get("status") != "published" or not key:
            continue
        rows.append({"key": key.group(1), "title": m.get("title", f.stem),
                     "published": str(m.get("published", ""))[:10],
                     "genre": m.get("genre") or f"({m.get('category', '?')})",
                     "tone": m.get("tone") or "—"})
    return rows


def snapshot(today: str) -> dict[str, int]:
    st = note_insights.fetch_stats(note_insights._cookie_header())
    pv = {n["key"]: n.get("read_count", 0) for n in st["notes"]}
    lines = HIST.read_text(encoding="utf-8").splitlines() if HIST.exists() else []
    lines = [x for x in lines if json.loads(x).get("date") != today]   # 同日は上書き
    lines.append(json.dumps({"date": today, "pv": pv}, ensure_ascii=False))
    HIST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return pv


def pv_at(hist: list[dict], key: str, pub: str, days: int) -> str:
    try:
        p = dt.date.fromisoformat(pub)
    except ValueError:
        return "—"
    for h in hist:   # 日付順
        d = (dt.date.fromisoformat(h["date"]) - p).days
        if d >= days and key in h["pv"]:
            return f"{h['pv'][key]}" + (f"（{d}日）" if d != days else "")
    return "—"


def main() -> None:
    today = dt.datetime.now(JST).date().isoformat()
    now = snapshot(today)
    hist = sorted((json.loads(x) for x in HIST.read_text(encoding="utf-8").splitlines() if x.strip()),
                  key=lambda h: h["date"])
    rows = articles()
    lines = [
        "---", "tags: [insights, note, experiment]", "status: auto-generated",
        f"updated: {today}", "updated_by: scripts/note_experiment.py（自動生成・手編集しない）", "---", "",
        "# 📝 note 探索期の突き合わせ（[[exploration_v1]]）", "",
        "> 読み方: **同じ条件3本以上・中央値が2倍以上**の差だけを差とみなす。1本の差は誤差。",
        "> 3日後/7日後PVは、その日以降に初めて記録された値（括弧内は実際の経過日数）。", "",
        "## ジャンル別（7日後PVの中央値）", "",
        "| ジャンル | 本数（7日経過） | 中央値 | 各記事 |", "|---|---|---|---|",
    ]
    by: dict[str, list[int]] = {}
    for r in rows:
        v = pv_at(hist, r["key"], r["published"], 7)
        if v != "—":
            by.setdefault(r["genre"], []).append(int(v.split("（")[0]))
    for g, vs in sorted(by.items()):
        name = GENRES.get(g, g)
        lines.append(f"| {name} | {len(vs)} | {statistics.median(vs):g} | {', '.join(map(str, vs))} |")
    lines += ["", "## 記事別", "",
              "| 公開日 | ジャンル | 口調 | 3日後 | 7日後 | 現在 | タイトル |", "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["published"], reverse=True):
        lines.append(f"| {r['published']} | {GENRES.get(r['genre'], r['genre'])} | {TONES.get(r['tone'], r['tone'])} | "
                     f"{pv_at(hist, r['key'], r['published'], 3)} | {pv_at(hist, r['key'], r['published'], 7)} | "
                     f"{now.get(r['key'], '—')} | {r['title'][:30]} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"→ {OUT.relative_to(ROOT)}（記事 {len(rows)} 本・記録 {len(hist)} 日分）")


if __name__ == "__main__":
    main()
