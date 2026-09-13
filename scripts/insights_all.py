"""全サイト横断の反応集計（read-only）＝ note ＋ Threads（＋Instagram は手動枠）。

note_insights.py / threads_insights.py / note_comments_read.py を1本にまとめ、
「いいね・コメント・PV/views」をサイトごとに集計して、

  1. docs/insights/history.jsonl … 1回の集計＝1行（同日再実行は上書き）。推移の真実源
  2. docs/insights/dashboard.md  … Obsidian で読む表示専用ビュー（前回比つき・手編集しない）

に書き出す。**外部サービスへの書き込みは一切しない**（GET のみ）。

使い方:
    .venv/bin/python scripts/insights_all.py            # 集計→history 追記→dashboard 再生成
    .venv/bin/python scripts/insights_all.py --json     # 集計結果を JSON で標準出力（保存もする）
    .venv/bin/python scripts/insights_all.py --no-save  # 表示だけ（保存しない）

前提:
    - note:    .auth/note_state.json（capture_note_session.py で取得）
    - Threads: .env の META_ACCESS_TOKEN / META_THREADS_USER_ID
    - Instagram: API 未接続（オーナー手動投稿のため）。docs/insights/manual_instagram.json に
      手入力した数字があれば表示する（無ければ「未接続」表示）。

片方の認証が無くても落ちず、取れた分だけ集計する。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.threads_insights import (  # noqa: E402
    ACTIVE_METRICS,
    THREADS_API_BASE,
    _load_posts as load_threads_posts,
    fetch_account as fetch_threads_account,
    fetch_post_insights as fetch_threads_post_insights,
)
from scripts.note_insights import (  # noqa: E402
    KPI_BASELINE,
    KPI_TARGET_HIGH,
    KPI_TARGET_LOW,
    _cookie_header as note_cookie_header,
    fetch_stats as fetch_note_stats,
)
from scripts.note_comments_read import (  # noqa: E402
    COMMENTS_API as NOTE_COMMENTS_API,
    MY_URLNAME,
    extract_text,
)

JST = timezone(timedelta(hours=9))
OUT_DIR = PROJECT_ROOT / "docs" / "insights"
HISTORY = OUT_DIR / "history.jsonl"
DASHBOARD = OUT_DIR / "dashboard.md"
MANUAL_IG = OUT_DIR / "manual_instagram.json"
NOTE_AUTH = PROJECT_ROOT / ".auth" / "note_state.json"


# ----------------------------------------------------------------------------
# note
# ----------------------------------------------------------------------------
def _note_get(url: str, cookie: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Cookie": cookie, "Accept": "application/json"}
    )
    raw = urllib.request.urlopen(req, timeout=30).read().decode()
    return json.loads(raw)


def _note_comments(key: str, cookie: str) -> list[dict[str, Any]]:
    """1記事のルートコメント（本物は /note_comments。/comments は常に0の罠）。"""
    rows: list[dict[str, Any]] = []
    for page in range(1, 21):
        url = f"{NOTE_COMMENTS_API.format(key=key)}?per_page=50&page={page}&order=newest"
        try:
            data = _note_get(url, cookie).get("data", [])
        except (urllib.error.HTTPError, urllib.error.URLError):
            break
        if not data:
            break
        for c in data:
            u = c.get("user") or {}
            rows.append(
                {
                    "author": u.get("nickname"),
                    "author_urlname": u.get("urlname"),
                    "is_mine": u.get("urlname") == MY_URLNAME,
                    "body": extract_text(c.get("comment")).strip(),
                    "created_at": c.get("created_at"),
                    "replied": bool(c.get("is_creator_replied")),
                }
            )
        if len(data) < 50:
            break
    return rows


def collect_note() -> dict[str, Any]:
    if not NOTE_AUTH.exists():
        return {"ok": False, "reason": "no_session（capture_note_session.py 未実行）"}
    cookie = note_cookie_header()
    try:
        stats = fetch_note_stats(cookie)
    except Exception as exc:  # noqa: BLE001  セッション失効など
        return {"ok": False, "reason": f"stats_error: {exc}"}
    if not stats["notes"] and stats["totals"]["pv"] == 0:
        return {"ok": False, "reason": "not_login（セッション失効の可能性・再ログイン要）"}

    articles = []
    all_comments = []
    for n in stats["notes"]:
        key = n.get("key")
        comments = _note_comments(key, cookie) if key else []
        others = [c for c in comments if not c["is_mine"]]
        unreplied = [c for c in others if not c["replied"]]
        articles.append(
            {
                "key": key,
                "title": (n.get("name") or "").strip(),
                "pv": n.get("read_count", 0),
                "like": n.get("like_count", 0),
                "comment": len(others),
                "unreplied": len(unreplied),
                "url": f"https://note.com/{MY_URLNAME}/n/{key}" if key else "",
            }
        )
        for c in others:
            all_comments.append({**c, "article": articles[-1]["title"], "article_key": key})
    return {
        "ok": True,
        "totals": stats["totals"],
        "articles": articles,
        "comments": all_comments,
    }


# ----------------------------------------------------------------------------
# Threads
# ----------------------------------------------------------------------------
def _threads_replies(post_id: str, token: str) -> list[dict[str, Any]]:
    """投稿への返信本文。権限（threads_read_replies）が無ければ空で返す。"""
    q = urllib.parse.urlencode(
        {"fields": "id,text,username,timestamp", "access_token": token}
    )
    try:
        raw = urllib.request.urlopen(
            f"{THREADS_API_BASE}/{post_id}/replies?{q}", timeout=30
        ).read().decode()
    except (urllib.error.HTTPError, urllib.error.URLError):
        return []
    return [
        {
            "author": r.get("username"),
            "body": (r.get("text") or "").strip(),
            "created_at": r.get("timestamp"),
        }
        for r in json.loads(raw).get("data", [])
    ]


def collect_threads() -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    uid = os.environ.get("META_THREADS_USER_ID", "").strip()
    if not token or not uid:
        return {"ok": False, "reason": "no_token（.env の META_ACCESS_TOKEN / META_THREADS_USER_ID）"}
    try:
        account = fetch_threads_account(uid, token)
    except Exception as exc:  # noqa: BLE001  トークン失効など
        return {"ok": False, "reason": f"account_error: {exc}"}

    posts = []
    replies_all = []
    totals = {"views": 0, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0}
    for p in load_threads_posts():
        ins = fetch_threads_post_insights(p["post_id"], token)
        for k in totals:
            totals[k] += ins.get(k, 0)
        active = sum(ins[m] for m in ACTIVE_METRICS)
        replies = _threads_replies(p["post_id"], token) if ins.get("replies") else []
        posts.append(
            {
                "date": p["date"],
                "theme": p["theme"],
                "post_id": p["post_id"],
                **ins,
                "active": active,
            }
        )
        for r in replies:
            if r["author"] != "hidamarikosodachi":
                replies_all.append({**r, "post_date": p["date"], "theme": p["theme"]})
    totals["active"] = totals["replies"] + totals["reposts"] + totals["quotes"]
    return {
        "ok": True,
        "account": {
            "followers": account.get("followers_count"),
            "profile_views": account.get("views"),
        },
        "totals": totals,
        "posts": sorted(posts, key=lambda x: x["date"]),
        "replies": replies_all,
    }


# ----------------------------------------------------------------------------
# Instagram（API 未接続・手動枠）
# ----------------------------------------------------------------------------
def collect_instagram() -> dict[str, Any]:
    if not MANUAL_IG.exists():
        return {"ok": False, "reason": "未接続（オーナー手動投稿・数字は manual_instagram.json に手入力）"}
    try:
        return {"ok": True, "manual": True, **json.loads(MANUAL_IG.read_text(encoding="utf-8"))}
    except json.JSONDecodeError as exc:
        return {"ok": False, "reason": f"manual_instagram.json 読込失敗: {exc}"}


# ----------------------------------------------------------------------------
# history / dashboard
# ----------------------------------------------------------------------------
def _load_history() -> list[dict[str, Any]]:
    if not HISTORY.exists():
        return []
    rows = []
    for line in HISTORY.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _save_history(snapshot: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [r for r in _load_history() if r["date"] != snapshot["date"]]  # 同日は上書き
    rows.append(snapshot)
    HISTORY.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )


def _summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    """history に残す軽量サマリ（本文は残さない）。"""
    n, t = snapshot["note"], snapshot["threads"]
    return {
        "date": snapshot["date"],
        "note": (
            {"pv": n["totals"]["pv"], "like": n["totals"]["like"], "comment": n["totals"]["comment"],
             "articles": len(n["articles"]), "unreplied": sum(a["unreplied"] for a in n["articles"])}
            if n.get("ok") else None
        ),
        "threads": (
            {**t["totals"], "followers": t["account"]["followers"],
             "profile_views": t["account"]["profile_views"], "posts": len(t["posts"])}
            if t.get("ok") else None
        ),
    }


def _delta(cur: int | None, prev: int | None) -> str:
    if cur is None or prev is None:
        return ""
    d = cur - prev
    return f"（{'+' if d >= 0 else ''}{d}）"


def _short(s: str, n: int = 36) -> str:
    s = " ".join(s.split())  # 改行を潰す（表・引用行を壊さない）
    return s if len(s) <= n else s[: n - 1] + "…"


def render_dashboard(snapshot: dict[str, Any], prev: dict[str, Any] | None) -> str:
    n, t, ig = snapshot["note"], snapshot["threads"], snapshot["instagram"]
    pn = (prev or {}).get("note") or {}
    pt = (prev or {}).get("threads") or {}
    prev_date = (prev or {}).get("date", "—")
    L: list[str] = []
    L += [
        "---",
        "tags: [insights, kpi, observation]",
        "status: active",
        f"updated: {snapshot['date']}",
        "updated_by: scripts/insights_all.py（自動生成・手編集しない）",
        "related: [[this_week]] [[backlog]] [[posting_schedule]]",
        "---",
        "",
        "# 📊 反応ダッシュボード（全サイト・read-only）",
        "",
        f"> 集計 {snapshot['collected_at']}" + (f"／前回比は {prev_date} 集計との差。" if prev else "／初回集計（前回比なし）。"),
        "> 再集計: `.venv/bin/python scripts/insights_all.py`。推移の真実源は `history.jsonl`。",
        "",
        "## サイト別サマリ",
        "",
        "| サイト | 到達 | いいね | コメント/返信 | 能動反応 | 未返信 | フォロワー |",
        "|---|---|---|---|---|---|---|",
    ]
    if n.get("ok"):
        unrep = sum(a["unreplied"] for a in n["articles"])
        L.append(
            f"| note | PV {n['totals']['pv']}{_delta(n['totals']['pv'], pn.get('pv'))} "
            f"| {n['totals']['like']}{_delta(n['totals']['like'], pn.get('like'))} "
            f"| {n['totals']['comment']}{_delta(n['totals']['comment'], pn.get('comment'))} "
            f"| — | **{unrep}** | — |"
        )
    else:
        L.append(f"| note | ⚠️ {n.get('reason')} | | | | | |")
    if t.get("ok"):
        tt, ac = t["totals"], t["account"]
        L.append(
            f"| Threads | views {tt['views']}{_delta(tt['views'], pt.get('views'))} "
            f"| {tt['likes']}{_delta(tt['likes'], pt.get('likes'))} "
            f"| {tt['replies']}{_delta(tt['replies'], pt.get('replies'))} "
            f"| {tt['active']}{_delta(tt['active'], pt.get('active'))} "
            f"| — | {ac['followers']}{_delta(ac['followers'], pt.get('followers'))} |"
        )
    else:
        L.append(f"| Threads | ⚠️ {t.get('reason')} | | | | | |")
    if ig.get("ok"):
        L.append(
            f"| Instagram（手入力 {ig.get('as_of', '?')}） | {ig.get('reach', '—')} | {ig.get('likes', '—')} "
            f"| {ig.get('comments', '—')} | — | — | {ig.get('followers', '—')} |"
        )
    else:
        L.append(f"| Instagram | ⚪ {ig.get('reason')} | | | | | |")

    # KPI
    if n.get("ok"):
        pv = n["totals"]["pv"]
        L += [
            "",
            f"**KPI（note 総PV）**: 基準 {KPI_BASELINE} → 目標 {KPI_TARGET_LOW}〜{KPI_TARGET_HIGH}／現在 **{pv}**"
            f"（目標下限まで残り {max(0, KPI_TARGET_LOW - pv)}）",
        ]

    # note 記事別
    if n.get("ok"):
        L += ["", "## note 記事別", "", "| PV | スキ | コメ | 未返信 | 記事 |", "|---|---|---|---|---|"]
        for a in n["articles"]:
            L.append(
                f"| {a['pv']} | {a['like']} | {a['comment']} | {'**' + str(a['unreplied']) + '**' if a['unreplied'] else 0} "
                f"| [{_short(a['title'])}]({a['url']}) |"
            )

    # Threads 投稿別
    if t.get("ok"):
        L += [
            "", "## Threads 投稿別", "",
            "| 日付 | views | like | 返信 | RP | 引用 | 能動 | テーマ |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for p in t["posts"]:
            L.append(
                f"| {p['date']} | {p['views']} | {p['likes']} | {p['replies']} | {p['reposts']} "
                f"| {p['quotes']} | {p['active']} | {_short(p['theme'], 30)} |"
            )

    # コメント一覧
    L += ["", "## コメント・返信（他者分・新しい順）", ""]
    items: list[tuple[str, str]] = []
    if n.get("ok"):
        for c in n["comments"]:
            flag = "" if c["replied"] else " **⬜未返信**"
            items.append(
                (c["created_at"] or "",
                 f"- **note** {(c['created_at'] or '')[:10]} @{c['author_urlname']}（{c['author']}）"
                 f" → 「{_short(c['article'], 24)}」{flag}\n  > {_short(c['body'], 120)}")
            )
    if t.get("ok"):
        for r in t["replies"]:
            items.append(
                (r["created_at"] or "",
                 f"- **Threads** {(r['created_at'] or '')[:10]} @{r['author']} → {_short(r['theme'], 24)}\n"
                 f"  > {_short(r['body'], 120)}")
            )
    if items:
        L += [s for _, s in sorted(items, key=lambda x: x[0], reverse=True)]
    else:
        L.append("（まだありません）")

    # 推移
    hist = _load_history()
    if len(hist) >= 2:
        L += ["", "## 推移（history.jsonl）", "", "| 集計日 | note PV | note スキ | note コメ | Threads views | Threads 能動 | フォロワー |", "|---|---|---|---|---|---|---|"]
        for h in hist[-12:]:
            hn, ht = h.get("note") or {}, h.get("threads") or {}
            L.append(
                f"| {h['date']} | {hn.get('pv', '—')} | {hn.get('like', '—')} | {hn.get('comment', '—')} "
                f"| {ht.get('views', '—')} | {ht.get('active', '—')} | {ht.get('followers', '—')} |"
            )
    return "\n".join(L) + "\n"


@click.command(help="note / Threads / Instagram(手動) の反応を横断集計する（read-only）。")
@click.option("--json", "as_json", is_flag=True, help="集計結果を JSON で標準出力")
@click.option("--no-save", is_flag=True, help="history / dashboard に保存しない")
def main(as_json: bool, no_save: bool) -> None:
    now = datetime.now(JST)
    snapshot = {
        "date": now.strftime("%Y-%m-%d"),
        "collected_at": now.strftime("%Y-%m-%d %H:%M JST"),
        "note": collect_note(),
        "threads": collect_threads(),
        "instagram": collect_instagram(),
    }
    hist = _load_history()
    prev = next((h for h in reversed(hist) if h["date"] != snapshot["date"]), None)

    if as_json:
        click.echo(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        n, t = snapshot["note"], snapshot["threads"]
        click.echo(f"=== 反応集計 {snapshot['collected_at']} ===")
        if n.get("ok"):
            unrep = sum(a["unreplied"] for a in n["articles"])
            click.echo(f"note   : PV {n['totals']['pv']} / スキ {n['totals']['like']} / コメント {n['totals']['comment']}（未返信 {unrep}）")
        else:
            click.echo(f"note   : ⚠️ {n.get('reason')}")
        if t.get("ok"):
            tt = t["totals"]
            click.echo(f"Threads: views {tt['views']} / like {tt['likes']} / 返信 {tt['replies']} / 能動 {tt['active']} / フォロワー {t['account']['followers']}")
        else:
            click.echo(f"Threads: ⚠️ {t.get('reason')}")
        ig = snapshot["instagram"]
        click.echo(f"IG     : {'手入力 ' + str(ig.get('as_of')) if ig.get('ok') else '⚪ ' + ig.get('reason', '')}")

    if no_save:
        return
    _save_history(_summary(snapshot))
    DASHBOARD.write_text(render_dashboard(snapshot, prev), encoding="utf-8")
    click.echo(f"→ {DASHBOARD.relative_to(PROJECT_ROOT)} / {HISTORY.relative_to(PROJECT_ROOT)} を更新")


if __name__ == "__main__":
    main()
