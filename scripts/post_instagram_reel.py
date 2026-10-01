#!/usr/bin/env python3
"""Instagram にリールを投稿する（Instagram ログイン方式・`graph.instagram.com`）。

オーナー方針（2026-10-01）: **Instagram はリールを基本形式にする**（文章・カルーセルより回るため）。

前提:
  - 動画は**公開URL**に置く（Cloudflare Pages の `web/ig/reels/` に置けば配信される）
  - 1080x1920・3〜90秒・MP4(h264/aac) 推奨
  - 権限 `instagram_business_content_publish`

    # 動画をサイトに置いてURLを得る（デプロイが必要）
    cp assets/reels/<name>.mp4 web/ig/reels/
    cd web && npx wrangler pages deploy . --project-name hidamari-kosodachi --commit-dirty=true

    # dry-run（コンテナも作らない）
    .venv/bin/python scripts/post_instagram_reel.py --video <URL> --caption-file <md>
    # 実投稿
    .venv/bin/python scripts/post_instagram_reel.py --video <URL> --caption-file <md> --commit

注意（正直に）:
  API から投稿したリールには **Instagram の音源ライブラリ（流行の音）を付けられない**。
  音は動画に焼き込んだものだけになる。流行音の後押しが要る回は、アプリから手で投稿する。
"""
from __future__ import annotations

import json
import os
import re
import sys
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


def _post(path: str, data: dict) -> dict:
    tok, _ = _env()
    body = urllib.parse.urlencode({**data, "access_token": tok}).encode()
    req = urllib.request.Request(f"{HOST}/{VER}/{path}", data=body)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def _get(path: str, params: dict) -> dict:
    tok, _ = _env()
    q = urllib.parse.urlencode({**params, "access_token": tok})
    try:
        with urllib.request.urlopen(f"{HOST}/{VER}/{path}?{q}", timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode())


def check_duplicate(caption: str, video_url: str) -> list[str]:
    """過去の投稿と同じ内容でないか確かめる（2026-10-01 に重複投稿をやらかしたため）。

    判定は2つ。(1) 同じ動画ファイルを投稿済みか（ログ）。
    (2) 既存投稿のキャプションと文字の重なりが大きいか（先頭120字の2-gram 一致率）。
    """
    warns: list[str] = []
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("video") == video_url:
                warns.append(f"同じ動画URLを {r.get('ts','?')[:10]} に投稿済み: {r.get('permalink')}")

    def grams(t: str) -> set[str]:
        t = re.sub(r"[\s#\u3000]", "", t)[:120]
        return {t[i:i + 2] for i in range(len(t) - 1)}

    mine = grams(caption)
    if mine:
        _, uid = _env()
        for m in _get(f"{uid}/media", {"fields": "caption,permalink,timestamp", "limit": 25}).get("data", []):
            other = grams(m.get("caption") or "")
            if not other:
                continue
            ratio = len(mine & other) / len(mine)
            if ratio >= 0.5:
                warns.append(f"既存投稿と内容が {ratio:.0%} 重なります（{m.get('timestamp','')[:10]}）: {m.get('permalink')}")
    return warns


def caption_from(md: Path) -> str:
    """台本mdから「## キャプション」節を取り出す。無ければ本文全体。"""
    s = md.read_text(encoding="utf-8")
    m = re.search(r"^##\s*キャプション[^\n]*\n(.+?)(?=\n##\s|\Z)", s, re.S | re.M)
    return (m.group(1) if m else s).strip()


@click.command(help="Instagram にリールを投稿する（--commit 無しは dry-run）。")
@click.option("--video", "video_url", required=True, help="動画の公開URL（https://…/xxx.mp4）")
@click.option("--caption-file", type=click.Path(exists=True, path_type=Path), help="キャプションを含む md")
@click.option("--caption", help="キャプションを直接指定")
@click.option("--cover", help="サムネ画像の公開URL（任意）")
@click.option("--commit", is_flag=True, help="付けると実投稿")
@click.option("--allow-duplicate", is_flag=True, help="重複の疑いがあっても投稿する")
def main(video_url: str, caption_file: Path | None, caption: str | None,
         cover: str | None, commit: bool, allow_duplicate: bool) -> None:
    if not caption and caption_file:
        caption = caption_from(caption_file)
    caption = (caption or "").strip()
    if len(caption) > 2200:
        raise click.ClickException(f"キャプションが長すぎます（{len(caption)}字 / 2200まで）")

    click.echo(f"動画: {video_url}")
    click.echo(f"キャプション（{len(caption)}字）:\n---\n{caption[:400]}\n---")

    for w in (dups := check_duplicate(caption, video_url)):
        click.echo(f"[重複の疑い] {w}")
    if dups and not allow_duplicate:
        raise click.ClickException(
            "過去の投稿と重なります。別の内容にするか、意図的なら --allow-duplicate を付けてください。")

    if not commit:
        click.echo("[dry-run] 投稿していません。--commit で実行します。")
        return

    _, uid = _env()
    params = {"media_type": "REELS", "video_url": video_url, "caption": caption}
    if cover:
        params["cover_url"] = cover
    res = _post(f"{uid}/media", params)
    if "id" not in res:
        raise click.ClickException(f"コンテナ作成に失敗: {res.get('error', res)}")
    cid = res["id"]
    click.echo(f"コンテナ作成: {cid}（動画の処理を待ちます…）")

    for i in range(40):  # 最大約4分
        time.sleep(6)
        st = _get(cid, {"fields": "status_code,status"})
        code = st.get("status_code")
        click.echo(f"  {i*6+6}秒: {code}")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise click.ClickException(f"動画の処理に失敗: {st.get('status')}")
    else:
        raise click.ClickException("処理が終わりませんでした（時間をおいて再実行）")

    pub = _post(f"{uid}/media_publish", {"creation_id": cid})
    if "id" not in pub:
        raise click.ClickException(f"公開に失敗: {pub.get('error', pub)}")
    media_id = pub["id"]
    info = _get(media_id, {"fields": "permalink,media_type,timestamp"})
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "action": "reel",
                            "media_id": media_id, "video": video_url,
                            "permalink": info.get("permalink")}, ensure_ascii=False) + "\n")
    click.echo(f"[OK] 投稿しました\n  {info.get('permalink')}")


if __name__ == "__main__":
    main()
