"""note 同系統記事の発見（read-only・誠実接触 T070 の接触先選定用）。

note コメント自動化（オーナー決裁 2026-06-17）の補助部品。育児・子育て・教育系の
ハッシュタグから同系統の記事を集め、**接触先候補リスト**を作る。書き込み（スキ・
コメント）は一切しない＝完全に read-only・可逆。

背景: 唯一の実エンゲージメント源（ともさん@maison_axis）も、最初はこちらから
コメントしたのが起点。相性の良い育児/子育て/教育アカウントを見つけて誠実に関わる
のは実証済みの成長レバー。本ツールはその「見つける」を担う。**深さ>広さ**。

API（2026-06-17 実地確認）:
    GET https://note.com/api/v3/hashtags/{tag}/notes?page=N
        -> data.notes[] : {key,name,body,publish_at,like_count,is_liked,is_author,price,user{...}}
    （検索API /api/v3/searches は 403。ハッシュタグAPIは 200・1ページ50件）

使い方:
    python3 scripts/note_discover.py                      # 既定の育児/教育タグで発見
    python3 scripts/note_discover.py --tag 幼児教育 --tag モンテッソーリ
    python3 scripts/note_discover.py --pages 2 --limit 40 --json
    python3 scripts/note_discover.py --exclude-liked      # まだスキしていない記事だけ
"""
from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = PROJECT_ROOT / ".auth" / "note_state.json"
HASHTAG_API = "https://note.com/api/v3/hashtags/{tag}/notes"
MY_URLNAME = "hidamari_sodachi"

# 既定の対象タグ＝育児・子育て・教育系のみ（オーナー指示2026-06-17）
DEFAULT_TAGS = [
    "子育て", "育児", "幼児教育", "知育", "子育て記録",
    "モンテッソーリ", "育児日記", "子どもの教育", "発達",
]

# 育児・子育て・教育らしさのゆるい確認（タグのノイズ落とし）
RELEVANCE_KEYWORDS = [
    "子育て", "育児", "子ども", "子供", "こども", "親", "ママ", "パパ", "母", "父",
    "保育", "幼児", "発達", "教育", "知育", "モンテ", "赤ちゃん", "乳児", "幼稚園",
    "保育園", "小学生", "習い事", "しつけ", "絵本", "イヤイヤ", "反抗期", "家庭学習",
]


def _require_session() -> None:
    if not AUTH_PATH.exists():
        raise click.ClickException(
            f"ログインセッションがありません: {AUTH_PATH}\n"
            "先に `python3 scripts/capture_note_session.py` を実行してください。"
        )


def _is_relevant(item: dict[str, Any]) -> bool:
    """タイトル＋抜粋＋著者名に育児/教育系キーワードが含まれるか（ゆるい判定）。"""
    hay = " ".join(
        [
            # API は name / nickname も null を返すことがある（2026-10-01 に遭遇）
            item.get("name") or "",
            item.get("body") or "",
            (item.get("user") or {}).get("nickname") or "",
        ]
    )
    return any(kw in hay for kw in RELEVANCE_KEYWORDS)


def discover(req, tags: list[str], pages: int) -> list[dict[str, Any]]:
    """指定タグから記事を集め、自分の記事を除外・key で重複排除して返す。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for tag in tags:
        t = urllib.parse.quote(tag)
        for page in range(1, pages + 1):
            r = req.get(f"{HASHTAG_API.format(tag=t)}?page={page}", timeout=20000)
            if r.status != 200:
                break
            notes = r.json().get("data", {}).get("notes", [])
            if not notes:
                break
            for n in notes:
                key = n.get("key")
                user = n.get("user") or {}
                if not key or key in seen:
                    continue
                if n.get("is_author") or user.get("urlname") == MY_URLNAME:
                    continue  # 自分の記事は除外
                seen.add(key)
                out.append({**n, "_tag": tag})
    return out


@click.command(help="育児/子育て/教育系の同系統記事を発見する（read-only・書込しない）。")
@click.option("--tag", "tags", multiple=True, help="対象ハッシュタグ（複数可・無指定で既定セット）")
@click.option("--pages", default=1, show_default=True, help="各タグの取得ページ数（1ページ50件）")
@click.option("--limit", default=30, show_default=True, help="表示する最大件数")
@click.option("--max-per-author", default=1, show_default=True, help="同一著者からの最大件数（1人に集中しない）")
@click.option("--exclude-liked", is_flag=True, help="既にスキ済みの記事を除外")
@click.option("--no-filter", is_flag=True, help="育児/教育キーワードのゆるい絞り込みを無効化")
@click.option("--json", "as_json", is_flag=True, help="JSON で出力")
def main(tags, pages, limit, max_per_author, exclude_liked, no_filter, as_json) -> None:
    _require_session()
    from playwright.sync_api import sync_playwright

    tag_list = list(tags) or DEFAULT_TAGS

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(storage_state=str(AUTH_PATH))
        items = discover(ctx.request, tag_list, pages)
        b.close()

    # 絞り込み
    if not no_filter:
        items = [n for n in items if _is_relevant(n)]
    if exclude_liked:
        items = [n for n in items if not n.get("is_liked")]

    # 新しい順（旬の記事＝コメントが自然）
    items.sort(key=lambda n: n.get("publish_at", ""), reverse=True)

    # 著者あたりの件数を制限（1人に集中＝スパム化を避ける）
    per_author: dict[str, int] = {}
    picked: list[dict[str, Any]] = []
    for n in items:
        au = (n.get("user") or {}).get("urlname", "?")
        if per_author.get(au, 0) >= max_per_author:
            continue
        per_author[au] = per_author.get(au, 0) + 1
        picked.append(n)
        if len(picked) >= limit:
            break

    rows = [
        {
            "key": n.get("key"),
            "url": f"https://note.com/{(n.get('user') or {}).get('urlname')}/n/{n.get('key')}",
            "title": n.get("name"),
            "author_urlname": (n.get("user") or {}).get("urlname"),
            "author_nickname": (n.get("user") or {}).get("nickname"),
            "like_count": n.get("like_count"),
            "is_liked": n.get("is_liked"),
            "price": n.get("price"),
            "publish_at": n.get("publish_at"),
            "tag": n.get("_tag"),
            "excerpt": (n.get("body") or "").strip().replace("\n", " ")[:80],
        }
        for n in picked
    ]

    if as_json:
        click.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    click.echo(f"=== 接触先候補 {len(rows)}件（タグ: {', '.join(tag_list)} / 各{pages}ページ）===")
    for i, r in enumerate(rows, 1):
        liked = " ♥済" if r["is_liked"] else ""
        paid = " 【有料】" if (r["price"] or 0) > 0 else ""
        click.echo(f"\n[{i}] {r['title']}{paid}{liked}")
        click.echo(f"    @{r['author_urlname']}（{r['author_nickname']}） ♥{r['like_count']} #{r['tag']} {r['publish_at'][:10]}")
        click.echo(f"    {r['url']}")
        click.echo(f"    抜粋: {r['excerpt']}")
    click.echo("\n※ read-only。スキ/コメントはしていません。接触は別途ガードレール付きで実施。")


if __name__ == "__main__":
    main()
