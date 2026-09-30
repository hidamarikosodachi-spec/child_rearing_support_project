#!/usr/bin/env python3
"""Instagram の投稿に付いたコメントを読み、返信する（Instagram ログイン方式）。

背景:
  Instagram はこれまで全チャネル中いちばん反応率がよい（2026-09-28 のカルーセルで
  コメント1件・パパ層から）。返信は速いほど効くが、これまで手作業だった。

方式:
  Instagram API with Instagram Login（Facebookページ不要・`graph.instagram.com`）。
  必要な権限: instagram_business_basic / instagram_business_manage_comments

    # 未返信のコメントを一覧（read-only）
    .venv/bin/python scripts/instagram_comments.py list
    # 返信（--commit 無しは dry-run）
    .venv/bin/python scripts/instagram_comments.py reply --id <comment_id> --text "..." --commit

安全側の設計:
  - `--commit` を付けない限り書き込まない
  - 自分のコメントには返信しない（自己会話を防ぐ）
  - 返信は1回の実行で最大3件（連投による凍結リスクを避ける）
  - 全操作を .auth/instagram_comment_log.jsonl に記録
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / ".auth" / "instagram_comment_log.jsonl"
HOST = os.environ.get("META_GRAPH_HOST", "https://graph.instagram.com")
VER = "v21.0"
MAX_REPLIES_PER_RUN = 3


def _env() -> tuple[str, str]:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and line.startswith("META_INSTAGRAM_"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    tok = os.environ.get("META_INSTAGRAM_TOKEN", "").strip()
    uid = os.environ.get("META_INSTAGRAM_USER_ID", "").strip()
    if not tok or not uid:
        raise click.ClickException(
            "META_INSTAGRAM_TOKEN / META_INSTAGRAM_USER_ID が未設定です。\n"
            "→ docs/instagram/auto_post_setup.md の手順でトークンを取得してください。")
    return tok, uid


def _get(path: str, params: dict) -> dict:
    tok, _ = _env()
    params = {**params, "access_token": tok}
    url = f"{HOST}/{VER}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def _post(path: str, data: dict) -> dict:
    tok, _ = _env()
    body = urllib.parse.urlencode({**data, "access_token": tok}).encode()
    req = urllib.request.Request(f"{HOST}/{VER}/{path}", data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _log(rec: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    rec["ts"] = datetime.now().astimezone().isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


@click.group(help="Instagram のコメントを読む／返信する。")
def cli() -> None:
    pass


@cli.command("list", help="直近の投稿に付いたコメントを表示する（読み取りのみ）。")
@click.option("--limit", default=10, help="見る投稿数")
def list_comments(limit: int) -> None:
    _, uid = _env()
    me = _get(f"{uid}", {"fields": "username"})
    media = _get(f"{uid}/media", {
        "fields": "id,caption,permalink,timestamp,comments_count", "limit": limit})
    total = 0
    for m in media.get("data", []):
        if not m.get("comments_count"):
            continue
        cs = _get(f"{m['id']}/comments", {
            "fields": "id,text,username,timestamp,replies{id,username,text}"})
        for c in cs.get("data", []):
            if c.get("username") == me.get("username"):
                continue  # 自分のコメントは対象外
            replied = any(r.get("username") == me.get("username")
                          for r in (c.get("replies", {}).get("data") or []))
            total += 1
            mark = "✅返信済" if replied else "🔴未返信"
            click.echo(f"\n{mark}  @{c.get('username')}  {c.get('timestamp','')[:10]}")
            click.echo(f"  {c.get('text','')}")
            click.echo(f"  comment_id: {c['id']}")
            click.echo(f"  投稿: {m.get('permalink')}")
    click.echo(f"\n他者コメント {total} 件")


@cli.command("reply", help="コメントに返信する（--commit 無しは dry-run）。")
@click.option("--id", "comment_id", required=True, help="コメントID（list で確認）")
@click.option("--text", required=True, help="返信本文")
@click.option("--commit", is_flag=True, help="付けると実際に投稿する")
def reply(comment_id: str, text: str, commit: bool) -> None:
    if len(text) > 2200:
        raise click.ClickException("返信が長すぎます（2200字まで）")
    today = datetime.now().astimezone().date().isoformat()
    done = 0
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("action") == "reply" and r.get("ok") and r.get("ts", "").startswith(today):
                done += 1
    if done >= MAX_REPLIES_PER_RUN:
        raise click.ClickException(f"本日の返信上限（{MAX_REPLIES_PER_RUN}件）に達しています")

    click.echo(f"--- 返信内容 ---\n{text}\n----------------")
    if not commit:
        click.echo("[dry-run] 送信していません。--commit で実行します。")
        return
    res = _post(f"{comment_id}/replies", {"message": text})
    _log({"action": "reply", "ok": True, "comment_id": comment_id,
          "reply_id": res.get("id"), "text": text})
    click.echo(f"[OK] 返信しました id={res.get('id')}")


if __name__ == "__main__":
    cli()
