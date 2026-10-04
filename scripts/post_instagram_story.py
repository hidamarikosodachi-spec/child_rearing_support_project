#!/usr/bin/env python3
"""Instagram のストーリーを投稿する（Instagram ログイン方式・`graph.instagram.com`）。

2026-10-04 に実地検証して通ることを確認した。Facebook ページは不要
（6月に「不可」と判断したのは旧方式＝Facebook ログインの話で、いまは別経路）。

できないこと（仕様・回避不能）:
  **リンクスタンプは API では貼れない。** タップで記事へ飛ばす導線は作れないので、
  画像側に「プロフィールのリンクから」と書いておき、プロフィールのリンクで受ける。

    .venv/bin/python scripts/post_instagram_story.py --image https://…/x.png          # dry-run
    .venv/bin/python scripts/post_instagram_story.py --image https://…/x.png --commit
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
HOST = os.environ.get("META_GRAPH_HOST", "https://graph.instagram.com")
VER = "v21.0"
LOG = ROOT / ".auth" / "instagram_post_log.jsonl"


def _env() -> tuple[str, str]:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and line.startswith("META_INSTAGRAM_"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    tok = os.environ.get("META_INSTAGRAM_TOKEN", "").strip()
    uid = os.environ.get("META_INSTAGRAM_USER_ID", "").strip()
    if not tok or not uid:
        raise click.ClickException("META_INSTAGRAM_TOKEN / META_INSTAGRAM_USER_ID が未設定です")
    return tok, uid


def _call(path: str, data: dict) -> dict:
    tok, _ = _env()
    body = urllib.parse.urlencode({**data, "access_token": tok}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{HOST}/{VER}/{path}", data=body), timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def publish_story(image_url: str) -> dict:
    _, uid = _env()
    res = _call(f"{uid}/media", {"media_type": "STORIES", "image_url": image_url})
    if "id" not in res:
        raise click.ClickException(f"コンテナ作成に失敗: {res.get('error', res)}")
    time.sleep(5)
    pub = _call(f"{uid}/media_publish", {"creation_id": res["id"]})
    if "id" not in pub:
        raise click.ClickException(f"公開に失敗: {pub.get('error', pub)}")
    q = urllib.parse.urlencode({"fields": "permalink,timestamp", "access_token": _env()[0]})
    with urllib.request.urlopen(f"{HOST}/{VER}/{pub['id']}?{q}", timeout=30) as r:
        info = json.loads(r.read().decode())
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "action": "story",
                            "media_id": pub["id"], "image": image_url,
                            "permalink": info.get("permalink")}, ensure_ascii=False) + "\n")
    return {**pub, **info}


@click.command(help="Instagram ストーリーを投稿する（--commit 無しは dry-run）。")
@click.option("--image", "image_url", required=True, help="画像の公開URL（1080x1920 推奨）")
@click.option("--commit", is_flag=True, help="付けると実投稿")
def main(image_url: str, commit: bool) -> None:
    click.echo(f"画像: {image_url}")
    click.echo("※ リンクスタンプは API では貼れません（画像内の案内＋プロフィールのリンクで受けます）")
    if not commit:
        click.echo("[dry-run] 投稿していません。--commit で実行します。")
        return
    info = publish_story(image_url)
    click.echo(f"[OK] ストーリーを投稿しました（24時間で消えます）\n  {info.get('permalink')}")


if __name__ == "__main__":
    main()
