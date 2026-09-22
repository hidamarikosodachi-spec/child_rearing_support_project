#!/usr/bin/env python3
"""投稿済み Threads 投稿に「1返信目のリンク導線」を後付けする（T101・後追い用）。

通常は post_threads.py が投稿直後に自動で返信を付ける（ドラフト front-matter `reply:`）。
本スクリプトは、その仕組み導入前に飛んだ投稿や、返信だけ失敗した投稿への後追い用。

    python3 scripts/threads_reply_link.py --date 2026-09-22            # dry-run
    python3 scripts/threads_reply_link.py --date 2026-09-22 --commit   # 実投稿

冪等: posted_log の当該行に reply_post_id があればスキップ。成功時は同行に reply_post_id を追記。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from lib.draft_loader import load_drafts  # noqa: E402
from post_threads import post_to_threads  # noqa: E402

LOG = PROJECT_ROOT / "docs" / "posted_log" / "threads.jsonl"


@click.command(help="投稿済み Threads 投稿へ 1返信目のリンク導線を後付けする。")
@click.option("--date", required=True, help="対象日付（YYYY-MM-DD）")
@click.option("--commit", is_flag=True, help="付けると実投稿。無いと dry-run。")
def main(date: str, commit: bool) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    targets = [r for r in rows if r.get("date") == date and r.get("platform") == "threads"]
    if not targets:
        raise click.ClickException(f"posted_log に {date} の投稿がありません（まだ飛んでいない？）")
    drafts = {str(d.path.relative_to(PROJECT_ROOT)): d for d in load_drafts("threads", date)}

    changed = False
    for r in targets:
        d = drafts.get(r["draft_path"])
        reply = (d.frontmatter.get("reply") or "").strip() if d else ""
        if not reply:
            click.echo(f"[SKIP] {r['draft_path']}: front-matter に reply が無い"); continue
        if r.get("reply_post_id"):
            click.echo(f"[SKIP] {r['draft_path']}: 返信済み reply_post_id={r['reply_post_id']}"); continue
        click.echo(f"--- {r['draft_path']} (post_id={r['post_id']}) ---\n{reply}\n")
        if not commit:
            continue
        rep = post_to_threads(
            reply,
            access_token=os.environ["META_ACCESS_TOKEN"],
            user_id=os.environ["META_THREADS_USER_ID"],
            reply_to_id=r["post_id"],
        )
        r["reply_post_id"] = rep["post_id"]
        changed = True
        click.echo(f"[OK] reply_post_id={rep['post_id']}")

    if changed:
        LOG.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        click.echo("posted_log に reply_post_id を追記")
    elif not commit:
        click.echo("(dry-run: --commit で実投稿)")


if __name__ == "__main__":
    main()
