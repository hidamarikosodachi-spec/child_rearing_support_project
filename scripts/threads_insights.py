"""
==============================================================================
Threads インサイト取得スクリプト（読み取り専用・マーケ測定用）
------------------------------------------------------------------------------
用途:
    docs/posted_log/threads.jsonl に記録された投稿の指標
    （views / likes / replies / reposts / quotes）を Threads API から取得し、
    テーマ別に一覧表示する。アカウント単位（フォロワー数・プロフィール表示）も表示。

    狙い:
      - 痛みテーマ test①〜④（赤ちゃん返り/夜泣き/イヤイヤ期/叱り方）の
        どれが「能動的反応（replies+reposts+quotes）」を取れるかを観測し、
        有料記事(paid01)のテーマ選定（T050）の判断材料にする。
      - スキ/いいねは "問い/相談" の質を持たないため主指標にしない（T100準拠）。

前提:
    - `.env` に META_ACCESS_TOKEN, META_THREADS_USER_ID（Threads本番化済み）
    - 投稿が docs/posted_log/threads.jsonl に記録されていること

実行例:
    python3 scripts/threads_insights.py            # 全投稿の指標を一覧
    python3 scripts/threads_insights.py --json      # 機械可読JSONで出力

備考:
    完全に読み取り専用（GET のみ）。--commit のような副作用フラグは無い。
    指標は反映に時間差があり、フォロワーが少ない初期は 0 が続くのが正常。
==============================================================================
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.lib.draft_loader import configure_logging  # noqa: E402

logger = logging.getLogger("threads_insights")

THREADS_API_BASE = "https://graph.threads.net/v1.0"
POSTED_LOG = PROJECT_ROOT / "docs" / "posted_log" / "threads.jsonl"

# 能動的反応＝返信＋リポスト＋引用（スキ/いいねは含めない・T100準拠）
ACTIVE_METRICS = ("replies", "reposts", "quotes")
POST_METRICS = ("views", "likes", "replies", "reposts", "quotes")


def _read_theme(draft_path: str) -> str:
    """ドラフトの front-matter から theme を読む。無ければファイル名。"""
    p = PROJECT_ROOT / draft_path
    if not p.exists():
        return Path(draft_path).stem
    in_fm = False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip() == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm and line.startswith("theme:"):
            return line.split(":", 1)[1].strip()
    return Path(draft_path).stem


def _load_posts() -> list[dict[str, Any]]:
    """posted_log を読み、各投稿に theme を補う。"""
    if not POSTED_LOG.exists():
        return []
    posts = []
    for line in POSTED_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if not rec.get("post_id"):
            continue
        rec["theme"] = _read_theme(rec.get("draft_path", ""))
        posts.append(rec)
    return posts


def _get(url: str, params: dict[str, str], token: str) -> dict[str, Any]:
    import requests

    params = dict(params)
    params["access_token"] = token
    r = requests.get(url, params=params, timeout=30)
    if not r.ok:
        logger.warning("GET 失敗 status=%s body=%s", r.status_code, r.text[:300])
        return {}
    return r.json()


def fetch_post_insights(post_id: str, token: str) -> dict[str, int]:
    """1投稿のインサイトを {metric: value} で返す。"""
    data = _get(
        f"{THREADS_API_BASE}/{post_id}/insights",
        {"metric": ",".join(POST_METRICS)},
        token,
    )
    out = {m: 0 for m in POST_METRICS}
    for item in data.get("data", []):
        name = item.get("name")
        vals = item.get("values") or []
        if name in out and vals:
            out[name] = vals[0].get("value", 0)
    return out


def fetch_account(uid: str, token: str) -> dict[str, Any]:
    """アカウント単位（フォロワー数・プロフィール表示）。"""
    data = _get(
        f"{THREADS_API_BASE}/{uid}/threads_insights",
        {"metric": "followers_count,views"},
        token,
    )
    out: dict[str, Any] = {}
    for item in data.get("data", []):
        name = item.get("name")
        if "total_value" in item:
            out[name] = item["total_value"].get("value")
        else:
            vals = item.get("values") or []
            out[name] = vals[-1].get("value") if vals else None
    return out


@click.command(help="Threads 投稿のインサイトを取得して一覧表示する（読み取り専用）。")
@click.option("--json", "as_json", is_flag=True, default=False, help="JSON で出力")
def main(as_json: bool) -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    configure_logging(os.environ.get("LOG_LEVEL"))

    token = os.environ.get("META_ACCESS_TOKEN", "").strip()
    uid = os.environ.get("META_THREADS_USER_ID", "").strip()
    if not token or not uid:
        raise click.ClickException(
            "META_ACCESS_TOKEN / META_THREADS_USER_ID が未設定です（.env を確認）。"
        )

    posts = _load_posts()
    # 自分の返信（T101 の note リンク導線）は他者反応ではないので差し引く。
    # 差し引かないと、導線を張るたびに「能動反応」が自作自演で増える（insights_all.py と同じ扱い）。
    own_reply_ids = {
        r.get("reply_post_id") for r in posts if r.get("reply_post_id")
    }
    rows = []
    for p in posts:
        ins = fetch_post_insights(p["post_id"], token)
        if p.get("reply_post_id"):
            ins["replies"] = max(0, ins.get("replies", 0) - 1)
        active = sum(ins[m] for m in ACTIVE_METRICS)
        rows.append({**p, "insights": ins, "active": active})

    account = fetch_account(uid, token)

    if as_json:
        click.echo(json.dumps({"account": account, "posts": rows}, ensure_ascii=False, indent=2))
        return

    click.echo("=== Threads インサイト（読み取り専用）===")
    click.echo(
        f"フォロワー数: {account.get('followers_count', '?')}　"
        f"プロフィール表示(直近): {account.get('views', '?')}"
    )
    if not rows:
        click.echo("\n投稿記録なし（docs/posted_log/threads.jsonl が空）。")
        return

    click.echo("\n日付       | views | like | 返信 | RP | 引用 | 能動計 | テーマ")
    click.echo("-" * 78)
    for r in sorted(rows, key=lambda x: x["date"]):
        i = r["insights"]
        click.echo(
            f"{r['date']} | {i['views']:>5} | {i['likes']:>4} | {i['replies']:>4} | "
            f"{i['reposts']:>2} | {i['quotes']:>4} | {r['active']:>5}  | {r['theme']}"
        )

    # 能動的反応のトップ（リーチが付いてからのみ意味を持つ）
    ranked = sorted(rows, key=lambda x: (x["active"], x["insights"]["views"]), reverse=True)
    top = ranked[0]
    total_views = sum(r["insights"]["views"] for r in rows)
    click.echo("\n--- テーマ選定の目安（T050 有料記事）---")
    if total_views < 50:
        click.echo(
            "総views < 50：まだリーチ不足で判定は時期尚早（0が続くのは想定内）。"
            "リーチが付いてから再評価する。"
        )
    else:
        click.echo(
            f"暫定トップ: 「{top['theme']}」"
            f"（能動反応{top['active']} / views{top['insights']['views']}）。"
            "テストが出揃ったらCEOが有料記事テーマの確定/寄せ替えを判断。"
        )


if __name__ == "__main__":
    main()
