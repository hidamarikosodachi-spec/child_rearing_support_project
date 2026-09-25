"""
==============================================================================
Instagram 自動投稿スクリプト
------------------------------------------------------------------------------
用途:
    docs/drafts/instagram/YYYY-MM-DD*.md のうち approved=true のものを
    Meta Graph API 経由で Instagram Business アカウントに投稿する。
    画像は Cloudflare R2 にアップロードしてから公開 URL を Meta に渡す。

前提:
    - Instagram Business アカウント切替済み（個人アカウントでは投稿不可）
    - Meta for Developers でアプリ登録 + アプリ審査済み
    - frontmatter の ``image`` または ``images`` に画像パス or URL を指定
    - 単一画像なら2段階、複数画像（カルーセル）なら3段階呼び出し

実行例:
    # dry-run
    python scripts/post_instagram.py --date 2026-05-14

    # 実投稿
    python scripts/post_instagram.py --date 2026-05-14 --commit

関連 .env キー:
    META_ACCESS_TOKEN
    META_INSTAGRAM_BUSINESS_ID
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME, R2_PUBLIC_URL
    LOG_LEVEL (optional)
==============================================================================
"""
from __future__ import annotations

import logging
import re
import os
import sys
import time
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv

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
from scripts.lib.r2_uploader import upload_if_local  # noqa: E402


logger = logging.getLogger("post_instagram")


GRAPH_API_BASE = "https://graph.facebook.com/v20.0"
IG_CAPTION_MAX = 2200
CONTAINER_POLL_INTERVAL = 3
CONTAINER_POLL_MAX = 20  # 約60秒


def build_caption(draft: Draft) -> str:
    """ドラフトから Instagram キャプションを組み立てる。

    Args:
        draft: 対象ドラフト。

    Returns:
        ハッシュタグ付与済みキャプション。
    """
    body = draft.body.strip()
    # ドラフトはスライド原稿・注意書き・キャプションを1ファイルに持つ。
    # 「## キャプション（投稿本文）」があれば、その節だけを投稿本文にする
    # （無いと原稿全体が本文として投稿されてしまう）。
    m = re.search(r"^##\s*キャプション[^\n]*\n(.+?)(?=\n##\s|\Z)", body, re.S | re.M)
    if m:
        body = m.group(1).strip()
    else:
        logger.warning("「## キャプション（投稿本文）」が見つからないため本文全体を使います: %s", draft.path.name)
    tags = draft.hashtags
    # キャプション末尾に既にハッシュタグ行があれば二重に付けない
    if tags and not re.search(r"(^|\n)#\S+", body):
        tag_line = " ".join(f"#{t}" for t in tags)
        body = f"{body}\n\n{tag_line}".strip()
    if len(body) > IG_CAPTION_MAX:
        logger.warning(
            "キャプションが %d 字を超過したため切り詰めます", IG_CAPTION_MAX
        )
        body = body[: IG_CAPTION_MAX - 1] + "…"
    return body


def _create_image_container(
    *,
    user_id: str,
    access_token: str,
    image_url: str,
    caption: str | None = None,
    is_carousel_item: bool = False,
) -> str:
    """単一画像のメディアコンテナを作成し、container ID を返す。"""
    import requests

    url = f"{GRAPH_API_BASE}/{user_id}/media"
    payload: dict[str, Any] = {
        "image_url": image_url,
        "access_token": access_token,
    }
    if caption is not None:
        payload["caption"] = caption
    if is_carousel_item:
        payload["is_carousel_item"] = "true"

    logger.info(
        "image container 作成: image_url=%s carousel=%s",
        image_url,
        is_carousel_item,
    )
    r = requests.post(url, data=payload, timeout=30)
    logger.info("status=%s body=%s", r.status_code, r.text)
    r.raise_for_status()
    cid = r.json().get("id")
    if not cid:
        raise RuntimeError(f"container id 取得失敗: {r.text}")
    return cid


def _create_carousel_container(
    *,
    user_id: str,
    access_token: str,
    children: list[str],
    caption: str,
) -> str:
    """カルーセル親コンテナを作成し、container ID を返す。"""
    import requests

    url = f"{GRAPH_API_BASE}/{user_id}/media"
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(children),
        "caption": caption,
        "access_token": access_token,
    }
    logger.info("carousel container 作成: children=%d", len(children))
    r = requests.post(url, data=payload, timeout=30)
    logger.info("status=%s body=%s", r.status_code, r.text)
    r.raise_for_status()
    cid = r.json().get("id")
    if not cid:
        raise RuntimeError(f"carousel container id 取得失敗: {r.text}")
    return cid


def _wait_container_ready(container_id: str, *, access_token: str) -> None:
    """コンテナが ``FINISHED`` になるまでポーリングする。

    Args:
        container_id: 対象コンテナ ID。
        access_token: Meta アクセストークン。
    """
    import requests

    url = f"{GRAPH_API_BASE}/{container_id}"
    for attempt in range(1, CONTAINER_POLL_MAX + 1):
        r = requests.get(
            url,
            params={"fields": "status_code", "access_token": access_token},
            timeout=30,
        )
        if r.ok:
            status = r.json().get("status_code")
            logger.info("ポーリング [%d] status=%s", attempt, status)
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise RuntimeError(f"container {container_id} がエラー状態: {r.text}")
        else:
            logger.warning("ポーリング失敗 [%d]: %s", attempt, r.text)
        time.sleep(CONTAINER_POLL_INTERVAL)
    raise TimeoutError(f"container {container_id} が FINISHED にならず")


