"""
==============================================================================
Threads 自動投稿スクリプト
------------------------------------------------------------------------------
用途:
    docs/drafts/threads/YYYY-MM-DD*.md のうち frontmatter で
    approved=true のものを Meta Threads API 経由で投稿する。

前提:
    - Meta for Developers でアプリを登録し、長期アクセストークンを取得済み
    - Threads ユーザー ID を取得済み（``GET /me`` から）
    - Threads API: https://developers.facebook.com/docs/threads
    - 2段階処理: (1) メディアコンテナ作成 → (2) 公開

実行例:
    # dry-run（実投稿なし、プレビューのみ）
    python scripts/post_threads.py --date 2026-05-14

    # 実投稿
    python scripts/post_threads.py --date 2026-05-14 --commit

関連 .env キー:
    META_ACCESS_TOKEN
    META_THREADS_USER_ID
    LOG_LEVEL (optional)
==============================================================================
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv

# プロジェクトルートを sys.path に追加（直接実行に対応）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lib.draft_loader import (  # noqa: E402
    Draft,
    configure_logging,
    load_drafts,
    log_post,
    print_dry_run_notice,
    truncate_for_log,
)


logger = logging.getLogger("post_threads")


THREADS_API_BASE = "https://graph.threads.net/v1.0"
THREADS_MAX_CHARS = 500


def build_post_text(draft: Draft) -> str:
    """ドラフトから Threads 投稿用の本文を組み立てる。

    Args:
        draft: 対象ドラフト。

    Returns:
        ハッシュタグ付与済みの本文文字列（500字に切り詰め）。
    """
    body = draft.body.strip()
    tags = draft.hashtags
    if tags:
        tag_line = " ".join(f"#{t}" for t in tags)
        body = f"{body}\n\n{tag_line}".strip()
    if len(body) > THREADS_MAX_CHARS:
        logger.warning(
            "本文が500字を超過したため切り詰めます: %d -> %d",
            len(body),
            THREADS_MAX_CHARS,
        )
        body = body[: THREADS_MAX_CHARS - 1] + "…"
    return body


def post_to_threads(
    text: str, *, access_token: str, user_id: str, reply_to_id: str | None = None
) -> dict[str, Any]:
    """Meta Threads API で実投稿する（2段階）。

    Args:
        text: 投稿本文。
        access_token: 長期アクセストークン。
        user_id: Threads ユーザー ID。
        reply_to_id: 指定すると、その投稿への返信として投稿する（自己返信でリンク導線を置く用途）。

    Returns:
        ``{"container_id": ..., "post_id": ...}`` を含む辞書。
    """
    import requests  # 遅延 import（dry-run のみのケースで未導入でも動くように）

    # 1) メディアコンテナ作成
    create_url = f"{THREADS_API_BASE}/{user_id}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token,
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id
    logger.info("メディアコンテナ作成: POST %s", create_url)
    r = requests.post(create_url, data=params, timeout=30)
    logger.info("create status=%s body=%s", r.status_code, r.text)
    r.raise_for_status()
    container_id = r.json().get("id")
    if not container_id:
        raise RuntimeError(f"container_id を取得できません: {r.text}")

    # API 推奨: 数秒待ってから publish
    time.sleep(2.0)

    # 2) 公開
    publish_url = f"{THREADS_API_BASE}/{user_id}/threads_publish"
    pub_params = {
        "creation_id": container_id,
        "access_token": access_token,
    }
    logger.info("公開: POST %s", publish_url)
    r2 = requests.post(publish_url, data=pub_params, timeout=30)
    logger.info("publish status=%s body=%s", r2.status_code, r2.text)
    r2.raise_for_status()
    post_id = r2.json().get("id")
    if not post_id:
        raise RuntimeError(f"post_id を取得できません: {r2.text}")

    return {"container_id": container_id, "post_id": post_id}


def _get_required_env(name: str) -> str:
    """必須環境変数を取得。未設定なら案内付きエラー。"""
    v = os.environ.get(name, "").strip()
    if not v:
        raise click.ClickException(
            f"環境変数 {name} が未設定です。`.env` を作成し値を入れてください。"
            f"（テンプレ: .env.example）"
        )
    return v


def _already_posted_paths() -> set[str]:
    """posted_log から投稿済みの draft_path 集合を読む（冪等化＝二重投稿防止）。

    定期実行(cron)で同じ承認済みドラフトを毎日叩いても再投稿しないために使う。

    Returns:
        投稿済みドラフトの相対パス文字列の集合。ログが無ければ空集合。
    """
    import json

    log_path = PROJECT_ROOT / "docs" / "posted_log" / "threads.jsonl"
    posted: set[str] = set()
    if not log_path.exists():
        return posted
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        dp = rec.get("draft_path")
        if dp and rec.get("post_id"):
            posted.add(dp)
    return posted


@click.command(help="Threads に承認済みドラフトを投稿する。")
@click.option(
    "--date",
    "date",
    required=True,
    help="対象日付（YYYY-MM-DD）。例: 2026-05-14",
)
@click.option(
    "--commit",
    is_flag=True,
    default=False,
    help="このフラグを付けると実投稿。無いと dry-run。",
)
def main(date: str, commit: bool) -> None:
    """CLI エントリポイント。"""
    load_dotenv(PROJECT_ROOT / ".env")
    configure_logging(os.environ.get("LOG_LEVEL"))

    drafts = load_drafts("threads", date)
    if not drafts:
        # 「承認済みなし」と「そもそも無い」を区別したい
        all_path = (PROJECT_ROOT / "docs" / "drafts" / "threads").glob(f"{date}*.md")
        if any(all_path):
            click.echo(f"承認済みドラフトなし (date={date})")
        else:
            click.echo(f"該当ドラフトなし (date={date})")
        return

    click.echo(f"=== Threads 投稿 {len(drafts)}件 (date={date}, commit={commit}) ===")

    if not commit:
        # dry-run
        for i, d in enumerate(drafts, 1):
            text = build_post_text(d)
            click.echo(f"\n--- [{i}/{len(drafts)}] {d.path.name} ---")
            click.echo(text)
            click.echo(f"({len(text)}文字)")
            reply_text = (d.frontmatter.get("reply") or "").strip()
            if reply_text:
                click.echo(f"--- 1返信目（リンク導線） ---\n{reply_text}")
        print_dry_run_notice()
        return

    access_token = _get_required_env("META_ACCESS_TOKEN")
    user_id = _get_required_env("META_THREADS_USER_ID")

    posted_paths = _already_posted_paths()

    success = 0
    skipped = 0
    for i, d in enumerate(drafts, 1):
        rel = str(d.path.relative_to(PROJECT_ROOT))
        if rel in posted_paths:
            click.echo(f"[SKIP] {d.path.name}: 投稿済み（posted_log に記録あり）")
            skipped += 1
            continue
        text = build_post_text(d)
        logger.info(
            "[%d/%d] 投稿開始 path=%s preview=%s",
            i,
            len(drafts),
            d.path.name,
            truncate_for_log(text),
        )
        try:
            result = post_to_threads(text, access_token=access_token, user_id=user_id)
            entry: dict[str, Any] = {
                "date": date,
                "draft_path": str(d.path.relative_to(PROJECT_ROOT)),
                "post_id": result["post_id"],
                "container_id": result["container_id"],
                "text_len": len(text),
            }
            # 導線（T101）: front-matter `reply:` があれば 1返信目に note 記事リンクを置く。
            # 本文にリンクを入れるとリーチが落ちる通説への対処。返信失敗は本投稿の成功を妨げない。
            reply_text = (d.frontmatter.get("reply") or "").strip()
            if reply_text:
                try:
                    time.sleep(3.0)
                    rep = post_to_threads(
                        reply_text, access_token=access_token, user_id=user_id,
                        reply_to_id=result["post_id"],
                    )
                    entry["reply_post_id"] = rep["post_id"]
                    click.echo(f"[OK] 返信リンク -> reply_post_id={rep['post_id']}")
                except Exception as exc:  # noqa: BLE001
                    logger.exception("返信リンク投稿失敗: %s", d.path)
                    click.echo(f"[WARN] 返信リンク失敗（本投稿は成功）: {exc}", err=True)
            log_post("threads", entry)
            success += 1
            click.echo(f"[OK] {d.path.name} -> post_id={result['post_id']}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("投稿失敗: %s", d.path)
            click.echo(f"[FAIL] {d.path.name}: {exc}", err=True)

    click.echo(f"\n完了: {success}/{len(drafts)} 件成功 (スキップ {skipped} 件=投稿済み)")

    # 投稿失敗があれば非ゼロ終了する（CI/cron が "緑なのに未投稿" を見逃さないため）。
    # 失敗 = 対象ドラフトのうち、スキップでも成功でもなかったもの。空打ち(0件)は失敗ではない。
    failures = len(drafts) - skipped - success
    if failures > 0:
        click.echo(f"[ERROR] {failures}件の投稿に失敗しました（詳細は上記ログ）。", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
