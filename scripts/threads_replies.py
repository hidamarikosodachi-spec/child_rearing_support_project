#!/usr/bin/env python3
"""自分の Threads 投稿に付いたコメントを一覧し、返信する（ガードレール付き）。

    .venv/bin/python scripts/threads_replies.py list                     # 未返信コメントの一覧（read-only）
    .venv/bin/python scripts/threads_replies.py reply --to <comment_id> --text "..."          # dry-run
    .venv/bin/python scripts/threads_replies.py reply --to <comment_id> --text "..." --commit # 実投稿

ガードレール（note の接触コメントと同じ思想・外さない）:
  - 返信先は「自分の投稿に付いたコメント」だけ（他者の投稿には返信しない）
  - 1日 5 件まで
  - 売り込み語（URL・note・記事・連載・診断・ぜひ・よかったら・フォロー）を含む本文は拒否
  - 全操作ログ: .auth/threads_reply_log.jsonl
  - 緊急停止: .auth/STOP_THREADS_REPLIES を置くと全停止
  - --commit 無しは dry-run
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from post_threads import post_to_threads  # noqa: E402

API = "https://graph.threads.net/v1.0"
POSTED = ROOT / "docs" / "posted_log" / "threads.jsonl"
LOG = ROOT / ".auth" / "threads_reply_log.jsonl"
STOP = ROOT / ".auth" / "STOP_THREADS_REPLIES"
DAILY_MAX = 5
NG_WORDS = ["http", "note", "記事", "連載", "診断", "ぜひ", "よかったら", "フォロー", "プロフィール"]
JST = timezone(timedelta(hours=9))


def _log_rows() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]


def _append_log(row: dict) -> None:
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _env() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    return os.environ["META_ACCESS_TOKEN"], os.environ["META_THREADS_USER_ID"]


def _own_posts(days: int = 14) -> list[dict]:
    since = datetime.now(JST) - timedelta(days=days)
    out = []
    for l in POSTED.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r.get("platform") != "threads" or not r.get("post_id"):
            continue
        try:
            t = datetime.fromisoformat(r["posted_at"]).astimezone(JST)
        except Exception:
            continue
        if t >= since:
            out.append(r)
    return out


@click.group()
def cli() -> None:
    pass


@cli.command("list")
@click.option("--days", default=14, help="さかのぼる日数")
def list_cmd(days: int) -> None:
    token, uid = _env()
    me = requests.get(f"{API}/me", params={"fields": "username", "access_token": token}, timeout=30).json().get("username")
    replied = {r["to"] for r in _log_rows() if r.get("committed")}
    n = 0
    for p in _own_posts(days):
        r = requests.get(
            f"{API}/{p['post_id']}/replies",
            params={"fields": "id,text,username,timestamp", "access_token": token},
            timeout=30,
        )
        if r.status_code != 200:
            print(f"取得失敗 {p['date']} status={r.status_code} {r.text[:120]}")
            continue
        for c in r.json().get("data", []):
            if c.get("username") == me or c["id"] in replied:
                continue
            n += 1
            print(f"[{p['date']}] comment_id={c['id']} @{c.get('username')}\n  {c.get('text','')[:200]}")
    print(f"未返信 {n} 件")


@cli.command("reply")
@click.option("--to", "to_id", required=True, help="返信先のコメント ID（自分の投稿に付いたもの）")
@click.option("--text", required=True)
@click.option("--commit", is_flag=True)
def reply_cmd(to_id: str, text: str, commit: bool) -> None:
    if STOP.exists():
        raise click.ClickException("STOP_THREADS_REPLIES があります。全停止中。")
    bad = [w for w in NG_WORDS if w in text]
    if bad:
        raise click.ClickException(f"売り込み語を含むため拒否: {bad}")
    if len(text) > 200:
        raise click.ClickException("200字以内にしてください")
    token, uid = _env()
    today = datetime.now(JST).date().isoformat()
    done = [r for r in _log_rows() if r.get("committed") and r.get("date") == today]
    if len(done) >= DAILY_MAX:
        raise click.ClickException(f"1日の上限 {DAILY_MAX} 件に達しています")
    # 返信先が自分の投稿に付いたコメントであることを確認する
    r = requests.get(f"{API}/{to_id}", params={"fields": "id,username,root_post", "access_token": token}, timeout=30)
    if r.status_code != 200:
        raise click.ClickException(f"返信先を確認できません: {r.status_code} {r.text[:150]}")
    root = (r.json().get("root_post") or {}).get("id")
    own_ids = {p["post_id"] for p in _own_posts(60)}
    if root not in own_ids:
        raise click.ClickException("返信先が自分の投稿のスレッドではありません。拒否。")
    print(f"返信先 @{r.json().get('username')} / 本文: {text}")
    if not commit:
        print("[dry-run] 実投稿しません。--commit で投稿。")
        return
    res = post_to_threads(text, access_token=token, user_id=uid, reply_to_id=to_id)
    _append_log({"ts": datetime.now(JST).isoformat(), "date": today, "to": to_id, "text": text, "committed": True, "post_id": res.get("post_id")})
    print(f"[OK] post_id={res.get('post_id')}")


if __name__ == "__main__":
    cli()