def _publish_container(
    container_id: str, *, user_id: str, access_token: str
) -> str:
    """コンテナを公開し、メディア ID を返す。"""
    import requests

    url = f"{GRAPH_API_BASE}/{user_id}/media_publish"
    payload = {
        "creation_id": container_id,
        "access_token": access_token,
    }
    logger.info("公開: %s", url)
    r = requests.post(url, data=payload, timeout=30)
    logger.info("status=%s body=%s", r.status_code, r.text)
    r.raise_for_status()
    media_id = r.json().get("id")
    if not media_id:
        raise RuntimeError(f"media id 取得失敗: {r.text}")
    return media_id


def post_to_instagram(
    draft: Draft,
    *,
    user_id: str,
    access_token: str,
) -> dict[str, Any]:
    """画像 URL を解決し、Meta Graph API で Instagram に投稿する。

    Args:
        draft: 対象ドラフト。
        user_id: Instagram Business アカウント ID。
        access_token: Meta アクセストークン。

    Returns:
        ``{"post_id": ..., "image_urls": [...], "container_ids": [...]}``
    """
    caption = build_caption(draft)
    image_sources = draft.images
    if not image_sources:
        raise RuntimeError(
            f"ドラフトに image / images の指定がありません: {draft.path}"
        )

    # 画像を R2 にアップロード（URL ならそのまま）
    image_urls = [upload_if_local(src, dry_run=False) for src in image_sources]

    if len(image_urls) == 1:
        # 単一画像: container 作成 → publish
        cid = _create_image_container(
            user_id=user_id,
            access_token=access_token,
            image_url=image_urls[0],
            caption=caption,
        )
        _wait_container_ready(cid, access_token=access_token)
        post_id = _publish_container(
            cid, user_id=user_id, access_token=access_token
        )
        return {
            "post_id": post_id,
            "image_urls": image_urls,
            "container_ids": [cid],
        }

    # カルーセル: 各画像 container → 親 container → publish
    children: list[str] = []
    for url in image_urls:
        children.append(
            _create_image_container(
                user_id=user_id,
                access_token=access_token,
                image_url=url,
                is_carousel_item=True,
            )
        )
    for cid in children:
        _wait_container_ready(cid, access_token=access_token)

    parent = _create_carousel_container(
        user_id=user_id,
        access_token=access_token,
        children=children,
        caption=caption,
    )
    _wait_container_ready(parent, access_token=access_token)
    post_id = _publish_container(
        parent, user_id=user_id, access_token=access_token
    )
    return {
        "post_id": post_id,
        "image_urls": image_urls,
        "container_ids": [*children, parent],
    }


def _get_required_env(name: str) -> str:
    """必須環境変数を取得。未設定なら案内付きエラー。"""
    v = os.environ.get(name, "").strip()
    if not v:
        raise click.ClickException(
            f"環境変数 {name} が未設定です。`.env` を作成し値を入れてください。"
        )
    return v


@click.command(help="Instagram に承認済みドラフトを投稿する。")
@click.option("--date", required=True, help="対象日付（YYYY-MM-DD）")
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

    drafts = load_drafts("instagram", date)
    if not drafts:
        all_path = (PROJECT_ROOT / "docs" / "drafts" / "instagram").glob(
            f"{date}*.md"
        )
        if any(all_path):
            click.echo(f"承認済みドラフトなし (date={date})")
        else:
            click.echo(f"該当ドラフトなし (date={date})")
        return

    click.echo(
        f"=== Instagram 投稿 {len(drafts)}件 (date={date}, commit={commit}) ==="
    )

    if not commit:
        for i, d in enumerate(drafts, 1):
            cap = build_caption(d)
            click.echo(f"\n--- [{i}/{len(drafts)}] {d.path.name} ---")
            click.echo(f"images: {d.images or '(なし)'}")
            click.echo(f"caption: {truncate_for_log(cap, 200)}")
            click.echo(f"({len(cap)}文字)")
        print_dry_run_notice()
        return

    user_id = _get_required_env("META_INSTAGRAM_BUSINESS_ID")
    access_token = _get_required_env("META_ACCESS_TOKEN")

    success = 0
    for i, d in enumerate(drafts, 1):
        logger.info(
            "[%d/%d] 投稿開始 path=%s preview=%s",
            i,
            len(drafts),
            d.path.name,
            truncate_for_log(d.body),
        )
        try:
            r = post_to_instagram(
                d, user_id=user_id, access_token=access_token
            )
            log_post(
                "instagram",
                {
                    "date": date,
                    "draft_path": str(d.path.relative_to(PROJECT_ROOT)),
                    "post_id": r["post_id"],
                    "image_urls": r["image_urls"],
                    "container_ids": r["container_ids"],
                },
            )
            success += 1
            click.echo(f"[OK] {d.path.name} -> post_id={r['post_id']}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("投稿失敗: %s", d.path)
            click.echo(f"[FAIL] {d.path.name}: {exc}", err=True)

    click.echo(f"\n完了: {success}/{len(drafts)} 件成功")


if __name__ == "__main__":
    main()
