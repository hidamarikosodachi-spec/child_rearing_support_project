#!/usr/bin/env python3
"""その日のリールを1本だけ投稿する（予約投稿・毎日運用の心臓部）。

オーナー指示（2026-10-06）: **Instagram も毎日投稿する**。
1本ずつ手で投げていては続かないので、**週1でまとめて作り、毎朝1本ずつ自動で出す**。

仕組み:
  `docs/instagram/reels/*.md` の front-matter に `publish_on: YYYY-MM-DD` と `slug` を書く。
  動画は先に `web/ig/reels/<slug>.mp4` へ置いてデプロイしておく（公開URLが必要なため）。
  このスクリプトは **その日に予約された1本だけ**を投稿する。

    .venv/bin/python scripts/post_instagram_queue.py            # dry-run（今日の対象を表示）
    .venv/bin/python scripts/post_instagram_queue.py --commit   # 実投稿
    .venv/bin/python scripts/post_instagram_queue.py --date 2026-10-08 --commit

安全側:
  - **1日1本まで**（同日の投稿ログがあれば止める）
  - 動画URLが 200 を返さなければ投稿しない
  - 既存投稿との重複チェック（post_instagram_reel.check_duplicate）を通す
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
QUEUE = ROOT / "docs/instagram/reels"
LOG = ROOT / ".auth" / "instagram_post_log.jsonl"
SITE = "https://hidamari-kosodachi.com"
JST = dt.timezone(dt.timedelta(hours=9))


def _fm(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}, raw
    fm, body = raw.split("---", 2)[1], raw.split("---", 2)[2]
    meta = {}
    for line in fm.splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.split("#")[0].strip().strip('"')
    return meta, body


def _posted_today(day: str) -> bool:
    if not LOG.exists():
        return False
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if r.get("action") in ("reel", "story_skip") and r.get("ts", "").startswith(day):
            if r.get("action") == "reel":
                return True
    return False


@click.command(help="その日に予約されたリールを1本だけ投稿する（--commit 無しは dry-run）。")
@click.option("--date", "day", default="", help="対象日（既定: 今日・JST）")
@click.option("--commit", is_flag=True, help="付けると実投稿")
def main(day: str, commit: bool) -> None:
    day = day or dt.datetime.now(JST).date().isoformat()
    targets = []
    for f in sorted(QUEUE.glob("*.md")):
        meta, _ = _fm(f)
        if meta.get("publish_on") == day:
            targets.append((f, meta))
    if not targets:
        click.echo(f"{day}: 予約されたリールはありません（何もしません）")
        return
    if len(targets) > 1:
        raise click.ClickException(f"{day} に {len(targets)} 本が予約されています。1日1本にしてください")

    path, meta = targets[0]
    slug = meta.get("slug") or path.stem
    video = f"{SITE}/ig/reels/{slug}.mp4"
    click.echo(f"{day} の1本: {meta.get('title', path.stem)}\n  {video}")

    if _posted_today(day):
        click.echo("[skip] 本日はすでにリールを投稿しています（1日1本）")
        return
    # HEAD は Cloudflare に 403 で弾かれるため、先頭1バイトだけ GET して存在を確かめる。
    try:
        req = urllib.request.Request(video, headers={
            "Range": "bytes=0-1",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status not in (200, 206):
                raise click.ClickException(f"動画が公開されていません（HTTP {r.status}）: {video}")
    except Exception as e:  # noqa: BLE001
        raise click.ClickException(f"動画URLを確認できません: {e}")

    import post_instagram_reel as reel
    caption = reel.caption_from(path)
    for w in (dups := reel.check_duplicate(caption, video)):
        click.echo(f"[重複の疑い] {w}")
    if dups:
        raise click.ClickException("過去の投稿と重なります。中身を変えてください。")

    click.echo(f"キャプション（{len(caption)}字）:\n---\n{caption[:300]}\n---")
    if not commit:
        click.echo("[dry-run] 投稿していません。--commit で実行します。")
        return

    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "scripts/post_instagram_reel.py"),
                        "--video", video, "--caption-file", str(path), "--commit"],
                       text=True)
    if r.returncode != 0:
        raise click.ClickException("投稿に失敗しました")


if __name__ == "__main__":
    main()
